# flight_agent/services/flight_monitoring_service.py
import asyncio
import json
import redis
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from sqlalchemy.orm import sessionmaker
from ..models import SessionLocal, Booking, Flight, TripMonitor, DisruptionEvent, User, update_flight_status, create_disruption_event
from ..tools.flight_tools import get_flight_status, find_alternative_flights
import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FlightStatusData:
    """Data class for standardized flight status information"""
    flight_id: str
    status: str
    delay_minutes: int
    scheduled_departure: datetime
    actual_departure: Optional[datetime]
    scheduled_arrival: datetime
    actual_arrival: Optional[datetime]
    gate: Optional[str]
    terminal: Optional[str]
    is_disrupted: bool
    disruption_type: Optional[str]
    last_updated: datetime
    source: str  # FlightAware, backup API, etc.
    raw_data: Dict[str, Any]

class FlightDataSource:
    """Abstract base class for flight data sources"""
    
    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority  # Higher priority sources are preferred
        self.is_available = True
        self.last_error: Optional[str] = None
    
    async def get_flight_status(self, flight_number: str, departure_date: datetime) -> Optional[FlightStatusData]:
        """Get flight status from this data source"""
        raise NotImplementedError

class FlightAwareDataSource(FlightDataSource):
    """FlightAware API data source"""
    
    def __init__(self):
        super().__init__("FlightAware", priority=10)
        self.api_key = os.getenv("FLIGHTAWARE_API_KEY")
        if not self.api_key:
            self.is_available = False
            self.last_error = "API key not configured"
    
    async def get_flight_status(self, flight_number: str, departure_date: datetime) -> Optional[FlightStatusData]:
        """Get flight status from FlightAware API"""
        try:
            # Use existing flight_tools function
            status_result = get_flight_status(flight_number)
            
            if "ERROR" in status_result:
                self.last_error = status_result
                return None
            
            # Parse the status result and create FlightStatusData
            # This is a simplified parser - in production, you'd parse the full API response
            flight_id = f"{flight_number}_{departure_date.strftime('%Y%m%d')}"
            
            # Determine disruption status
            is_disrupted = any(keyword in status_result.upper() for keyword in ["CANCELLED", "DELAYED", "DIVERTED"])
            disruption_type = None
            delay_minutes = 0
            
            if "CANCELLED" in status_result.upper():
                disruption_type = "CANCELLED"
            elif "DELAYED" in status_result.upper():
                disruption_type = "DELAYED"
                delay_minutes = 120  # Default delay estimate
            elif "DIVERTED" in status_result.upper():
                disruption_type = "DIVERTED"
            
            return FlightStatusData(
                flight_id=flight_id,
                status=status_result,
                delay_minutes=delay_minutes,
                scheduled_departure=departure_date,
                actual_departure=None,  # Would be parsed from full API response
                scheduled_arrival=departure_date + timedelta(hours=2),  # Estimated
                actual_arrival=None,
                gate=None,
                terminal=None,
                is_disrupted=is_disrupted,
                disruption_type=disruption_type,
                last_updated=datetime.now(timezone.utc),
                source=self.name,
                raw_data={"status_text": status_result}
            )
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"FlightAware API error: {e}")
            return None

class BackupDataSource(FlightDataSource):
    """Mock backup data source for demonstration"""
    
    def __init__(self):
        super().__init__("BackupAPI", priority=5)
    
    async def get_flight_status(self, flight_number: str, departure_date: datetime) -> Optional[FlightStatusData]:
        """Get flight status from backup source (mock implementation)"""
        try:
            # Mock backup data source - in production, this would call another API
            flight_id = f"{flight_number}_{departure_date.strftime('%Y%m%d')}"
            
            return FlightStatusData(
                flight_id=flight_id,
                status="ON TIME (Backup Source)",
                delay_minutes=0,
                scheduled_departure=departure_date,
                actual_departure=None,
                scheduled_arrival=departure_date + timedelta(hours=2),
                actual_arrival=None,
                gate=None,
                terminal=None,
                is_disrupted=False,
                disruption_type=None,
                last_updated=datetime.now(timezone.utc),
                source=self.name,
                raw_data={"mock_data": True}
            )
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Backup API error: {e}")
            return None

class FlightMonitoringService:
    """
    Core flight monitoring service with periodic polling, multi-source aggregation, and Redis caching.
    
    Implements:
    - REQ-1.1: Real-time flight status monitoring using FlightAware API
    - REQ-1.6: Flight status checks within 5 seconds (via Redis caching)
    """
    
    def __init__(self, 
                 check_interval_seconds: int = 300,  # 5 minutes default
                 cache_ttl_seconds: int = 300,       # 5 minutes cache TTL
                 redis_url: str = None):
        """
        Initialize the flight monitoring service
        
        Args:
            check_interval_seconds: How often to poll flight status (default 5 minutes)
            cache_ttl_seconds: Redis cache TTL for flight data (default 5 minutes) 
            redis_url: Redis connection URL (defaults to localhost)
        """
        self.check_interval = check_interval_seconds
        self.cache_ttl = cache_ttl_seconds
        self.running = False
        self.last_check = {}
        
        # Initialize Redis connection
        try:
            redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis connected successfully: {redis_url}")
        except Exception as e:
            logger.warning(f"Redis not available: {e}. Running without cache.")
            self.redis_client = None
        
        # Initialize data sources (ordered by priority)
        self.data_sources: List[FlightDataSource] = [
            FlightAwareDataSource(),
            BackupDataSource()
        ]
        
        # Filter to only available sources
        self.data_sources = [src for src in self.data_sources if src.is_available]
        self.data_sources.sort(key=lambda x: x.priority, reverse=True)
        
        logger.info(f"Initialized with {len(self.data_sources)} data sources")
        
        # Statistics tracking
        self.stats = {
            "checks_performed": 0,
            "disruptions_detected": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "api_calls": 0,
            "errors": 0
        }
    
    def _get_cache_key(self, flight_number: str, departure_date: datetime) -> str:
        """Generate Redis cache key for flight status"""
        date_str = departure_date.strftime('%Y%m%d')
        return f"flight_status:{flight_number}:{date_str}"
    
    async def get_cached_flight_status(self, flight_number: str, departure_date: datetime) -> Optional[FlightStatusData]:
        """Get flight status from Redis cache"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._get_cache_key(flight_number, departure_date)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                self.stats["cache_hits"] += 1
                data = json.loads(cached_data)
                
                # Convert datetime strings back to datetime objects
                data["scheduled_departure"] = datetime.fromisoformat(data["scheduled_departure"])
                data["scheduled_arrival"] = datetime.fromisoformat(data["scheduled_arrival"])
                data["last_updated"] = datetime.fromisoformat(data["last_updated"])
                
                if data.get("actual_departure"):
                    data["actual_departure"] = datetime.fromisoformat(data["actual_departure"])
                if data.get("actual_arrival"):
                    data["actual_arrival"] = datetime.fromisoformat(data["actual_arrival"])
                
                return FlightStatusData(**data)
            else:
                self.stats["cache_misses"] += 1
                return None
                
        except Exception as e:
            logger.error(f"Redis cache read error: {e}")
            return None
    
    async def cache_flight_status(self, flight_status: FlightStatusData) -> bool:
        """Cache flight status in Redis"""
        if not self.redis_client:
            return False
        
        try:
            cache_key = self._get_cache_key(
                flight_status.flight_id.split('_')[0],  # Extract flight number from flight_id
                flight_status.scheduled_departure
            )
            
            # Convert FlightStatusData to JSON-serializable dict
            data = {
                "flight_id": flight_status.flight_id,
                "status": flight_status.status,
                "delay_minutes": flight_status.delay_minutes,
                "scheduled_departure": flight_status.scheduled_departure.isoformat(),
                "actual_departure": flight_status.actual_departure.isoformat() if flight_status.actual_departure else None,
                "scheduled_arrival": flight_status.scheduled_arrival.isoformat(),
                "actual_arrival": flight_status.actual_arrival.isoformat() if flight_status.actual_arrival else None,
                "gate": flight_status.gate,
                "terminal": flight_status.terminal,
                "is_disrupted": flight_status.is_disrupted,
                "disruption_type": flight_status.disruption_type,
                "last_updated": flight_status.last_updated.isoformat(),
                "source": flight_status.source,
                "raw_data": flight_status.raw_data
            }
            
            self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(data, default=str)
            )
            return True
            
        except Exception as e:
            logger.error(f"Redis cache write error: {e}")
            return False
    
    async def get_flight_status_multi_source(self, flight_number: str, departure_date: datetime) -> Optional[FlightStatusData]:
        """
        Get flight status using multi-source aggregation with fallback
        
        REQ-1.6: Ensures flight status checks complete within 5 seconds via caching
        """
        # First, check cache for quick response (sub-second)
        cached_status = await self.get_cached_flight_status(flight_number, departure_date)
        if cached_status:
            # Check if cache is still fresh (< 2 minutes old for critical updates)
            age = (datetime.now(timezone.utc) - cached_status.last_updated).total_seconds()
            if age < 120:  # 2 minutes
                return cached_status
        
        # If cache miss or stale, try data sources in priority order
        self.stats["api_calls"] += 1
        
        for source in self.data_sources:
            try:
                logger.info(f"Trying {source.name} for {flight_number}")
                status_data = await source.get_flight_status(flight_number, departure_date)
                
                if status_data:
                    # Cache the result for future quick access
                    await self.cache_flight_status(status_data)
                    logger.info(f"Got status from {source.name}: {status_data.status}")
                    return status_data
                    
            except Exception as e:
                logger.error(f"Error with {source.name}: {e}")
                source.last_error = str(e)
                self.stats["errors"] += 1
                continue
        
        # If all sources failed, return cached data even if stale
        if cached_status:
            logger.warning(f"All sources failed, returning stale cache for {flight_number}")
            return cached_status
        
        logger.error(f"No flight status available for {flight_number}")
        return None
    
    async def start_monitoring(self):
        """Start the periodic flight monitoring loop"""
        self.running = True
        logger.info(f"🚀 Flight monitoring service started (check interval: {self.check_interval}s)")
        
        while self.running:
            try:
                await self._monitor_all_flights()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                self.stats["errors"] += 1
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False
        logger.info("🛑 Flight monitoring service stopped")
    
    async def _monitor_all_flights(self):
        """Monitor all active bookings for disruptions"""
        db = SessionLocal()
        try:
            # Get active trip monitors (following existing pattern)
            active_monitors = db.query(TripMonitor).filter(
                TripMonitor.is_active == True,
                TripMonitor.expires_at > datetime.now(timezone.utc) if TripMonitor.expires_at.isnot(None) else True
            ).all()
            
            logger.info(f"Monitoring {len(active_monitors)} flights...")
            self.stats["checks_performed"] += len(active_monitors)
            
            for monitor in active_monitors:
                await self._monitor_single_flight(monitor, db)
                
        finally:
            db.close()
    
    async def _monitor_single_flight(self, monitor: TripMonitor, db):
        """Monitor a single flight for disruptions"""
        try:
            booking = db.query(Booking).filter(Booking.booking_id == monitor.booking_id).first()
            if not booking:
                logger.warning(f"Booking {monitor.booking_id} not found")
                return
            
            # Skip if checked recently (per monitor frequency settings)
            if monitor.last_check:
                minutes_since_check = (datetime.now(timezone.utc) - monitor.last_check).total_seconds() / 60
                if minutes_since_check < monitor.check_frequency_minutes:
                    return
            
            logger.info(f"  ✈️  Checking {booking.flight_number} for user {booking.user_id}")
            
            # Get flight status using multi-source aggregation
            status_data = await self.get_flight_status_multi_source(
                booking.flight_number,
                booking.departure_date
            )
            
            if not status_data:
                logger.warning(f"  ❌ No status data for {booking.flight_number}")
                return
            
            # Update flight record in database
            if booking.flight_id:
                await self._update_flight_record(booking.flight_id, status_data, db)
            
            # Check for disruptions
            if status_data.is_disrupted:
                logger.warning(f"  🚨 DISRUPTION: {booking.flight_number} - {status_data.disruption_type}")
                await self._handle_disruption(booking, status_data, db)
                self.stats["disruptions_detected"] += 1
            else:
                logger.info(f"  ✅ {booking.flight_number} is {status_data.status}")
            
            # Update monitor last check time
            monitor.last_check = datetime.now(timezone.utc)
            db.commit()
            
        except Exception as e:
            logger.error(f"  ❌ Error monitoring {monitor.monitor_id}: {e}")
            self.stats["errors"] += 1
    
    async def _update_flight_record(self, flight_id: str, status_data: FlightStatusData, db):
        """Update flight record with latest status"""
        try:
            update_data = {
                "flight_status": status_data.status,
                "delay_minutes": status_data.delay_minutes,
                "actual_departure": status_data.actual_departure,
                "actual_arrival": status_data.actual_arrival,
                "gate": status_data.gate,
                "terminal": status_data.terminal,
                "raw_flight_data": status_data.raw_data
            }
            
            update_flight_status(flight_id, update_data)
            
        except Exception as e:
            logger.error(f"Error updating flight {flight_id}: {e}")
    
    async def _handle_disruption(self, booking: Booking, status_data: FlightStatusData, db):
        """Handle a detected flight disruption"""
        try:
            # Check if disruption event already exists
            existing_event = db.query(DisruptionEvent).filter(
                DisruptionEvent.booking_id == booking.booking_id,
                DisruptionEvent.rebooking_status.in_(["PENDING", "IN_PROGRESS"])
            ).first()
            
            if existing_event:
                logger.info(f"    ℹ️  Disruption already being handled")
                return
            
            # Create disruption event
            disruption_data = {
                "type": status_data.disruption_type,
                "original_departure": booking.departure_date,
                "delay_minutes": status_data.delay_minutes,
                "reason": f"Flight {status_data.disruption_type.lower()} detected via {status_data.source}"
            }
            
            if status_data.actual_departure:
                disruption_data["new_departure"] = status_data.actual_departure
            
            event = create_disruption_event(booking.booking_id, disruption_data)
            
            # Find alternative flights if needed
            if status_data.disruption_type in ["CANCELLED", "DIVERTED"]:
                logger.info(f"    🔍 Finding alternatives for {booking.origin} → {booking.destination}")
                alternatives = find_alternative_flights(
                    booking.origin,
                    booking.destination,
                    booking.departure_date.strftime("%Y-%m-%d")
                )
                
                if alternatives and "error" not in alternatives.lower():
                    # Update event with alternatives (would need to re-query the event)
                    # This is simplified - in production, you'd properly update the event
                    logger.info(f"    ✅ Found alternatives: {alternatives[:100]}...")
            
            logger.info(f"    📧 Disruption event created: {event.event_id}")
            
        except Exception as e:
            logger.error(f"    ❌ Error handling disruption: {e}")
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics and health info"""
        data_source_health = []
        for source in self.data_sources:
            data_source_health.append({
                "name": source.name,
                "priority": source.priority,
                "available": source.is_available,
                "last_error": source.last_error
            })
        
        return {
            "service_status": "running" if self.running else "stopped",
            "check_interval_seconds": self.check_interval,
            "cache_ttl_seconds": self.cache_ttl,
            "redis_connected": self.redis_client is not None,
            "data_sources": data_source_health,
            "statistics": self.stats,
            "last_check_times": len(self.last_check)
        }

# Standalone monitoring service function
async def run_monitoring_service(check_interval: int = 300):
    """
    Run the monitoring service as a standalone process
    
    Args:
        check_interval: Check interval in seconds (default 5 minutes)
    """
    service = FlightMonitoringService(check_interval_seconds=check_interval)
    
    try:
        await service.start_monitoring()
    except KeyboardInterrupt:
        service.stop_monitoring()
        logger.info("Flight monitoring service stopped by user")

if __name__ == "__main__":
    # Run: python -m flight_agent.services.flight_monitoring_service
    asyncio.run(run_monitoring_service(check_interval=60))  # 1 minute for testing
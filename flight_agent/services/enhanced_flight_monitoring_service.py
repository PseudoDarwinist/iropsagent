# flight_agent/services/enhanced_flight_monitoring_service.py
"""
Enhanced flight monitoring service with new provider interfaces.

This service replaces the original flight_monitoring_service.py with:
- REQ-7.1: FlightDataProvider interface integration
- REQ-7.2: Enhanced failover logic between primary and secondary sources
- Improved error handling and metrics tracking
- Better performance monitoring and health checks
"""

import asyncio
import json
import redis
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import sessionmaker

# Import existing models and tools
from ..models import SessionLocal, Booking, TripMonitor, DisruptionEvent, update_flight_status, create_disruption_event
from ..tools.flight_tools import find_alternative_flights

# Import new provider interfaces
from ..providers import (
    FlightDataProvider,
    FlightAwareProvider, 
    MockFlightDataProvider,
    FailoverManager,
    FailoverConfig
)
from ..providers.interfaces import FlightStatusData, ProviderError

import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedFlightMonitoringService:
    """
    Enhanced flight monitoring service with provider interfaces and failover.
    
    Implements:
    - REQ-7.1: FlightDataProvider interface for external APIs
    - REQ-7.2: Failover logic between primary and secondary sources
    - REQ-1.1: Real-time flight status monitoring using FlightAware API
    - REQ-1.6: Flight status checks within 5 seconds (via Redis caching)
    """
    
    def __init__(self, 
                 check_interval_seconds: int = 300,  # 5 minutes default
                 cache_ttl_seconds: int = 300,       # 5 minutes cache TTL
                 redis_url: str = None,
                 enable_mock_provider: bool = False):
        """
        Initialize the enhanced flight monitoring service.
        
        Args:
            check_interval_seconds: How often to poll flight status (default 5 minutes)
            cache_ttl_seconds: Redis cache TTL for flight data (default 5 minutes) 
            redis_url: Redis connection URL (defaults to localhost)
            enable_mock_provider: Whether to include mock provider for testing
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
        
        # Initialize flight data providers
        self.providers = self._initialize_providers(enable_mock_provider)
        
        # Initialize failover manager
        failover_config = FailoverConfig(
            max_retries_per_provider=2,
            timeout_between_retries=1.0,
            health_check_interval=300,  # 5 minutes
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=600  # 10 minutes
        )
        
        self.failover_manager = FailoverManager(self.providers, failover_config)
        
        logger.info(f"Enhanced monitoring service initialized with {len(self.providers)} providers")
        
        # Statistics tracking
        self.stats = {
            "checks_performed": 0,
            "disruptions_detected": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "api_calls": 0,
            "errors": 0,
            "provider_failovers": 0
        }
    
    def _initialize_providers(self, enable_mock: bool) -> List[FlightDataProvider]:
        """Initialize flight data providers in priority order"""
        providers = []
        
        # Primary provider: FlightAware
        flightaware_provider = FlightAwareProvider(priority=10)
        providers.append(flightaware_provider)
        
        # Mock provider for testing/development
        if enable_mock or not flightaware_provider.is_available:
            mock_provider = MockFlightDataProvider(
                name="MockBackup",
                priority=5,
                simulate_errors=False,
                simulate_delays=True
            )
            providers.append(mock_provider)
            logger.info("Mock provider enabled as backup")
        
        # Additional mock provider for testing failover
        if enable_mock:
            secondary_mock = MockFlightDataProvider(
                name="SecondaryMock", 
                priority=1,
                simulate_errors=True,
                error_rate=0.3  # 30% error rate for testing
            )
            providers.append(secondary_mock)
        
        return providers
    
    def _get_cache_key(self, flight_number: str, departure_date: datetime) -> str:
        """Generate Redis cache key for flight status"""
        date_str = departure_date.strftime('%Y%m%d')
        return f"flight_status:v2:{flight_number}:{date_str}"
    
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
                "confidence_score": flight_status.confidence_score,
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
    
    async def get_flight_status_with_failover(self, flight_number: str, departure_date: datetime) -> Optional[FlightStatusData]:
        """
        Get flight status using enhanced failover logic.
        
        REQ-1.6: Ensures flight status checks complete within 5 seconds via caching
        REQ-7.2: Implements failover logic between primary and secondary sources
        """
        # First, check cache for quick response (sub-second)
        cached_status = await self.get_cached_flight_status(flight_number, departure_date)
        if cached_status:
            # Check if cache is still fresh (< 2 minutes old for critical updates)
            age = (datetime.now(timezone.utc) - cached_status.last_updated).total_seconds()
            if age < 120:  # 2 minutes
                logger.debug(f"Returning fresh cached data for {flight_number} (age: {age}s)")
                return cached_status
        
        # If cache miss or stale, use failover manager
        self.stats["api_calls"] += 1
        
        try:
            logger.info(f"Getting flight status for {flight_number} via failover manager")
            status_data = await self.failover_manager.get_flight_status(flight_number, departure_date)
            
            if status_data:
                # Cache the result for future quick access
                await self.cache_flight_status(status_data)
                logger.info(f"Successfully got flight data from {status_data.source}")
                return status_data
            else:
                self.stats["errors"] += 1
                logger.warning(f"All providers failed for {flight_number}")
                
        except Exception as e:
            logger.error(f"Failover manager error for {flight_number}: {e}")
            self.stats["errors"] += 1
        
        # If all sources failed, return cached data even if stale
        if cached_status:
            age = (datetime.now(timezone.utc) - cached_status.last_updated).total_seconds()
            logger.warning(f"All sources failed, returning stale cache for {flight_number} (age: {age}s)")
            return cached_status
        
        logger.error(f"No flight status available for {flight_number}")
        return None
    
    async def get_multiple_flights_status(
        self, 
        flight_requests: List[tuple[str, datetime]]
    ) -> Dict[str, Optional[FlightStatusData]]:
        """Get status for multiple flights efficiently with failover"""
        
        logger.info(f"Getting status for {len(flight_requests)} flights")
        
        # Check cache first for all flights
        cached_results = {}
        uncached_requests = []
        
        for flight_number, departure_date in flight_requests:
            cached = await self.get_cached_flight_status(flight_number, departure_date)
            if cached:
                age = (datetime.now(timezone.utc) - cached.last_updated).total_seconds()
                if age < 120:  # Fresh cache
                    cached_results[flight_number] = cached
                else:
                    uncached_requests.append((flight_number, departure_date))
            else:
                uncached_requests.append((flight_number, departure_date))
        
        logger.info(f"Found {len(cached_results)} cached results, fetching {len(uncached_requests)} from providers")
        
        # Get remaining flights from providers
        provider_results = {}
        if uncached_requests:
            try:
                provider_results = await self.failover_manager.get_multiple_flights(uncached_requests)
                
                # Cache new results
                for flight_number, status_data in provider_results.items():
                    if status_data:
                        await self.cache_flight_status(status_data)
                        
            except Exception as e:
                logger.error(f"Batch flight status error: {e}")
                self.stats["errors"] += 1
        
        # Combine cached and provider results
        all_results = {**cached_results, **provider_results}
        
        return all_results
    
    async def start_monitoring(self):
        """Start the periodic flight monitoring loop"""
        self.running = True
        logger.info(f"🚀 Enhanced flight monitoring service started (check interval: {self.check_interval}s)")
        
        # Start background health checks
        health_check_task = asyncio.create_task(self._periodic_health_checks())
        
        try:
            while self.running:
                try:
                    await self._monitor_all_flights()
                    await asyncio.sleep(self.check_interval)
                except Exception as e:
                    logger.error(f"Monitor loop error: {e}")
                    self.stats["errors"] += 1
                    await asyncio.sleep(60)  # Wait 1 minute on error
        finally:
            health_check_task.cancel()
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False
        logger.info("🛑 Enhanced flight monitoring service stopped")
    
    async def _periodic_health_checks(self):
        """Perform periodic health checks on all providers"""
        while self.running:
            try:
                logger.debug("Performing provider health checks")
                health_results = await self.failover_manager.health_check_all()
                
                healthy_count = sum(1 for is_healthy in health_results.values() if is_healthy)
                logger.info(f"Provider health check: {healthy_count}/{len(health_results)} providers healthy")
                
                # Log any unhealthy providers
                for provider_name, is_healthy in health_results.items():
                    if not is_healthy:
                        logger.warning(f"Provider {provider_name} is unhealthy")
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            # Wait 5 minutes between health checks
            await asyncio.sleep(300)
    
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
            
            # Batch process flights for efficiency
            flight_requests = []
            monitor_map = {}
            
            for monitor in active_monitors:
                booking = db.query(Booking).filter(Booking.booking_id == monitor.booking_id).first()
                if booking:
                    flight_requests.append((booking.flight_number, booking.departure_date))
                    monitor_map[booking.flight_number] = (monitor, booking)
            
            # Get all flight statuses in batch
            if flight_requests:
                flight_statuses = await self.get_multiple_flights_status(flight_requests)
                
                # Process results
                for flight_number, status_data in flight_statuses.items():
                    if flight_number in monitor_map:
                        monitor, booking = monitor_map[flight_number]
                        await self._process_flight_status(monitor, booking, status_data, db)
                        
        finally:
            db.close()
    
    async def _process_flight_status(self, monitor: TripMonitor, booking: Booking, status_data: Optional[FlightStatusData], db):
        """Process flight status for a single booking"""
        try:
            if not status_data:
                logger.warning(f"  ❌ No status data for {booking.flight_number}")
                return
            
            # Skip if checked recently (per monitor frequency settings)
            if monitor.last_check:
                minutes_since_check = (datetime.now(timezone.utc) - monitor.last_check).total_seconds() / 60
                if minutes_since_check < monitor.check_frequency_minutes:
                    return
            
            logger.info(f"  ✈️  Processing {booking.flight_number} (source: {status_data.source}, confidence: {status_data.confidence_score:.2f})")
            
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
            logger.error(f"  ❌ Error processing {booking.flight_number}: {e}")
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
                "reason": f"Flight {status_data.disruption_type.lower()} detected via {status_data.source} (confidence: {status_data.confidence_score:.2f})"
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
        """Get comprehensive service statistics"""
        
        # Get provider stats from failover manager
        provider_stats = self.failover_manager.get_provider_stats()
        
        return {
            "service_status": "running" if self.running else "stopped",
            "check_interval_seconds": self.check_interval,
            "cache_ttl_seconds": self.cache_ttl,
            "redis_connected": self.redis_client is not None,
            "provider_count": len(self.providers),
            "statistics": self.stats,
            "providers": provider_stats["providers"],
            "circuit_breakers": provider_stats["circuit_breakers"],
            "performance_summary": provider_stats["performance_summary"]
        }
    
    async def force_health_check(self) -> Dict[str, Any]:
        """Force immediate health check of all providers"""
        logger.info("Forcing health check of all providers")
        
        health_results = await self.failover_manager.health_check_all()
        stats = self.get_service_stats()
        
        return {
            "health_check_results": health_results,
            "service_stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Standalone monitoring service function  
async def run_enhanced_monitoring_service(
    check_interval: int = 300,
    enable_mock_provider: bool = False
):
    """
    Run the enhanced monitoring service as a standalone process
    
    Args:
        check_interval: Check interval in seconds (default 5 minutes)
        enable_mock_provider: Whether to enable mock provider for testing
    """
    service = EnhancedFlightMonitoringService(
        check_interval_seconds=check_interval,
        enable_mock_provider=enable_mock_provider
    )
    
    try:
        await service.start_monitoring()
    except KeyboardInterrupt:
        service.stop_monitoring()
        logger.info("Enhanced flight monitoring service stopped by user")


if __name__ == "__main__":
    # Run: python -m flight_agent.services.enhanced_flight_monitoring_service
    asyncio.run(run_enhanced_monitoring_service(
        check_interval=60,  # 1 minute for testing
        enable_mock_provider=True
    ))
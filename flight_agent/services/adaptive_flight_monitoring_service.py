# flight_agent/services/adaptive_flight_monitoring_service.py
"""
Adaptive Flight Monitoring Service
Task 2.3: Implement monitoring frequency adjustment

This service combines the EnhancedFlightMonitoringService with the 
MonitoringFrequencyManager to provide dynamic, risk-based monitoring 
with intelligent frequency adjustments.

Features:
- Dynamic polling frequency based on risk assessment
- High-risk route detection and flagging
- Monitoring interruption notifications
- Performance optimization through intelligent intervals
- Full integration with existing monitoring infrastructure
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from .enhanced_flight_monitoring_service import EnhancedFlightMonitoringService
from .monitoring_frequency_manager import MonitoringFrequencyManager, run_monitoring_frequency_adjustment
from ..models import SessionLocal, TripMonitor

logger = logging.getLogger(__name__)


class AdaptiveFlightMonitoringService(EnhancedFlightMonitoringService):
    """
    Adaptive flight monitoring service with dynamic frequency adjustment.
    
    Extends EnhancedFlightMonitoringService with:
    - REQ-1.3: Dynamic monitoring frequency based on risk assessment
    - REQ-1.4: High-risk route flagging (>40% delay rate threshold)
    - REQ-1.6: Performance optimization through intelligent polling intervals
    """
    
    def __init__(self, 
                 check_interval_seconds: int = 300,  # Base interval, will be dynamic per monitor
                 cache_ttl_seconds: int = 300,
                 redis_url: str = None,
                 enable_mock_provider: bool = False,
                 frequency_adjustment_interval: int = 900):  # 15 minutes
        """
        Initialize adaptive flight monitoring service.
        
        Args:
            check_interval_seconds: Base check interval (individual monitors may vary)
            cache_ttl_seconds: Redis cache TTL for flight data
            redis_url: Redis connection URL
            enable_mock_provider: Whether to enable mock provider for testing
            frequency_adjustment_interval: How often to run frequency adjustments (seconds)
        """
        super().__init__(check_interval_seconds, cache_ttl_seconds, redis_url, enable_mock_provider)
        
        # Initialize frequency manager
        self.frequency_manager = MonitoringFrequencyManager(self)
        self.frequency_adjustment_interval = frequency_adjustment_interval
        self.last_frequency_adjustment = None
        
        # Enhanced statistics
        self.adaptive_stats = {
            "frequency_adjustments": 0,
            "high_risk_routes_monitored": 0,
            "interruption_alerts_sent": 0,
            "performance_optimizations": 0,
            "average_monitoring_frequency": 15.0  # minutes
        }
        
        logger.info("AdaptiveFlightMonitoringService initialized with dynamic frequency adjustment")
    
    async def start_monitoring(self):
        """Start the adaptive monitoring loop with frequency management"""
        self.running = True
        logger.info(f"🚀 Adaptive flight monitoring service started (base interval: {self.check_interval}s)")
        
        # Start background tasks
        health_check_task = asyncio.create_task(self._periodic_health_checks())
        frequency_adjustment_task = asyncio.create_task(self._periodic_frequency_adjustments())
        
        try:
            while self.running:
                try:
                    await self._adaptive_monitor_all_flights()
                    await asyncio.sleep(self.check_interval)
                except Exception as e:
                    logger.error(f"Adaptive monitor loop error: {e}")
                    self.stats["errors"] += 1
                    await asyncio.sleep(60)  # Wait 1 minute on error
        finally:
            health_check_task.cancel()
            frequency_adjustment_task.cancel()
    
    async def _periodic_frequency_adjustments(self):
        """Run periodic frequency adjustments and optimization"""
        while self.running:
            try:
                logger.debug("Running periodic frequency adjustments")
                
                # Run frequency adjustment cycle
                adjustment_summary = await self.frequency_manager.run_monitoring_adjustment_cycle()
                
                # Update statistics
                if "monitors_optimized" in adjustment_summary:
                    self.adaptive_stats["performance_optimizations"] += adjustment_summary["monitors_optimized"]
                
                if "interruption_alerts_created" in adjustment_summary:
                    self.adaptive_stats["interruption_alerts_sent"] += adjustment_summary["interruption_alerts_created"]
                
                # Calculate average monitoring frequency
                await self._update_average_frequency_stats()
                
                self.last_frequency_adjustment = datetime.now(timezone.utc)
                
                logger.info(f"Frequency adjustment cycle completed: {adjustment_summary.get('monitors_optimized', 0)} monitors optimized")
                
            except Exception as e:
                logger.error(f"Frequency adjustment error: {e}")
            
            # Wait for next adjustment cycle
            await asyncio.sleep(self.frequency_adjustment_interval)
    
    async def _adaptive_monitor_all_flights(self):
        """
        Monitor flights with adaptive frequency per monitor.
        
        Each monitor is checked based on its individual frequency setting,
        rather than using a global interval.
        """
        db = SessionLocal()
        try:
            # Get all active trip monitors
            active_monitors = db.query(TripMonitor).filter(
                TripMonitor.is_active == True,
                TripMonitor.expires_at > datetime.now(timezone.utc) if TripMonitor.expires_at.isnot(None) else True
            ).all()
            
            current_time = datetime.now(timezone.utc)
            monitors_checked = 0
            
            logger.debug(f"Evaluating {len(active_monitors)} monitors for adaptive checking")
            
            # Group monitors by their check frequency for batch processing
            frequency_groups = {}
            
            for monitor in active_monitors:
                # Check if this monitor is due for a check based on its individual frequency
                if self._is_monitor_due_for_check(monitor, current_time):
                    frequency = monitor.check_frequency_minutes
                    if frequency not in frequency_groups:
                        frequency_groups[frequency] = []
                    frequency_groups[frequency].append(monitor)
            
            # Process each frequency group
            for frequency, monitors_in_group in frequency_groups.items():
                logger.debug(f"Processing {len(monitors_in_group)} monitors with {frequency}min frequency")
                
                # Batch process flights for efficiency (from parent class)
                flight_requests = []
                monitor_map = {}
                
                for monitor in monitors_in_group:
                    booking = db.query(self._get_booking_model()).filter(
                        self._get_booking_model().booking_id == monitor.booking_id
                    ).first()
                    if booking:
                        flight_requests.append((booking.flight_number, booking.departure_date))
                        monitor_map[booking.flight_number] = (monitor, booking)
                
                # Get flight statuses in batch
                if flight_requests:
                    flight_statuses = await self.get_multiple_flights_status(flight_requests)
                    
                    # Process results
                    for flight_number, status_data in flight_statuses.items():
                        if flight_number in monitor_map:
                            monitor, booking = monitor_map[flight_number]
                            await self._process_flight_status(monitor, booking, status_data, db)
                            monitors_checked += 1
            
            self.stats["checks_performed"] += len(active_monitors)
            logger.info(f"Adaptive monitoring: checked {monitors_checked}/{len(active_monitors)} monitors")
            
        finally:
            db.close()
    
    def _is_monitor_due_for_check(self, monitor: TripMonitor, current_time: datetime) -> bool:
        """
        Determine if a monitor is due for a check based on its individual frequency.
        
        This allows each monitor to have its own check schedule.
        """
        if not monitor.last_check:
            return True  # First check
        
        time_since_last_check = (current_time - monitor.last_check).total_seconds() / 60  # minutes
        return time_since_last_check >= monitor.check_frequency_minutes
    
    def _get_booking_model(self):
        """Get the Booking model class for database queries"""
        from ..models import Booking
        return Booking
    
    async def _update_average_frequency_stats(self):
        """Update average monitoring frequency statistics"""
        db = SessionLocal()
        try:
            active_monitors = db.query(TripMonitor).filter(TripMonitor.is_active == True).all()
            
            if active_monitors:
                total_frequency = sum(monitor.check_frequency_minutes for monitor in active_monitors)
                self.adaptive_stats["average_monitoring_frequency"] = total_frequency / len(active_monitors)
                
                # Count high-risk routes being monitored
                high_risk_count = 0
                for monitor in active_monitors:
                    if monitor.check_frequency_minutes <= 5:  # High frequency = high risk
                        high_risk_count += 1
                
                self.adaptive_stats["high_risk_routes_monitored"] = high_risk_count
                
        finally:
            db.close()
    
    async def trigger_frequency_optimization(self) -> Dict[str, Any]:
        """
        Manually trigger frequency optimization.
        
        Useful for API endpoints or immediate optimization needs.
        Returns optimization results.
        """
        logger.info("Manual frequency optimization triggered")
        
        optimization_results = await self.frequency_manager.run_monitoring_adjustment_cycle()
        
        # Update statistics
        if "monitors_optimized" in optimization_results:
            self.adaptive_stats["performance_optimizations"] += optimization_results["monitors_optimized"]
            self.adaptive_stats["frequency_adjustments"] += optimization_results["monitors_optimized"]
        
        if "interruption_alerts_created" in optimization_results:
            self.adaptive_stats["interruption_alerts_sent"] += optimization_results["interruption_alerts_created"]
        
        await self._update_average_frequency_stats()
        
        return optimization_results
    
    async def get_high_risk_routes(self) -> List[Dict[str, Any]]:
        """
        Get list of currently identified high-risk routes.
        
        REQ-1.4: High-risk route identification with >40% delay rate
        """
        high_risk_routes = []
        
        # Get routes from frequency manager cache
        for route, stats in self.frequency_manager.route_stats_cache.items():
            if stats.delay_rate > self.frequency_manager.high_risk_delay_threshold:
                high_risk_routes.append({
                    "route": route,
                    "delay_rate": stats.delay_rate,
                    "total_flights": stats.total_flights,
                    "delayed_flights": stats.delayed_flights,
                    "average_delay_minutes": stats.average_delay_minutes,
                    "last_updated": stats.last_updated.isoformat(),
                    "risk_level": "HIGH"
                })
        
        # Sort by delay rate (highest first)
        high_risk_routes.sort(key=lambda x: x["delay_rate"], reverse=True)
        
        return high_risk_routes
    
    async def get_monitoring_interruptions(self) -> List[Dict[str, Any]]:
        """
        Get current monitoring interruptions.
        
        REQ-1.3: Monitoring interruption detection
        """
        interruptions = []
        interruption_threshold = timedelta(minutes=self.frequency_manager.interruption_notification_threshold)
        threshold_time = datetime.now(timezone.utc) - interruption_threshold
        
        db = SessionLocal()
        try:
            interrupted_monitors = db.query(TripMonitor).filter(
                TripMonitor.is_active == True,
                TripMonitor.last_check < threshold_time,
                TripMonitor.last_check.isnot(None)
            ).all()
            
            for monitor in interrupted_monitors:
                booking = db.query(self._get_booking_model()).filter(
                    self._get_booking_model().booking_id == monitor.booking_id
                ).first()
                
                if booking:
                    interruption_minutes = (datetime.now(timezone.utc) - monitor.last_check).total_seconds() / 60
                    
                    interruptions.append({
                        "monitor_id": monitor.monitor_id,
                        "flight_number": booking.flight_number,
                        "route": f"{booking.origin}-{booking.destination}",
                        "last_check": monitor.last_check.isoformat(),
                        "interruption_minutes": round(interruption_minutes, 1),
                        "expected_frequency": monitor.check_frequency_minutes,
                        "severity": self._classify_interruption_severity(interruption_minutes)
                    })
        finally:
            db.close()
        
        return interruptions
    
    def _classify_interruption_severity(self, interruption_minutes: float) -> str:
        """Classify interruption severity based on duration"""
        if interruption_minutes >= 120:  # 2+ hours
            return "CRITICAL"
        elif interruption_minutes >= 60:  # 1-2 hours
            return "HIGH"
        else:  # 30min - 1 hour
            return "MEDIUM"
    
    def get_adaptive_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive adaptive monitoring statistics"""
        base_stats = self.get_service_stats()
        frequency_stats = self.frequency_manager.get_adjustment_statistics()
        
        return {
            **base_stats,
            "adaptive_statistics": self.adaptive_stats.copy(),
            "frequency_management": frequency_stats,
            "last_frequency_adjustment": self.last_frequency_adjustment.isoformat() if self.last_frequency_adjustment else None,
            "adaptive_features": {
                "dynamic_frequency_enabled": True,
                "high_risk_threshold": self.frequency_manager.high_risk_delay_threshold,
                "interruption_threshold_minutes": self.frequency_manager.interruption_notification_threshold,
                "base_frequencies": {
                    "high_risk": 5,
                    "default": 15,
                    "low_risk": 30
                }
            }
        }
    
    async def force_health_check_with_frequency_analysis(self) -> Dict[str, Any]:
        """Enhanced health check with frequency analysis"""
        base_health = await self.force_health_check()
        
        # Add frequency management health
        high_risk_routes = await self.get_high_risk_routes()
        interruptions = await self.get_monitoring_interruptions()
        
        frequency_health = {
            "frequency_manager_healthy": True,
            "high_risk_routes_count": len(high_risk_routes),
            "active_interruptions_count": len(interruptions),
            "average_frequency_minutes": self.adaptive_stats["average_monitoring_frequency"],
            "optimization_recommendations": []
        }
        
        # Add optimization recommendations
        if len(interruptions) > 0:
            frequency_health["optimization_recommendations"].append(
                f"Found {len(interruptions)} monitoring interruptions - consider system health check"
            )
        
        if len(high_risk_routes) > 5:
            frequency_health["optimization_recommendations"].append(
                f"Monitoring {len(high_risk_routes)} high-risk routes - resource usage may be elevated"
            )
        
        return {
            **base_health,
            "frequency_management_health": frequency_health
        }


# Standalone function for running adaptive monitoring
async def run_adaptive_monitoring_service(
    check_interval: int = 300,
    enable_mock_provider: bool = False,
    frequency_adjustment_interval: int = 900
):
    """
    Run the adaptive monitoring service as a standalone process.
    
    Args:
        check_interval: Base check interval in seconds
        enable_mock_provider: Whether to enable mock provider for testing
        frequency_adjustment_interval: Frequency adjustment interval in seconds
    """
    service = AdaptiveFlightMonitoringService(
        check_interval_seconds=check_interval,
        enable_mock_provider=enable_mock_provider,
        frequency_adjustment_interval=frequency_adjustment_interval
    )
    
    try:
        await service.start_monitoring()
    except KeyboardInterrupt:
        service.stop_monitoring()
        logger.info("Adaptive flight monitoring service stopped by user")


if __name__ == "__main__":
    # Run: python -m flight_agent.services.adaptive_flight_monitoring_service
    asyncio.run(run_adaptive_monitoring_service(
        check_interval=60,  # 1 minute base interval for testing
        enable_mock_provider=True,
        frequency_adjustment_interval=300  # 5 minute frequency adjustments for testing
    ))
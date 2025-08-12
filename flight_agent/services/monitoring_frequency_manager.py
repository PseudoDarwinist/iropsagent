# flight_agent/services/monitoring_frequency_manager.py
"""
Monitoring Frequency Adjustment Manager
Task 2.3: Implement monitoring frequency adjustment

This module implements:
- Dynamic polling frequency (15min default, 5min high-risk)
- High-risk route flagging based on historical data (>40% delay rate) 
- Monitoring interruption notifications (30min threshold)
- Requirements: REQ-1.3, REQ-1.4, REQ-1.6

Features:
- REQ-1.3: Dynamic monitoring frequencies based on risk assessment
- REQ-1.4: High-risk route identification with >40% delay rate threshold
- REQ-1.6: Performance optimization through intelligent polling intervals
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from ..models import (
    SessionLocal, TripMonitor, Booking, DisruptionEvent, DisruptionAlert, 
    create_disruption_alert, User, get_users_with_sms_enabled
)
from .disruption_risk_detector import DisruptionRiskDetector, RiskLevel, detect_disruption_risk
from .enhanced_flight_monitoring_service import EnhancedFlightMonitoringService

logger = logging.getLogger(__name__)


class MonitoringFrequency(Enum):
    """Monitoring frequency levels based on risk assessment"""
    HIGH_FREQUENCY = 5    # 5 minutes for high-risk routes/flights
    DEFAULT_FREQUENCY = 15  # 15 minutes default frequency
    LOW_FREQUENCY = 30    # 30 minutes for low-risk flights
    
    
class RouteRiskLevel(Enum):
    """Route risk levels based on historical delay data"""
    HIGH_RISK = "high"      # >40% historical delay rate
    MEDIUM_RISK = "medium"  # 20-40% delay rate
    LOW_RISK = "low"        # <20% delay rate


@dataclass
class RouteDelayStats:
    """Historical delay statistics for a route"""
    route: str  # "ORIGIN-DESTINATION" format
    total_flights: int
    delayed_flights: int
    delay_rate: float  # Percentage of flights delayed
    average_delay_minutes: float
    last_updated: datetime
    sample_period_days: int = 30


@dataclass
class MonitoringAdjustment:
    """Monitoring frequency adjustment recommendation"""
    monitor_id: str
    current_frequency: int  # Current check frequency in minutes
    recommended_frequency: int  # Recommended frequency in minutes
    reason: str  # Why the adjustment is recommended
    risk_level: RiskLevel
    route_risk_level: RouteRiskLevel
    priority: int  # 1-5, with 1 being highest priority
    effective_until: datetime  # When to re-evaluate


class MonitoringFrequencyManager:
    """
    Manages dynamic monitoring frequency adjustments based on risk assessment.
    
    Implements:
    - REQ-1.3: Dynamic monitoring frequency based on disruption risk
    - REQ-1.4: High-risk route detection (>40% delay rate threshold)  
    - REQ-1.6: Performance optimization through intelligent intervals
    """
    
    def __init__(self, monitoring_service: EnhancedFlightMonitoringService = None):
        """Initialize monitoring frequency manager"""
        self.monitoring_service = monitoring_service
        self.risk_detector = DisruptionRiskDetector()
        
        # Configuration
        self.high_risk_delay_threshold = 0.40  # 40% delay rate threshold (REQ-1.4)
        self.interruption_notification_threshold = 30  # 30 minute threshold for interruption alerts
        self.route_stats_cache: Dict[str, RouteDelayStats] = {}
        self.last_stats_update = {}
        
        # Monitoring frequency mappings
        self.frequency_mapping = {
            RiskLevel.CRITICAL: MonitoringFrequency.HIGH_FREQUENCY.value,  # 5 minutes
            RiskLevel.HIGH: MonitoringFrequency.HIGH_FREQUENCY.value,      # 5 minutes  
            RiskLevel.MEDIUM: MonitoringFrequency.DEFAULT_FREQUENCY.value, # 15 minutes
            RiskLevel.LOW: MonitoringFrequency.LOW_FREQUENCY.value         # 30 minutes
        }
        
        # High-risk route frequency override
        self.high_risk_route_frequency = MonitoringFrequency.HIGH_FREQUENCY.value  # 5 minutes
        
        # Statistics
        self.adjustment_stats = {
            "frequency_changes": 0,
            "high_risk_routes_detected": 0,
            "interruption_alerts_sent": 0,
            "performance_optimizations": 0
        }
        
        logger.info("MonitoringFrequencyManager initialized with 40% delay rate threshold")
    
    async def get_route_delay_statistics(self, origin: str, destination: str) -> RouteDelayStats:
        """
        Get historical delay statistics for a route.
        
        REQ-1.4: Calculate delay rate to identify high-risk routes (>40% threshold)
        """
        route_key = f"{origin}-{destination}"
        
        # Check cache first
        if route_key in self.route_stats_cache:
            cached_stats = self.route_stats_cache[route_key]
            # Update cache if older than 24 hours
            if (datetime.now(timezone.utc) - cached_stats.last_updated).hours < 24:
                return cached_stats
        
        # Calculate fresh statistics from database
        db = SessionLocal()
        try:
            # Query historical disruption events for this route
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            
            # Get all bookings for this route in the last 30 days
            route_bookings = db.query(Booking).filter(
                Booking.origin == origin,
                Booking.destination == destination,
                Booking.departure_date >= thirty_days_ago
            ).all()
            
            if not route_bookings:
                # No historical data, return default stats
                return RouteDelayStats(
                    route=route_key,
                    total_flights=0,
                    delayed_flights=0,  
                    delay_rate=0.0,
                    average_delay_minutes=0.0,
                    last_updated=datetime.now(timezone.utc)
                )
            
            total_flights = len(route_bookings)
            delayed_flights = 0
            total_delay_minutes = 0
            
            # Count disruption events (delays) for these bookings
            booking_ids = [b.booking_id for b in route_bookings]
            
            delay_events = db.query(DisruptionEvent).filter(
                DisruptionEvent.booking_id.in_(booking_ids),
                DisruptionEvent.disruption_type.in_(["DELAYED", "CANCELLED", "DIVERTED"]),
                DisruptionEvent.detected_at >= thirty_days_ago
            ).all()
            
            for event in delay_events:
                delayed_flights += 1
                total_delay_minutes += event.delay_minutes or 0
            
            delay_rate = delayed_flights / total_flights if total_flights > 0 else 0.0
            average_delay = total_delay_minutes / delayed_flights if delayed_flights > 0 else 0.0
            
            stats = RouteDelayStats(
                route=route_key,
                total_flights=total_flights,
                delayed_flights=delayed_flights,
                delay_rate=delay_rate,
                average_delay_minutes=average_delay,
                last_updated=datetime.now(timezone.utc)
            )
            
            # Cache the results
            self.route_stats_cache[route_key] = stats
            
            logger.info(f"Route {route_key} delay statistics: {delay_rate:.1%} delay rate ({delayed_flights}/{total_flights})")
            
            return stats
            
        finally:
            db.close()
    
    def classify_route_risk_level(self, delay_stats: RouteDelayStats) -> RouteRiskLevel:
        """
        Classify route risk level based on delay statistics.
        
        REQ-1.4: Routes with >40% delay rate are classified as HIGH_RISK
        """
        if delay_stats.delay_rate > self.high_risk_delay_threshold:  # >40%
            return RouteRiskLevel.HIGH_RISK
        elif delay_stats.delay_rate > 0.20:  # 20-40%
            return RouteRiskLevel.MEDIUM_RISK
        else:  # <20%
            return RouteRiskLevel.LOW_RISK
    
    async def calculate_optimal_frequency(self, monitor: TripMonitor) -> MonitoringAdjustment:
        """
        Calculate optimal monitoring frequency for a trip monitor.
        
        REQ-1.3: Dynamic monitoring frequency based on risk assessment
        REQ-1.4: High-risk route flagging (>40% delay rate) 
        """
        db = SessionLocal()
        try:
            # Get the associated booking
            booking = db.query(Booking).filter(Booking.booking_id == monitor.booking_id).first()
            if not booking:
                logger.warning(f"Booking {monitor.booking_id} not found for monitor {monitor.monitor_id}")
                return None
            
            # Get current frequency
            current_frequency = monitor.check_frequency_minutes
            
            # 1. Assess disruption risk for the booking
            disruption_risk = await detect_disruption_risk(booking.booking_id)
            risk_level = disruption_risk.risk_level if disruption_risk else RiskLevel.LOW
            
            # 2. Get route delay statistics  
            route_stats = await self.get_route_delay_statistics(booking.origin, booking.destination)
            route_risk_level = self.classify_route_risk_level(route_stats)
            
            # 3. Determine recommended frequency
            # Start with risk-based frequency
            recommended_frequency = self.frequency_mapping.get(risk_level, MonitoringFrequency.DEFAULT_FREQUENCY.value)
            
            # Override for high-risk routes (REQ-1.4)
            if route_risk_level == RouteRiskLevel.HIGH_RISK:
                recommended_frequency = self.high_risk_route_frequency
                self.adjustment_stats["high_risk_routes_detected"] += 1
                logger.warning(f"High-risk route detected: {route_stats.route} ({route_stats.delay_rate:.1%} delay rate)")
            
            # 4. Additional frequency adjustments
            priority = 3  # Default priority
            reason_parts = []
            
            # Flight disruption risk factor
            if risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                reason_parts.append(f"High disruption risk ({risk_level.value})")
                priority = 1
            elif risk_level == RiskLevel.MEDIUM:
                reason_parts.append(f"Medium disruption risk")
                priority = 2
            
            # Route historical performance factor
            if route_risk_level == RouteRiskLevel.HIGH_RISK:
                reason_parts.append(f"High-risk route ({route_stats.delay_rate:.1%} delay rate)")
                priority = min(priority, 1)  # Elevate priority
            elif route_risk_level == RouteRiskLevel.MEDIUM_RISK:
                reason_parts.append(f"Medium-risk route ({route_stats.delay_rate:.1%} delay rate)")
                priority = min(priority, 2)
            
            # Departure time proximity factor
            time_until_departure = (booking.departure_date - datetime.now(timezone.utc)).total_seconds() / 3600
            if time_until_departure <= 4:  # Less than 4 hours
                recommended_frequency = min(recommended_frequency, MonitoringFrequency.HIGH_FREQUENCY.value)
                reason_parts.append("Departure within 4 hours")
                priority = min(priority, 1)
            elif time_until_departure <= 24:  # Less than 24 hours
                recommended_frequency = min(recommended_frequency, MonitoringFrequency.DEFAULT_FREQUENCY.value)
                reason_parts.append("Departure within 24 hours")
            
            # Create the final reason string
            reason = "; ".join(reason_parts) if reason_parts else "Standard monitoring frequency"
            
            # Set effective period (when to re-evaluate)
            if priority == 1:
                effective_until = datetime.now(timezone.utc) + timedelta(hours=2)  # Re-evaluate in 2 hours
            elif priority == 2:
                effective_until = datetime.now(timezone.utc) + timedelta(hours=6)  # Re-evaluate in 6 hours  
            else:
                effective_until = datetime.now(timezone.utc) + timedelta(hours=12)  # Re-evaluate in 12 hours
            
            adjustment = MonitoringAdjustment(
                monitor_id=monitor.monitor_id,
                current_frequency=current_frequency,
                recommended_frequency=recommended_frequency,
                reason=reason,
                risk_level=risk_level,
                route_risk_level=route_risk_level,
                priority=priority,
                effective_until=effective_until
            )
            
            return adjustment
            
        finally:
            db.close()
    
    async def apply_frequency_adjustment(self, adjustment: MonitoringAdjustment) -> bool:
        """
        Apply frequency adjustment to a trip monitor.
        
        Returns True if adjustment was successfully applied.
        """
        if adjustment.current_frequency == adjustment.recommended_frequency:
            logger.debug(f"Monitor {adjustment.monitor_id} already has optimal frequency ({adjustment.recommended_frequency}min)")
            return False
        
        db = SessionLocal()
        try:
            monitor = db.query(TripMonitor).filter(TripMonitor.monitor_id == adjustment.monitor_id).first()
            if not monitor:
                logger.error(f"Monitor {adjustment.monitor_id} not found")
                return False
            
            old_frequency = monitor.check_frequency_minutes
            monitor.check_frequency_minutes = adjustment.recommended_frequency
            monitor.updated_at = datetime.now(timezone.utc)
            
            # Add adjustment reason to notes
            adjustment_note = f"[{datetime.now(timezone.utc).strftime('%m/%d %H:%M')}] Frequency adjusted: {old_frequency}min → {adjustment.recommended_frequency}min. Reason: {adjustment.reason}"
            
            if monitor.notes:
                monitor.notes += f"\n{adjustment_note}"
            else:
                monitor.notes = adjustment_note
            
            db.commit()
            
            self.adjustment_stats["frequency_changes"] += 1
            logger.info(f"Monitor {adjustment.monitor_id} frequency adjusted: {old_frequency}min → {adjustment.recommended_frequency}min ({adjustment.reason})")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying frequency adjustment to monitor {adjustment.monitor_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    async def check_monitoring_interruptions(self) -> List[str]:
        """
        Check for monitoring interruptions and send notifications.
        
        REQ-1.3: Monitoring interruption notifications (30min threshold)
        Returns list of alert IDs created.
        """
        alert_ids = []
        interruption_threshold_minutes = self.interruption_notification_threshold
        threshold_time = datetime.now(timezone.utc) - timedelta(minutes=interruption_threshold_minutes)
        
        db = SessionLocal()
        try:
            # Find active monitors that haven't been checked in >30 minutes
            interrupted_monitors = db.query(TripMonitor).filter(
                TripMonitor.is_active == True,
                TripMonitor.last_check < threshold_time,
                TripMonitor.last_check.isnot(None)  # Must have been checked at least once
            ).all()
            
            logger.info(f"Found {len(interrupted_monitors)} monitors with interruptions >{interruption_threshold_minutes}min")
            
            for monitor in interrupted_monitors:
                try:
                    # Get booking and user details
                    booking = db.query(Booking).filter(Booking.booking_id == monitor.booking_id).first()
                    if not booking:
                        continue
                        
                    user = db.query(User).filter(User.user_id == monitor.user_id).first()
                    if not user:
                        continue
                    
                    # Calculate interruption duration
                    interruption_minutes = (datetime.now(timezone.utc) - monitor.last_check).total_seconds() / 60
                    
                    # Create interruption alert
                    alert_message = (
                        f"MONITORING INTERRUPTION: Flight {booking.flight_number} monitoring "
                        f"has been interrupted for {interruption_minutes:.0f} minutes. "
                        f"Last check: {monitor.last_check.strftime('%H:%M:%S UTC')}. "
                        f"Please verify flight status manually."
                    )
                    
                    # Determine alert severity based on interruption duration
                    if interruption_minutes >= 120:  # 2+ hours
                        risk_severity = "CRITICAL"
                        urgency_score = 95
                    elif interruption_minutes >= 60:  # 1-2 hours  
                        risk_severity = "HIGH"
                        urgency_score = 80
                    else:  # 30min - 1 hour
                        risk_severity = "MEDIUM"
                        urgency_score = 60
                    
                    # Create disruption alert
                    alert_data = {
                        "alert_type": "EMAIL",  # Default to email
                        "risk_severity": risk_severity,
                        "alert_message": alert_message,
                        "urgency_score": urgency_score,
                        "alert_metadata": {
                            "interruption_type": "monitoring_gap",
                            "interruption_minutes": interruption_minutes,
                            "last_check": monitor.last_check.isoformat(),
                            "monitor_id": monitor.monitor_id,
                            "flight_number": booking.flight_number,
                            "route": f"{booking.origin}-{booking.destination}"
                        },
                        "expires_at": datetime.now(timezone.utc) + timedelta(hours=6)
                    }
                    
                    # Create a dummy disruption event if none exists for this booking
                    existing_event = db.query(DisruptionEvent).filter(
                        DisruptionEvent.booking_id == booking.booking_id
                    ).first()
                    
                    if not existing_event:
                        from ..models import create_disruption_event
                        disruption_data = {
                            "type": "MONITORING_INTERRUPTION",
                            "original_departure": booking.departure_date,
                            "delay_minutes": 0,
                            "reason": f"Monitoring interrupted for {interruption_minutes:.0f} minutes"
                        }
                        existing_event = create_disruption_event(booking.booking_id, disruption_data)
                    
                    alert = create_disruption_alert(existing_event.event_id, user.user_id, alert_data)
                    alert_ids.append(alert.alert_id)
                    
                    self.adjustment_stats["interruption_alerts_sent"] += 1
                    
                    logger.warning(
                        f"Monitoring interruption alert created for user {user.email}, "
                        f"flight {booking.flight_number}: {interruption_minutes:.0f}min gap"
                    )
                    
                except Exception as e:
                    logger.error(f"Error creating interruption alert for monitor {monitor.monitor_id}: {e}")
                    continue
            
        finally:
            db.close()
        
        return alert_ids
    
    async def optimize_monitoring_performance(self) -> Dict[str, int]:
        """
        Perform monitoring performance optimizations.
        
        REQ-1.6: Performance optimization through intelligent polling
        Returns statistics about optimizations performed.
        """
        optimization_stats = {
            "monitors_optimized": 0,
            "frequency_increases": 0,
            "frequency_decreases": 0,
            "performance_gained_minutes": 0
        }
        
        db = SessionLocal()
        try:
            # Get all active monitors
            active_monitors = db.query(TripMonitor).filter(TripMonitor.is_active == True).all()
            
            for monitor in active_monitors:
                # Calculate optimal frequency
                adjustment = await self.calculate_optimal_frequency(monitor)
                if not adjustment:
                    continue
                
                # Apply optimization if beneficial
                if adjustment.recommended_frequency != adjustment.current_frequency:
                    success = await self.apply_frequency_adjustment(adjustment)
                    if success:
                        optimization_stats["monitors_optimized"] += 1
                        
                        if adjustment.recommended_frequency < adjustment.current_frequency:
                            optimization_stats["frequency_increases"] += 1
                            # More frequent monitoring
                        else:
                            optimization_stats["frequency_decreases"] += 1
                            # Less frequent monitoring saves resources
                            minutes_saved = adjustment.recommended_frequency - adjustment.current_frequency
                            optimization_stats["performance_gained_minutes"] += minutes_saved
            
            self.adjustment_stats["performance_optimizations"] += optimization_stats["monitors_optimized"]
            
        finally:
            db.close()
        
        logger.info(f"Performance optimization completed: {optimization_stats}")
        return optimization_stats
    
    async def run_monitoring_adjustment_cycle(self) -> Dict[str, any]:
        """
        Run a complete monitoring adjustment cycle.
        
        This method should be called periodically to:
        1. Check for monitoring interruptions
        2. Optimize monitoring frequencies
        3. Update route risk classifications
        
        Returns summary of actions taken.
        """
        cycle_start = datetime.now(timezone.utc)
        
        try:
            # 1. Check for monitoring interruptions
            interruption_alerts = await self.check_monitoring_interruptions()
            
            # 2. Optimize monitoring performance  
            optimization_stats = await self.optimize_monitoring_performance()
            
            # 3. Update route statistics cache
            await self._update_route_statistics_cache()
            
            cycle_duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            
            summary = {
                "cycle_completed_at": cycle_start.isoformat(),
                "cycle_duration_seconds": cycle_duration,
                "interruption_alerts_created": len(interruption_alerts),
                "monitors_optimized": optimization_stats["monitors_optimized"],
                "frequency_adjustments": {
                    "increases": optimization_stats["frequency_increases"],
                    "decreases": optimization_stats["frequency_decreases"]
                },
                "performance_gained_minutes": optimization_stats["performance_gained_minutes"],
                "alert_ids": interruption_alerts,
                "statistics": self.adjustment_stats.copy()
            }
            
            logger.info(f"Monitoring adjustment cycle completed in {cycle_duration:.1f}s: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"Error in monitoring adjustment cycle: {e}")
            return {"error": str(e), "cycle_completed_at": cycle_start.isoformat()}
    
    async def _update_route_statistics_cache(self):
        """Update route statistics cache for commonly used routes"""
        # Get most common routes from recent bookings
        db = SessionLocal()
        try:
            recent_date = datetime.now(timezone.utc) - timedelta(days=7)
            
            # Find most common origin-destination pairs
            route_counts = {}
            recent_bookings = db.query(Booking).filter(
                Booking.departure_date >= recent_date
            ).all()
            
            for booking in recent_bookings:
                route = f"{booking.origin}-{booking.destination}"
                route_counts[route] = route_counts.get(route, 0) + 1
            
            # Update cache for top 20 most common routes
            top_routes = sorted(route_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            
            for route, count in top_routes:
                origin, destination = route.split('-')
                await self.get_route_delay_statistics(origin, destination)
                
            logger.debug(f"Updated route statistics cache for {len(top_routes)} routes")
            
        finally:
            db.close()
    
    def get_adjustment_statistics(self) -> Dict[str, any]:
        """Get monitoring adjustment statistics"""
        return {
            "adjustment_stats": self.adjustment_stats.copy(),
            "cache_stats": {
                "cached_routes": len(self.route_stats_cache),
                "high_risk_routes": len([
                    route for route, stats in self.route_stats_cache.items()
                    if stats.delay_rate > self.high_risk_delay_threshold
                ])
            },
            "configuration": {
                "high_risk_delay_threshold": self.high_risk_delay_threshold,
                "interruption_notification_threshold": self.interruption_notification_threshold,
                "frequency_mapping": {k.value: v for k, v in self.frequency_mapping.items()}
            }
        }


# Standalone function for easy integration
async def run_monitoring_frequency_adjustment(monitoring_service: EnhancedFlightMonitoringService = None) -> Dict[str, any]:
    """
    Run monitoring frequency adjustment as a standalone operation.
    
    Args:
        monitoring_service: Optional monitoring service instance
        
    Returns:
        Summary of adjustment cycle results
    """
    manager = MonitoringFrequencyManager(monitoring_service)
    return await manager.run_monitoring_adjustment_cycle()


if __name__ == "__main__":
    # Run standalone monitoring frequency adjustment
    asyncio.run(run_monitoring_frequency_adjustment())
# tests/flight_agent/test_monitoring_frequency_manager.py
"""
Tests for Monitoring Frequency Adjustment Manager
Task 2.3: Implement monitoring frequency adjustment

Test coverage for:
- Dynamic polling frequency (15min default, 5min high-risk)
- High-risk route flagging based on historical data (>40% delay rate)
- Monitoring interruption notifications (30min threshold)
- REQ-1.3, REQ-1.4, REQ-1.6 compliance
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock

from flight_agent.services.monitoring_frequency_manager import (
    MonitoringFrequencyManager,
    MonitoringFrequency,
    RouteRiskLevel,
    RouteDelayStats,
    MonitoringAdjustment,
    run_monitoring_frequency_adjustment
)
from flight_agent.services.enhanced_flight_monitoring_service import EnhancedFlightMonitoringService
from flight_agent.services.disruption_risk_detector import RiskLevel, DisruptionRisk
from flight_agent.models import (
    SessionLocal, Booking, TripMonitor, DisruptionEvent, DisruptionAlert,
    User, create_user, create_booking, create_trip_monitor, create_disruption_event
)


class TestMonitoringFrequencyManager:
    """Test MonitoringFrequencyManager core functionality"""
    
    @pytest.fixture
    def manager(self):
        """Create MonitoringFrequencyManager instance"""
        mock_monitoring_service = Mock(spec=EnhancedFlightMonitoringService)
        return MonitoringFrequencyManager(mock_monitoring_service)
    
    @pytest.fixture
    def test_user(self):
        """Create test user"""
        return create_user("frequency_test@example.com", "+1234567890")
    
    @pytest.fixture
    def test_booking(self, test_user):
        """Create test booking"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        booking_data = {
            "pnr": "FREQ123",
            "airline": "AA",
            "flight_number": "AA123",
            "departure_date": departure_date,
            "origin": "JFK",
            "destination": "LAX"
        }
        return create_booking(test_user.user_id, booking_data)
    
    @pytest.fixture
    def test_monitor(self, test_user, test_booking):
        """Create test trip monitor with default 15min frequency"""
        monitor_data = {
            "check_frequency_minutes": 15,  # Default frequency
            "expires_at": datetime.now(timezone.utc) + timedelta(days=2)
        }
        return create_trip_monitor(test_user.user_id, test_booking.booking_id, "flight_123", monitor_data)
    
    def test_manager_initialization(self, manager):
        """Test manager initializes with correct parameters"""
        assert manager.high_risk_delay_threshold == 0.40  # 40% threshold (REQ-1.4)
        assert manager.interruption_notification_threshold == 30  # 30 minute threshold
        assert manager.high_risk_route_frequency == MonitoringFrequency.HIGH_FREQUENCY.value  # 5 minutes
        
        # Verify frequency mappings
        assert manager.frequency_mapping[RiskLevel.CRITICAL] == 5
        assert manager.frequency_mapping[RiskLevel.HIGH] == 5
        assert manager.frequency_mapping[RiskLevel.MEDIUM] == 15
        assert manager.frequency_mapping[RiskLevel.LOW] == 30
    
    @pytest.mark.asyncio
    async def test_get_route_delay_statistics_no_data(self, manager):
        """Test route delay statistics with no historical data"""
        stats = await manager.get_route_delay_statistics("TEST", "DEST")
        
        assert stats.route == "TEST-DEST"
        assert stats.total_flights == 0
        assert stats.delayed_flights == 0
        assert stats.delay_rate == 0.0
        assert stats.average_delay_minutes == 0.0
    
    @pytest.mark.asyncio
    async def test_get_route_delay_statistics_with_data(self, manager, test_user):
        """Test route delay statistics calculation with actual data"""
        # Create historical bookings with disruptions
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=15)  # Within 30 day window
        
        # Create 5 bookings for the same route
        bookings = []
        for i in range(5):
            booking_data = {
                "pnr": f"HIST{i}",
                "airline": "AA",
                "flight_number": f"AA{100+i}",
                "departure_date": thirty_days_ago + timedelta(days=i),
                "origin": "ORD",
                "destination": "DFW"
            }
            booking = create_booking(test_user.user_id, booking_data)
            bookings.append(booking)
        
        # Create disruption events for 3 out of 5 flights (60% delay rate)
        for i in range(3):
            disruption_data = {
                "type": "DELAYED",
                "original_departure": bookings[i].departure_date,
                "delay_minutes": 45 + (i * 15),  # Varying delay times
                "reason": f"Test delay {i+1}"
            }
            create_disruption_event(bookings[i].booking_id, disruption_data)
        
        # Test statistics calculation
        stats = await manager.get_route_delay_statistics("ORD", "DFW")
        
        assert stats.route == "ORD-DFW"
        assert stats.total_flights == 5
        assert stats.delayed_flights == 3
        assert stats.delay_rate == 0.6  # 60% delay rate
        assert stats.average_delay_minutes == (45 + 60 + 75) / 3  # Average of the delays
    
    def test_classify_route_risk_level(self, manager):
        """Test route risk level classification based on delay rate"""
        # High risk: >40% delay rate (REQ-1.4)
        high_risk_stats = RouteDelayStats("HIGH-RISK", 100, 50, 0.50, 60.0, datetime.now(timezone.utc))
        assert manager.classify_route_risk_level(high_risk_stats) == RouteRiskLevel.HIGH_RISK
        
        # Exactly 40% should still be medium risk
        threshold_stats = RouteDelayStats("THRESHOLD", 100, 40, 0.40, 45.0, datetime.now(timezone.utc))
        assert manager.classify_route_risk_level(threshold_stats) == RouteRiskLevel.MEDIUM_RISK
        
        # Medium risk: 20-40% delay rate
        medium_risk_stats = RouteDelayStats("MED-RISK", 100, 30, 0.30, 30.0, datetime.now(timezone.utc))
        assert manager.classify_route_risk_level(medium_risk_stats) == RouteRiskLevel.MEDIUM_RISK
        
        # Low risk: <20% delay rate
        low_risk_stats = RouteDelayStats("LOW-RISK", 100, 10, 0.10, 15.0, datetime.now(timezone.utc))
        assert manager.classify_route_risk_level(low_risk_stats) == RouteRiskLevel.LOW_RISK
    
    @pytest.mark.asyncio
    @patch('flight_agent.services.monitoring_frequency_manager.detect_disruption_risk')
    async def test_calculate_optimal_frequency_high_risk(self, mock_risk_detect, manager, test_monitor):
        """Test optimal frequency calculation for high-risk scenarios"""
        # Mock high-risk disruption assessment
        mock_risk = Mock()
        mock_risk.risk_level = RiskLevel.HIGH
        mock_risk_detect.return_value = mock_risk
        
        # Mock high-risk route statistics (>40% delay rate)
        manager.get_route_delay_statistics = AsyncMock(return_value=RouteDelayStats(
            "JFK-LAX", 100, 45, 0.45, 60.0, datetime.now(timezone.utc)  # 45% delay rate
        ))
        
        adjustment = await manager.calculate_optimal_frequency(test_monitor)
        
        assert adjustment is not None
        assert adjustment.monitor_id == test_monitor.monitor_id
        assert adjustment.recommended_frequency == 5  # High-risk frequency
        assert adjustment.risk_level == RiskLevel.HIGH
        assert adjustment.route_risk_level == RouteRiskLevel.HIGH_RISK
        assert adjustment.priority == 1  # Highest priority
        assert "High disruption risk" in adjustment.reason
        assert "High-risk route" in adjustment.reason
    
    @pytest.mark.asyncio
    @patch('flight_agent.services.monitoring_frequency_manager.detect_disruption_risk')
    async def test_calculate_optimal_frequency_low_risk(self, mock_risk_detect, manager, test_monitor):
        """Test optimal frequency calculation for low-risk scenarios"""
        # Mock low-risk disruption assessment
        mock_risk = Mock()
        mock_risk.risk_level = RiskLevel.LOW
        mock_risk_detect.return_value = mock_risk
        
        # Mock low-risk route statistics (<20% delay rate)
        manager.get_route_delay_statistics = AsyncMock(return_value=RouteDelayStats(
            "JFK-LAX", 100, 10, 0.10, 20.0, datetime.now(timezone.utc)  # 10% delay rate
        ))
        
        adjustment = await manager.calculate_optimal_frequency(test_monitor)
        
        assert adjustment is not None
        assert adjustment.recommended_frequency == 30  # Low-risk frequency (30 min)
        assert adjustment.risk_level == RiskLevel.LOW
        assert adjustment.route_risk_level == RouteRiskLevel.LOW_RISK
        assert adjustment.priority == 3  # Lower priority
    
    @pytest.mark.asyncio
    @patch('flight_agent.services.monitoring_frequency_manager.detect_disruption_risk')
    async def test_calculate_optimal_frequency_departure_proximity(self, mock_risk_detect, manager, test_user):
        """Test frequency adjustment based on departure time proximity"""
        # Create booking departing in 2 hours (should trigger high frequency)
        near_departure = datetime.now(timezone.utc) + timedelta(hours=2)
        booking_data = {
            "pnr": "NEAR123",
            "airline": "AA", 
            "flight_number": "AA999",
            "departure_date": near_departure,
            "origin": "JFK",
            "destination": "LAX"
        }
        booking = create_booking(test_user.user_id, booking_data)
        
        monitor_data = {"check_frequency_minutes": 15}
        monitor = create_trip_monitor(test_user.user_id, booking.booking_id, "flight_999", monitor_data)
        
        # Mock medium risk
        mock_risk = Mock()
        mock_risk.risk_level = RiskLevel.MEDIUM
        mock_risk_detect.return_value = mock_risk
        
        # Mock low-risk route
        manager.get_route_delay_statistics = AsyncMock(return_value=RouteDelayStats(
            "JFK-LAX", 100, 15, 0.15, 25.0, datetime.now(timezone.utc)  # 15% delay rate
        ))
        
        adjustment = await manager.calculate_optimal_frequency(monitor)
        
        assert adjustment.recommended_frequency == 5  # Should be 5 min due to proximity
        assert "Departure within 4 hours" in adjustment.reason
        assert adjustment.priority == 1  # High priority due to proximity
    
    @pytest.mark.asyncio
    async def test_apply_frequency_adjustment(self, manager, test_monitor):
        """Test applying frequency adjustment to a monitor"""
        # Create adjustment that changes frequency
        adjustment = MonitoringAdjustment(
            monitor_id=test_monitor.monitor_id,
            current_frequency=15,
            recommended_frequency=5,
            reason="High risk detected",
            risk_level=RiskLevel.HIGH,
            route_risk_level=RouteRiskLevel.HIGH_RISK,
            priority=1,
            effective_until=datetime.now(timezone.utc) + timedelta(hours=2)
        )
        
        success = await manager.apply_frequency_adjustment(adjustment)
        assert success
        
        # Verify database was updated
        db = SessionLocal()
        try:
            updated_monitor = db.query(TripMonitor).filter(TripMonitor.monitor_id == test_monitor.monitor_id).first()
            assert updated_monitor.check_frequency_minutes == 5
            assert "Frequency adjusted: 15min → 5min" in updated_monitor.notes
        finally:
            db.close()
        
        # Verify statistics were updated
        assert manager.adjustment_stats["frequency_changes"] == 1
    
    @pytest.mark.asyncio
    async def test_apply_frequency_adjustment_no_change(self, manager, test_monitor):
        """Test applying adjustment when no change is needed"""
        # Create adjustment with same frequency
        adjustment = MonitoringAdjustment(
            monitor_id=test_monitor.monitor_id,
            current_frequency=15,
            recommended_frequency=15,  # Same as current
            reason="Already optimal",
            risk_level=RiskLevel.MEDIUM,
            route_risk_level=RouteRiskLevel.MEDIUM_RISK,
            priority=2,
            effective_until=datetime.now(timezone.utc) + timedelta(hours=6)
        )
        
        success = await manager.apply_frequency_adjustment(adjustment)
        assert not success  # Should return False when no change needed
        assert manager.adjustment_stats["frequency_changes"] == 0
    
    @pytest.mark.asyncio
    async def test_check_monitoring_interruptions(self, manager, test_user, test_booking):
        """Test monitoring interruption detection and notification (REQ-1.3)"""
        # Create monitor with last check >30 minutes ago
        interruption_time = datetime.now(timezone.utc) - timedelta(minutes=45)
        
        monitor_data = {
            "check_frequency_minutes": 15,
            "last_check": interruption_time,  # 45 minutes ago
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1)
        }
        
        interrupted_monitor = create_trip_monitor(
            test_user.user_id, 
            test_booking.booking_id, 
            "interrupted_flight", 
            monitor_data
        )
        
        # Set the last_check explicitly in database
        db = SessionLocal()
        try:
            monitor_record = db.query(TripMonitor).filter(TripMonitor.monitor_id == interrupted_monitor.monitor_id).first()
            monitor_record.last_check = interruption_time
            db.commit()
        finally:
            db.close()
        
        alert_ids = await manager.check_monitoring_interruptions()
        
        assert len(alert_ids) > 0
        assert manager.adjustment_stats["interruption_alerts_sent"] > 0
        
        # Verify alert was created with correct details
        db = SessionLocal()
        try:
            alert = db.query(DisruptionAlert).filter(DisruptionAlert.alert_id == alert_ids[0]).first()
            assert alert is not None
            assert "MONITORING INTERRUPTION" in alert.alert_message
            assert "45 minutes" in alert.alert_message
            assert alert.risk_severity == "MEDIUM"  # 30-60 min interruption
        finally:
            db.close()
    
    @pytest.mark.asyncio
    async def test_check_monitoring_interruptions_critical(self, manager, test_user, test_booking):
        """Test critical monitoring interruption (>2 hours)"""
        # Create monitor with last check >2 hours ago
        critical_interruption_time = datetime.now(timezone.utc) - timedelta(hours=3)
        
        monitor_data = {
            "check_frequency_minutes": 15,
            "last_check": critical_interruption_time,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1)
        }
        
        interrupted_monitor = create_trip_monitor(
            test_user.user_id,
            test_booking.booking_id,
            "critical_interrupted_flight",
            monitor_data
        )
        
        # Set the last_check in database
        db = SessionLocal()
        try:
            monitor_record = db.query(TripMonitor).filter(TripMonitor.monitor_id == interrupted_monitor.monitor_id).first()
            monitor_record.last_check = critical_interruption_time
            db.commit()
        finally:
            db.close()
        
        alert_ids = await manager.check_monitoring_interruptions()
        
        assert len(alert_ids) > 0
        
        # Verify alert severity is CRITICAL
        db = SessionLocal()
        try:
            alert = db.query(DisruptionAlert).filter(DisruptionAlert.alert_id == alert_ids[0]).first()
            assert alert.risk_severity == "CRITICAL"
            assert alert.urgency_score == 95
        finally:
            db.close()
    
    @pytest.mark.asyncio
    async def test_optimize_monitoring_performance(self, manager):
        """Test monitoring performance optimization (REQ-1.6)"""
        # This is a comprehensive test that would need multiple monitors
        # For now, test that the method executes without error
        optimization_stats = await manager.optimize_monitoring_performance()
        
        assert isinstance(optimization_stats, dict)
        assert "monitors_optimized" in optimization_stats
        assert "frequency_increases" in optimization_stats
        assert "frequency_decreases" in optimization_stats
        assert "performance_gained_minutes" in optimization_stats
    
    @pytest.mark.asyncio
    async def test_run_monitoring_adjustment_cycle(self, manager):
        """Test complete monitoring adjustment cycle"""
        # Mock the sub-methods to avoid complex database setup
        manager.check_monitoring_interruptions = AsyncMock(return_value=["alert_123"])
        manager.optimize_monitoring_performance = AsyncMock(return_value={
            "monitors_optimized": 3,
            "frequency_increases": 1,
            "frequency_decreases": 2,
            "performance_gained_minutes": 30
        })
        manager._update_route_statistics_cache = AsyncMock()
        
        summary = await manager.run_monitoring_adjustment_cycle()
        
        assert "cycle_completed_at" in summary
        assert "cycle_duration_seconds" in summary
        assert summary["interruption_alerts_created"] == 1
        assert summary["monitors_optimized"] == 3
        assert summary["performance_gained_minutes"] == 30
        assert "alert_123" in summary["alert_ids"]
    
    def test_get_adjustment_statistics(self, manager):
        """Test getting adjustment statistics"""
        # Set some test statistics
        manager.adjustment_stats["frequency_changes"] = 5
        manager.adjustment_stats["high_risk_routes_detected"] = 2
        manager.route_stats_cache["JFK-LAX"] = RouteDelayStats(
            "JFK-LAX", 100, 45, 0.45, 60.0, datetime.now(timezone.utc)
        )
        
        stats = manager.get_adjustment_statistics()
        
        assert stats["adjustment_stats"]["frequency_changes"] == 5
        assert stats["adjustment_stats"]["high_risk_routes_detected"] == 2
        assert stats["cache_stats"]["cached_routes"] == 1
        assert stats["cache_stats"]["high_risk_routes"] == 1  # JFK-LAX has 45% delay rate
        assert stats["configuration"]["high_risk_delay_threshold"] == 0.40


class TestMonitoringFrequencyIntegration:
    """Integration tests for monitoring frequency management"""
    
    @pytest.fixture
    def test_user(self):
        """Create test user for integration tests"""
        return create_user("integration_freq@example.com", "+1555000987")
    
    @pytest.mark.asyncio
    async def test_high_risk_route_detection_integration(self, test_user):
        """Test end-to-end high-risk route detection (REQ-1.4)"""
        manager = MonitoringFrequencyManager()
        
        # Create route with >40% delay rate
        route_origin = "ORD"
        route_destination = "BOS"  # Weather-prone route
        
        # Create historical data: 10 flights, 5 delayed (50% delay rate)
        historical_date = datetime.now(timezone.utc) - timedelta(days=10)
        bookings = []
        
        for i in range(10):
            booking_data = {
                "pnr": f"HISTORD{i}",
                "airline": "AA",
                "flight_number": f"AA{200+i}",
                "departure_date": historical_date + timedelta(hours=i*6),
                "origin": route_origin,
                "destination": route_destination
            }
            booking = create_booking(test_user.user_id, booking_data)
            bookings.append(booking)
        
        # Create disruption events for 5 flights (50% delay rate)
        for i in range(5):
            disruption_data = {
                "type": "DELAYED",
                "original_departure": bookings[i].departure_date,
                "delay_minutes": 60 + (i * 10),
                "reason": f"Weather delay {i+1}"
            }
            create_disruption_event(bookings[i].booking_id, disruption_data)
        
        # Test route statistics calculation
        stats = await manager.get_route_delay_statistics(route_origin, route_destination)
        assert stats.delay_rate == 0.5  # 50% delay rate
        
        # Test route risk classification
        risk_level = manager.classify_route_risk_level(stats)
        assert risk_level == RouteRiskLevel.HIGH_RISK  # >40% threshold
        
        # Create new monitor for this route
        new_departure = datetime.now(timezone.utc) + timedelta(days=1)
        new_booking_data = {
            "pnr": "NEWTRIP789",
            "airline": "AA",
            "flight_number": "AA789",
            "departure_date": new_departure,
            "origin": route_origin,
            "destination": route_destination
        }
        new_booking = create_booking(test_user.user_id, new_booking_data)
        
        monitor_data = {"check_frequency_minutes": 15}  # Default frequency
        monitor = create_trip_monitor(test_user.user_id, new_booking.booking_id, "flight_789", monitor_data)
        
        # Calculate optimal frequency
        with patch('flight_agent.services.monitoring_frequency_manager.detect_disruption_risk') as mock_risk:
            mock_risk.return_value = Mock(risk_level=RiskLevel.MEDIUM)
            
            adjustment = await manager.calculate_optimal_frequency(monitor)
            
            # Should recommend high frequency (5min) due to high-risk route
            assert adjustment.recommended_frequency == 5
            assert adjustment.route_risk_level == RouteRiskLevel.HIGH_RISK
            assert "High-risk route (50.0% delay rate)" in adjustment.reason
    
    @pytest.mark.asyncio  
    async def test_monitoring_interruption_workflow(self, test_user):
        """Test complete monitoring interruption workflow"""
        manager = MonitoringFrequencyManager()
        
        # Create booking and monitor
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        booking_data = {
            "pnr": "INTERRUPT123",
            "airline": "DL",
            "flight_number": "DL456", 
            "departure_date": departure_date,
            "origin": "ATL",
            "destination": "SEA"
        }
        booking = create_booking(test_user.user_id, booking_data)
        
        monitor_data = {
            "check_frequency_minutes": 10,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=2)
        }
        monitor = create_trip_monitor(test_user.user_id, booking.booking_id, "flight_456", monitor_data)
        
        # Simulate monitoring interruption by setting last_check to >30 minutes ago
        interruption_time = datetime.now(timezone.utc) - timedelta(minutes=35)
        
        db = SessionLocal()
        try:
            monitor_record = db.query(TripMonitor).filter(TripMonitor.monitor_id == monitor.monitor_id).first()
            monitor_record.last_check = interruption_time
            db.commit()
        finally:
            db.close()
        
        # Run interruption check
        alert_ids = await manager.check_monitoring_interruptions()
        
        assert len(alert_ids) > 0
        
        # Verify alert was created correctly
        db = SessionLocal()
        try:
            alert = db.query(DisruptionAlert).filter(DisruptionAlert.alert_id == alert_ids[0]).first()
            assert alert is not None
            assert alert.user_id == test_user.user_id
            assert "MONITORING INTERRUPTION" in alert.alert_message
            assert "35 minutes" in alert.alert_message
            assert alert.alert_metadata["interruption_type"] == "monitoring_gap"
            assert alert.alert_metadata["flight_number"] == "DL456"
            assert alert.alert_metadata["route"] == "ATL-SEA"
        finally:
            db.close()
    
    @pytest.mark.asyncio
    async def test_performance_optimization_integration(self, test_user):
        """Test performance optimization with real monitors"""
        manager = MonitoringFrequencyManager()
        
        # Create multiple monitors with different risk profiles
        monitors = []
        bookings = []
        
        # High-risk scenario (should get 5min frequency)
        high_risk_booking_data = {
            "pnr": "HIGH123",
            "airline": "NK",  # Budget carrier
            "flight_number": "NK123",
            "departure_date": datetime.now(timezone.utc) + timedelta(hours=2),  # Soon
            "origin": "LGA",  # Congested
            "destination": "ORD"  # Weather-prone
        }
        high_risk_booking = create_booking(test_user.user_id, high_risk_booking_data)
        bookings.append(high_risk_booking)
        
        high_risk_monitor = create_trip_monitor(
            test_user.user_id, 
            high_risk_booking.booking_id, 
            "high_risk_flight",
            {"check_frequency_minutes": 15}  # Will be optimized to 5
        )
        monitors.append(high_risk_monitor)
        
        # Low-risk scenario (should get 30min frequency)
        low_risk_booking_data = {
            "pnr": "LOW456",
            "airline": "DL",  # Reliable carrier
            "flight_number": "DL456",
            "departure_date": datetime.now(timezone.utc) + timedelta(days=5),  # Far future
            "origin": "ATL",  # DL hub
            "destination": "MSP"  # Less congested
        }
        low_risk_booking = create_booking(test_user.user_id, low_risk_booking_data)
        bookings.append(low_risk_booking)
        
        low_risk_monitor = create_trip_monitor(
            test_user.user_id,
            low_risk_booking.booking_id,
            "low_risk_flight", 
            {"check_frequency_minutes": 15}  # Will be optimized to 30
        )
        monitors.append(low_risk_monitor)
        
        # Mock risk detection to return appropriate risk levels
        with patch('flight_agent.services.monitoring_frequency_manager.detect_disruption_risk') as mock_risk:
            def risk_side_effect(booking_id):
                if booking_id == high_risk_booking.booking_id:
                    return Mock(risk_level=RiskLevel.HIGH)
                else:
                    return Mock(risk_level=RiskLevel.LOW)
            
            mock_risk.side_effect = risk_side_effect
            
            # Run performance optimization
            optimization_stats = await manager.optimize_monitoring_performance()
            
            assert optimization_stats["monitors_optimized"] >= 2
            assert optimization_stats["frequency_increases"] >= 1  # High-risk monitor
            assert optimization_stats["frequency_decreases"] >= 1  # Low-risk monitor
        
        # Verify frequency changes were applied
        db = SessionLocal()
        try:
            updated_high_risk = db.query(TripMonitor).filter(TripMonitor.monitor_id == high_risk_monitor.monitor_id).first()
            updated_low_risk = db.query(TripMonitor).filter(TripMonitor.monitor_id == low_risk_monitor.monitor_id).first()
            
            # High-risk should have increased frequency (lower number = more frequent)
            assert updated_high_risk.check_frequency_minutes <= 15
            
            # Low-risk should have decreased frequency (higher number = less frequent)
            assert updated_low_risk.check_frequency_minutes >= 15
        finally:
            db.close()


class TestRequirementsCompliance:
    """Test compliance with specific requirements"""
    
    def test_req_1_3_dynamic_frequency_implementation(self):
        """Test REQ-1.3: Dynamic monitoring frequency based on risk"""
        manager = MonitoringFrequencyManager()
        
        # Verify frequency mappings meet requirements
        assert manager.frequency_mapping[RiskLevel.CRITICAL] == 5  # High frequency
        assert manager.frequency_mapping[RiskLevel.HIGH] == 5     # High frequency
        assert manager.frequency_mapping[RiskLevel.MEDIUM] == 15  # Default frequency 
        assert manager.frequency_mapping[RiskLevel.LOW] == 30     # Low frequency
        
        # Verify interruption notification threshold
        assert manager.interruption_notification_threshold == 30  # 30 minute threshold
    
    def test_req_1_4_high_risk_route_threshold(self):
        """Test REQ-1.4: High-risk route flagging (>40% delay rate threshold)"""
        manager = MonitoringFrequencyManager()
        
        # Verify 40% threshold is correctly configured
        assert manager.high_risk_delay_threshold == 0.40
        
        # Test threshold boundary conditions
        high_risk_stats = RouteDelayStats("TEST", 100, 41, 0.41, 60.0, datetime.now(timezone.utc))
        medium_risk_stats = RouteDelayStats("TEST", 100, 40, 0.40, 60.0, datetime.now(timezone.utc))
        low_risk_stats = RouteDelayStats("TEST", 100, 39, 0.39, 60.0, datetime.now(timezone.utc))
        
        assert manager.classify_route_risk_level(high_risk_stats) == RouteRiskLevel.HIGH_RISK    # >40%
        assert manager.classify_route_risk_level(medium_risk_stats) == RouteRiskLevel.MEDIUM_RISK  # =40%
        assert manager.classify_route_risk_level(low_risk_stats) == RouteRiskLevel.MEDIUM_RISK    # <40% but >20%
        
        # Verify high-risk route frequency override
        assert manager.high_risk_route_frequency == 5  # 5 minutes for high-risk routes
    
    @pytest.mark.asyncio
    async def test_req_1_6_performance_optimization(self):
        """Test REQ-1.6: Performance optimization through intelligent polling"""
        manager = MonitoringFrequencyManager()
        
        # Test that optimization reduces unnecessary polling
        # This would be tested more thoroughly with actual monitor data
        
        # Verify optimization method exists and returns performance metrics
        optimization_stats = await manager.optimize_monitoring_performance()
        
        required_metrics = [
            "monitors_optimized",
            "frequency_increases", 
            "frequency_decreases",
            "performance_gained_minutes"
        ]
        
        for metric in required_metrics:
            assert metric in optimization_stats
            assert isinstance(optimization_stats[metric], int)
    
    @pytest.mark.asyncio
    async def test_default_frequencies_implementation(self):
        """Test that default frequencies match requirements (15min default, 5min high-risk)"""
        manager = MonitoringFrequencyManager()
        
        # Verify default frequency is 15 minutes
        assert MonitoringFrequency.DEFAULT_FREQUENCY.value == 15
        
        # Verify high-risk frequency is 5 minutes  
        assert MonitoringFrequency.HIGH_FREQUENCY.value == 5
        
        # Verify these are used in the frequency mapping
        assert manager.frequency_mapping[RiskLevel.MEDIUM] == 15  # Default
        assert manager.frequency_mapping[RiskLevel.HIGH] == 5     # High-risk


@pytest.mark.asyncio
async def test_standalone_function():
    """Test standalone monitoring frequency adjustment function"""
    # Test that the standalone function executes without error
    summary = await run_monitoring_frequency_adjustment()
    
    assert isinstance(summary, dict)
    # Should have either completed successfully or returned error info
    assert "cycle_completed_at" in summary


if __name__ == "__main__":
    # Run specific test
    pytest.main([__file__, "-v"])
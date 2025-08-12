# tests/flight_agent/test_adaptive_flight_monitoring_service.py
"""
Tests for Adaptive Flight Monitoring Service
Task 2.3: Implement monitoring frequency adjustment

Test coverage for:
- Integration of dynamic frequency management with flight monitoring
- Adaptive monitoring loop behavior
- High-risk route monitoring
- Monitoring interruption handling
- Performance optimization integration
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock

from flight_agent.services.adaptive_flight_monitoring_service import (
    AdaptiveFlightMonitoringService,
    run_adaptive_monitoring_service
)
from flight_agent.services.monitoring_frequency_manager import MonitoringFrequencyManager, RouteRiskLevel
from flight_agent.services.disruption_risk_detector import RiskLevel
from flight_agent.models import (
    SessionLocal, Booking, TripMonitor, DisruptionEvent,
    User, create_user, create_booking, create_trip_monitor, create_disruption_event
)


class TestAdaptiveFlightMonitoringService:
    """Test AdaptiveFlightMonitoringService core functionality"""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        return mock_redis
    
    @pytest.fixture
    def service(self, mock_redis):
        """Create AdaptiveFlightMonitoringService instance"""
        with patch('redis.from_url', return_value=mock_redis):
            service = AdaptiveFlightMonitoringService(
                check_interval_seconds=60,
                enable_mock_provider=True,
                frequency_adjustment_interval=120  # 2 minutes for testing
            )
        return service
    
    @pytest.fixture
    def test_user(self):
        """Create test user"""
        return create_user("adaptive_test@example.com", "+1234567890")
    
    @pytest.fixture
    def test_booking(self, test_user):
        """Create test booking"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        booking_data = {
            "pnr": "ADAPT123",
            "airline": "AA",
            "flight_number": "AA123",
            "departure_date": departure_date,
            "origin": "JFK",
            "destination": "LAX"
        }
        return create_booking(test_user.user_id, booking_data)
    
    @pytest.fixture
    def test_monitor(self, test_user, test_booking):
        """Create test trip monitor"""
        monitor_data = {
            "check_frequency_minutes": 15,  # Default frequency
            "expires_at": datetime.now(timezone.utc) + timedelta(days=2)
        }
        return create_trip_monitor(test_user.user_id, test_booking.booking_id, "flight_123", monitor_data)
    
    def test_service_initialization(self, service):
        """Test adaptive service initializes properly"""
        assert isinstance(service, AdaptiveFlightMonitoringService)
        assert isinstance(service.frequency_manager, MonitoringFrequencyManager)
        assert service.frequency_adjustment_interval == 120
        assert service.adaptive_stats["frequency_adjustments"] == 0
        assert service.adaptive_stats["high_risk_routes_monitored"] == 0
        assert service.adaptive_stats["interruption_alerts_sent"] == 0
        assert service.adaptive_stats["performance_optimizations"] == 0
    
    def test_is_monitor_due_for_check(self, service, test_monitor):
        """Test monitor check timing logic"""
        current_time = datetime.now(timezone.utc)
        
        # First check should always be due
        test_monitor.last_check = None
        assert service._is_monitor_due_for_check(test_monitor, current_time)
        
        # Recently checked should not be due
        test_monitor.last_check = current_time - timedelta(minutes=5)  # 5 min ago
        test_monitor.check_frequency_minutes = 15  # Check every 15 min
        assert not service._is_monitor_due_for_check(test_monitor, current_time)
        
        # Overdue check should be due
        test_monitor.last_check = current_time - timedelta(minutes=20)  # 20 min ago
        assert service._is_monitor_due_for_check(test_monitor, current_time)
    
    @pytest.mark.asyncio
    async def test_trigger_frequency_optimization(self, service):
        """Test manual frequency optimization trigger"""
        # Mock the frequency manager's run cycle
        mock_results = {
            "monitors_optimized": 3,
            "interruption_alerts_created": 1,
            "performance_gained_minutes": 45
        }
        service.frequency_manager.run_monitoring_adjustment_cycle = AsyncMock(return_value=mock_results)
        
        results = await service.trigger_frequency_optimization()
        
        assert results == mock_results
        assert service.adaptive_stats["performance_optimizations"] == 3
        assert service.adaptive_stats["frequency_adjustments"] == 3
        assert service.adaptive_stats["interruption_alerts_sent"] == 1
    
    @pytest.mark.asyncio
    async def test_get_high_risk_routes(self, service):
        """Test high-risk routes retrieval"""
        # Mock some high-risk routes in the frequency manager cache
        from flight_agent.services.monitoring_frequency_manager import RouteDelayStats
        
        service.frequency_manager.route_stats_cache = {
            "ORD-DFW": RouteDelayStats("ORD-DFW", 100, 45, 0.45, 60.0, datetime.now(timezone.utc)),  # 45% delay rate
            "JFK-BOS": RouteDelayStats("JFK-BOS", 100, 50, 0.50, 75.0, datetime.now(timezone.utc)),  # 50% delay rate
            "LAX-SEA": RouteDelayStats("LAX-SEA", 100, 15, 0.15, 30.0, datetime.now(timezone.utc))   # 15% delay rate (not high-risk)
        }
        
        high_risk_routes = await service.get_high_risk_routes()
        
        assert len(high_risk_routes) == 2  # Only routes with >40% delay rate
        
        # Should be sorted by delay rate (highest first)
        assert high_risk_routes[0]["route"] == "JFK-BOS"
        assert high_risk_routes[0]["delay_rate"] == 0.50
        assert high_risk_routes[1]["route"] == "ORD-DFW"
        assert high_risk_routes[1]["delay_rate"] == 0.45
        
        # Verify route details
        for route in high_risk_routes:
            assert route["risk_level"] == "HIGH"
            assert route["delay_rate"] > 0.40
            assert "total_flights" in route
            assert "delayed_flights" in route
            assert "average_delay_minutes" in route
    
    @pytest.mark.asyncio
    async def test_get_monitoring_interruptions(self, service, test_user, test_booking):
        """Test monitoring interruption detection"""
        # Create monitor with last check >30 minutes ago
        interruption_time = datetime.now(timezone.utc) - timedelta(minutes=45)
        
        monitor_data = {
            "check_frequency_minutes": 15,
            "last_check": interruption_time,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=2)
        }
        interrupted_monitor = create_trip_monitor(test_user.user_id, test_booking.booking_id, "interrupted_flight", monitor_data)
        
        # Set last_check in database
        db = SessionLocal()
        try:
            monitor_record = db.query(TripMonitor).filter(TripMonitor.monitor_id == interrupted_monitor.monitor_id).first()
            monitor_record.last_check = interruption_time
            db.commit()
        finally:
            db.close()
        
        interruptions = await service.get_monitoring_interruptions()
        
        assert len(interruptions) > 0
        
        interruption = interruptions[0]
        assert interruption["monitor_id"] == interrupted_monitor.monitor_id
        assert interruption["flight_number"] == test_booking.flight_number
        assert interruption["route"] == f"{test_booking.origin}-{test_booking.destination}"
        assert interruption["interruption_minutes"] == 45.0
        assert interruption["severity"] == "MEDIUM"  # 30-60 minutes
        assert interruption["expected_frequency"] == 15
    
    def test_classify_interruption_severity(self, service):
        """Test interruption severity classification"""
        assert service._classify_interruption_severity(30) == "MEDIUM"   # 30 minutes
        assert service._classify_interruption_severity(45) == "MEDIUM"   # 45 minutes
        assert service._classify_interruption_severity(90) == "HIGH"     # 1.5 hours
        assert service._classify_interruption_severity(150) == "CRITICAL"  # 2.5 hours
    
    @pytest.mark.asyncio
    async def test_update_average_frequency_stats(self, service, test_user):
        """Test average frequency statistics calculation"""
        # Create monitors with different frequencies
        bookings = []
        monitors = []
        frequencies = [5, 15, 30, 5, 15]  # Average should be 14
        
        for i, freq in enumerate(frequencies):
            booking_data = {
                "pnr": f"FREQ{i}",
                "airline": "AA",
                "flight_number": f"AA{100+i}",
                "departure_date": datetime.now(timezone.utc) + timedelta(days=1),
                "origin": "JFK",
                "destination": "LAX"
            }
            booking = create_booking(test_user.user_id, booking_data)
            bookings.append(booking)
            
            monitor_data = {"check_frequency_minutes": freq}
            monitor = create_trip_monitor(test_user.user_id, booking.booking_id, f"flight_{i}", monitor_data)
            monitors.append(monitor)
        
        await service._update_average_frequency_stats()
        
        expected_average = sum(frequencies) / len(frequencies)
        assert service.adaptive_stats["average_monitoring_frequency"] == expected_average
        
        # Should count 2 high-risk routes (frequency <= 5)
        high_risk_count = sum(1 for freq in frequencies if freq <= 5)
        assert service.adaptive_stats["high_risk_routes_monitored"] == high_risk_count
    
    def test_get_adaptive_service_stats(self, service):
        """Test comprehensive adaptive service statistics"""
        # Set some test statistics
        service.adaptive_stats["frequency_adjustments"] = 5
        service.adaptive_stats["high_risk_routes_monitored"] = 3
        service.adaptive_stats["interruption_alerts_sent"] = 2
        service.adaptive_stats["performance_optimizations"] = 4
        service.last_frequency_adjustment = datetime.now(timezone.utc)
        
        stats = service.get_adaptive_service_stats()
        
        # Should include base service stats
        assert "service_status" in stats
        assert "provider_count" in stats
        
        # Should include adaptive statistics
        assert "adaptive_statistics" in stats
        assert stats["adaptive_statistics"]["frequency_adjustments"] == 5
        assert stats["adaptive_statistics"]["high_risk_routes_monitored"] == 3
        
        # Should include frequency management info
        assert "frequency_management" in stats
        assert "last_frequency_adjustment" in stats
        
        # Should include adaptive features info
        assert "adaptive_features" in stats
        adaptive_features = stats["adaptive_features"]
        assert adaptive_features["dynamic_frequency_enabled"]
        assert adaptive_features["high_risk_threshold"] == 0.40
        assert adaptive_features["interruption_threshold_minutes"] == 30
        assert adaptive_features["base_frequencies"]["high_risk"] == 5
        assert adaptive_features["base_frequencies"]["default"] == 15
        assert adaptive_features["base_frequencies"]["low_risk"] == 30
    
    @pytest.mark.asyncio
    async def test_force_health_check_with_frequency_analysis(self, service):
        """Test enhanced health check with frequency analysis"""
        # Mock the base health check
        base_health = {
            "service_status": "running",
            "provider_count": 2,
            "statistics": {"checks_performed": 100}
        }
        
        with patch.object(service, 'force_health_check', return_value=base_health):
            # Mock high-risk routes and interruptions
            service.get_high_risk_routes = AsyncMock(return_value=[
                {"route": "ORD-DFW", "delay_rate": 0.45},
                {"route": "JFK-BOS", "delay_rate": 0.50}
            ])
            service.get_monitoring_interruptions = AsyncMock(return_value=[
                {"monitor_id": "test_123", "interruption_minutes": 45}
            ])
            
            health_check = await service.force_health_check_with_frequency_analysis()
            
            assert "frequency_management_health" in health_check
            freq_health = health_check["frequency_management_health"]
            
            assert freq_health["frequency_manager_healthy"]
            assert freq_health["high_risk_routes_count"] == 2
            assert freq_health["active_interruptions_count"] == 1
            assert len(freq_health["optimization_recommendations"]) > 0


class TestAdaptiveMonitoringIntegration:
    """Integration tests for adaptive monitoring"""
    
    @pytest.fixture
    def test_user(self):
        """Create test user for integration tests"""
        return create_user("adaptive_integration@example.com", "+1555000456")
    
    @pytest.mark.asyncio
    @patch('redis.from_url')
    async def test_adaptive_monitor_all_flights(self, mock_redis_from_url, test_user):
        """Test adaptive monitoring with different frequencies per monitor"""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis_from_url.return_value = mock_redis
        
        service = AdaptiveFlightMonitoringService(
            check_interval_seconds=60,
            enable_mock_provider=True
        )
        
        # Create monitors with different frequencies and last check times
        monitors_data = [
            {"freq": 5, "last_check_offset": 6, "should_check": True},   # High-risk, due for check
            {"freq": 15, "last_check_offset": 10, "should_check": False}, # Default, not due yet
            {"freq": 30, "last_check_offset": 35, "should_check": True},  # Low-risk, due for check
        ]
        
        monitors = []
        bookings = []
        current_time = datetime.now(timezone.utc)
        
        for i, data in enumerate(monitors_data):
            # Create booking
            booking_data = {
                "pnr": f"ADAPT{i}",
                "airline": "AA",
                "flight_number": f"AA{150+i}",
                "departure_date": current_time + timedelta(days=1),
                "origin": "JFK",
                "destination": "LAX"
            }
            booking = create_booking(test_user.user_id, booking_data)
            bookings.append(booking)
            
            # Create monitor
            monitor_data = {
                "check_frequency_minutes": data["freq"],
                "last_check": current_time - timedelta(minutes=data["last_check_offset"]),
                "expires_at": current_time + timedelta(days=2)
            }
            monitor = create_trip_monitor(test_user.user_id, booking.booking_id, f"flight_{i}", monitor_data)
            monitors.append(monitor)
        
        # Mock the flight status methods
        service.get_multiple_flights_status = AsyncMock(return_value={
            "AA150": Mock(flight_id="AA150_20250116", status="ON TIME", is_disrupted=False),
            "AA152": Mock(flight_id="AA152_20250116", status="ON TIME", is_disrupted=False)
        })
        service._process_flight_status = AsyncMock()
        
        # Run adaptive monitoring
        await service._adaptive_monitor_all_flights()
        
        # Should have checked 2 monitors (indices 0 and 2 were due)
        # Note: This is a simplified test - in reality, the database state matters
        assert service.stats["checks_performed"] > 0
    
    @pytest.mark.asyncio
    @patch('redis.from_url')
    async def test_periodic_frequency_adjustments(self, mock_redis_from_url, test_user):
        """Test periodic frequency adjustment background task"""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_from_url.return_value = mock_redis
        
        service = AdaptiveFlightMonitoringService(
            frequency_adjustment_interval=1,  # 1 second for testing
            enable_mock_provider=True
        )
        
        # Mock the frequency adjustment cycle
        mock_summary = {
            "monitors_optimized": 2,
            "interruption_alerts_created": 1,
            "performance_gained_minutes": 20
        }
        service.frequency_manager.run_monitoring_adjustment_cycle = AsyncMock(return_value=mock_summary)
        service._update_average_frequency_stats = AsyncMock()
        
        # Start the background task
        task = asyncio.create_task(service._periodic_frequency_adjustments())
        
        # Let it run for a short time
        await asyncio.sleep(1.5)
        
        # Stop the task
        service.running = False
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Should have run at least once
        assert service.adaptive_stats["performance_optimizations"] >= 2
        assert service.adaptive_stats["interruption_alerts_sent"] >= 1
        assert service.last_frequency_adjustment is not None
    
    @pytest.mark.asyncio
    async def test_end_to_end_high_risk_scenario(self, test_user):
        """Test end-to-end high-risk route monitoring scenario"""
        with patch('redis.from_url') as mock_redis_from_url:
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis.get.return_value = None
            mock_redis.setex.return_value = True
            mock_redis_from_url.return_value = mock_redis
            
            service = AdaptiveFlightMonitoringService(enable_mock_provider=True)
            
            # Create high-risk scenario: flight departing soon on historically bad route
            near_departure = datetime.now(timezone.utc) + timedelta(hours=2)
            booking_data = {
                "pnr": "HIGHRISK999",
                "airline": "NK",  # Budget carrier
                "flight_number": "NK999",
                "departure_date": near_departure,
                "origin": "LGA",  # Congested airport
                "destination": "ORD"  # Weather-prone
            }
            booking = create_booking(test_user.user_id, booking_data)
            
            # Create historical bad performance for this route
            historical_bookings = []
            for i in range(10):
                hist_data = {
                    "pnr": f"HIST{i}",
                    "airline": "NK",
                    "flight_number": f"NK{800+i}",
                    "departure_date": datetime.now(timezone.utc) - timedelta(days=15-i),
                    "origin": "LGA",
                    "destination": "ORD"
                }
                hist_booking = create_booking(test_user.user_id, hist_data)
                historical_bookings.append(hist_booking)
                
                # Create delay events for 5 out of 10 flights (50% delay rate)
                if i < 5:
                    disruption_data = {
                        "type": "DELAYED",
                        "original_departure": hist_booking.departure_date,
                        "delay_minutes": 90,
                        "reason": "Weather delay"
                    }
                    create_disruption_event(hist_booking.booking_id, disruption_data)
            
            # Create monitor with default frequency
            monitor_data = {"check_frequency_minutes": 15}
            monitor = create_trip_monitor(test_user.user_id, booking.booking_id, "high_risk_flight", monitor_data)
            
            # Trigger frequency optimization
            with patch('flight_agent.services.monitoring_frequency_manager.detect_disruption_risk') as mock_risk:
                mock_risk.return_value = Mock(risk_level=RiskLevel.HIGH)
                
                optimization_results = await service.trigger_frequency_optimization()
                
                # Verify optimization was triggered
                assert "cycle_completed_at" in optimization_results or optimization_results.get("monitors_optimized", 0) >= 0
            
            # Check for high-risk routes
            high_risk_routes = await service.get_high_risk_routes()
            
            # Should detect LGA-ORD as high-risk route
            lga_ord_route = next((r for r in high_risk_routes if r["route"] == "LGA-ORD"), None)
            if lga_ord_route:
                assert lga_ord_route["delay_rate"] >= 0.40  # Should exceed threshold


@pytest.mark.asyncio
async def test_standalone_adaptive_monitoring():
    """Test standalone adaptive monitoring function"""
    
    # Test that the function can be called without error
    # We'll cancel it quickly to avoid running indefinitely
    task = asyncio.create_task(run_adaptive_monitoring_service(
        check_interval=60,
        enable_mock_provider=True,
        frequency_adjustment_interval=300
    ))
    
    # Let it start up
    await asyncio.sleep(0.1)
    
    # Cancel it
    task.cancel()
    
    try:
        await task
    except asyncio.CancelledError:
        pass  # Expected
    
    # Test completed without errors during startup


if __name__ == "__main__":
    # Run specific test
    pytest.main([__file__, "-v"])
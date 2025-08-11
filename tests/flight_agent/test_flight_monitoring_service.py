# tests/flight_agent/test_flight_monitoring_service.py
import pytest
import asyncio
import json
import redis
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from flight_agent.services.flight_monitoring_service import (
    FlightMonitoringService,
    FlightStatusData,
    FlightAwareDataSource,
    BackupDataSource
)
from flight_agent.models import SessionLocal, Booking, TripMonitor, User, create_user, create_booking, create_trip_monitor

class TestFlightStatusData:
    """Test FlightStatusData dataclass"""
    
    def test_flight_status_data_creation(self):
        """Test creating FlightStatusData instance"""
        now = datetime.now(timezone.utc)
        
        data = FlightStatusData(
            flight_id="AA123_20250115",
            status="ON TIME",
            delay_minutes=0,
            scheduled_departure=now,
            actual_departure=None,
            scheduled_arrival=now + timedelta(hours=2),
            actual_arrival=None,
            gate="A12",
            terminal="1",
            is_disrupted=False,
            disruption_type=None,
            last_updated=now,
            source="FlightAware",
            raw_data={"test": "data"}
        )
        
        assert data.flight_id == "AA123_20250115"
        assert data.status == "ON TIME"
        assert not data.is_disrupted
        assert data.source == "FlightAware"

class TestFlightDataSources:
    """Test flight data source implementations"""
    
    @patch('flight_agent.services.flight_monitoring_service.get_flight_status')
    async def test_flightaware_data_source_success(self, mock_get_flight_status):
        """Test successful FlightAware data source call"""
        mock_get_flight_status.return_value = "Flight AA123: Status = ON TIME, Origin = JFK, Destination = LAX"
        
        source = FlightAwareDataSource()
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        result = await source.get_flight_status("AA123", departure_date)
        
        assert result is not None
        assert result.status == "Flight AA123: Status = ON TIME, Origin = JFK, Destination = LAX"
        assert not result.is_disrupted
        assert result.source == "FlightAware"
    
    @patch('flight_agent.services.flight_monitoring_service.get_flight_status')
    async def test_flightaware_data_source_cancelled_flight(self, mock_get_flight_status):
        """Test FlightAware detecting cancelled flight"""
        mock_get_flight_status.return_value = "Flight AA123: Status = CANCELLED, Origin = JFK, Destination = LAX"
        
        source = FlightAwareDataSource()
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        result = await source.get_flight_status("AA123", departure_date)
        
        assert result is not None
        assert result.is_disrupted
        assert result.disruption_type == "CANCELLED"
    
    @patch('flight_agent.services.flight_monitoring_service.get_flight_status')
    async def test_flightaware_data_source_api_error(self, mock_get_flight_status):
        """Test FlightAware API error handling"""
        mock_get_flight_status.return_value = "ERROR: API timeout"
        
        source = FlightAwareDataSource()
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        result = await source.get_flight_status("AA123", departure_date)
        
        assert result is None
        assert source.last_error == "ERROR: API timeout"
    
    async def test_backup_data_source(self):
        """Test backup data source functionality"""
        source = BackupDataSource()
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        result = await source.get_flight_status("AA123", departure_date)
        
        assert result is not None
        assert result.status == "ON TIME (Backup Source)"
        assert not result.is_disrupted
        assert result.source == "BackupAPI"

class TestFlightMonitoringService:
    """Test FlightMonitoringService main functionality"""
    
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
        """Create FlightMonitoringService instance with mocked Redis"""
        with patch('redis.from_url', return_value=mock_redis):
            service = FlightMonitoringService(
                check_interval_seconds=60,
                cache_ttl_seconds=300
            )
        return service
    
    def test_service_initialization(self, service):
        """Test service initialization"""
        assert service.check_interval == 60
        assert service.cache_ttl == 300
        assert not service.running
        assert len(service.data_sources) >= 1  # At least backup source should be available
        assert service.stats["checks_performed"] == 0
    
    def test_cache_key_generation(self, service):
        """Test Redis cache key generation"""
        departure_date = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
        cache_key = service._get_cache_key("AA123", departure_date)
        
        assert cache_key == "flight_status:AA123:20250115"
    
    async def test_cache_flight_status(self, service):
        """Test caching flight status data"""
        now = datetime.now(timezone.utc)
        status_data = FlightStatusData(
            flight_id="AA123_20250115",
            status="ON TIME",
            delay_minutes=0,
            scheduled_departure=now,
            actual_departure=None,
            scheduled_arrival=now + timedelta(hours=2),
            actual_arrival=None,
            gate="A12",
            terminal="1",
            is_disrupted=False,
            disruption_type=None,
            last_updated=now,
            source="FlightAware",
            raw_data={"test": "data"}
        )
        
        success = await service.cache_flight_status(status_data)
        assert success
    
    async def test_get_cached_flight_status(self, service):
        """Test retrieving cached flight status"""
        now = datetime.now(timezone.utc)
        departure_date = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
        
        # Mock cached data
        cached_data = {
            "flight_id": "AA123_20250115",
            "status": "ON TIME",
            "delay_minutes": 0,
            "scheduled_departure": departure_date.isoformat(),
            "actual_departure": None,
            "scheduled_arrival": (departure_date + timedelta(hours=2)).isoformat(),
            "actual_arrival": None,
            "gate": "A12",
            "terminal": "1",
            "is_disrupted": False,
            "disruption_type": None,
            "last_updated": now.isoformat(),
            "source": "FlightAware",
            "raw_data": {"test": "data"}
        }
        
        service.redis_client.get.return_value = json.dumps(cached_data)
        
        result = await service.get_cached_flight_status("AA123", departure_date)
        
        assert result is not None
        assert result.flight_id == "AA123_20250115"
        assert result.status == "ON TIME"
        assert service.stats["cache_hits"] == 1
    
    async def test_get_cached_flight_status_miss(self, service):
        """Test cache miss scenario"""
        departure_date = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
        service.redis_client.get.return_value = None
        
        result = await service.get_cached_flight_status("AA123", departure_date)
        
        assert result is None
        assert service.stats["cache_misses"] == 1
    
    @patch('flight_agent.services.flight_monitoring_service.get_flight_status')
    async def test_multi_source_flight_status_primary_success(self, mock_get_flight_status, service):
        """Test multi-source with primary source success"""
        mock_get_flight_status.return_value = "Flight AA123: Status = ON TIME, Origin = JFK, Destination = LAX"
        
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        result = await service.get_flight_status_multi_source("AA123", departure_date)
        
        assert result is not None
        assert result.source in ["FlightAware", "BackupAPI"]  # Could be either depending on availability
        assert service.stats["api_calls"] == 1
    
    @patch('flight_agent.services.flight_monitoring_service.get_flight_status')
    async def test_multi_source_flight_status_fallback(self, mock_get_flight_status, service):
        """Test multi-source with fallback to backup"""
        # Make primary source fail
        mock_get_flight_status.side_effect = Exception("API Error")
        
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        result = await service.get_flight_status_multi_source("AA123", departure_date)
        
        # Should get backup source result
        assert result is not None
        assert result.source == "BackupAPI"
    
    def test_service_stats(self, service):
        """Test service statistics"""
        stats = service.get_service_stats()
        
        assert "service_status" in stats
        assert "check_interval_seconds" in stats
        assert "cache_ttl_seconds" in stats
        assert "redis_connected" in stats
        assert "data_sources" in stats
        assert "statistics" in stats
        
        assert stats["check_interval_seconds"] == 60
        assert stats["cache_ttl_seconds"] == 300
        assert isinstance(stats["data_sources"], list)

class TestFlightMonitoringServiceIntegration:
    """Integration tests for FlightMonitoringService"""
    
    @pytest.fixture(scope="function")
    def test_user(self):
        """Create a test user"""
        user = create_user("test@example.com", "+1234567890")
        yield user
        # Cleanup would go here if needed
    
    @pytest.fixture(scope="function") 
    def test_booking(self, test_user):
        """Create a test booking"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        booking_data = {
            "pnr": "TEST123",
            "airline": "AA",
            "flight_number": "AA123",
            "departure_date": departure_date,
            "origin": "JFK",
            "destination": "LAX"
        }
        
        booking = create_booking(test_user.user_id, booking_data)
        yield booking
        # Cleanup would go here if needed
    
    @pytest.fixture(scope="function")
    def test_monitor(self, test_user, test_booking):
        """Create a test trip monitor"""
        monitor = create_trip_monitor(
            test_user.user_id, 
            test_booking.booking_id,
            "flight_123",  # mock flight_id
            {
                "check_frequency_minutes": 30,
                "expires_at": datetime.now(timezone.utc) + timedelta(days=2)
            }
        )
        yield monitor
        # Cleanup would go here if needed
    
    @pytest.mark.asyncio
    async def test_monitor_single_flight_integration(self, test_monitor):
        """Integration test for monitoring a single flight"""
        service = FlightMonitoringService(check_interval_seconds=60)
        
        # Mock the multi-source method to return test data
        async def mock_get_status(flight_number, departure_date):
            return FlightStatusData(
                flight_id=f"{flight_number}_{departure_date.strftime('%Y%m%d')}",
                status="ON TIME",
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
                source="Test",
                raw_data={}
            )
        
        service.get_flight_status_multi_source = mock_get_status
        
        db = SessionLocal()
        try:
            # Test monitoring
            await service._monitor_single_flight(test_monitor, db)
            
            # Verify monitor was updated
            db.refresh(test_monitor)
            assert test_monitor.last_check is not None
            
        finally:
            db.close()

@pytest.mark.asyncio 
async def test_service_start_stop():
    """Test service start/stop functionality"""
    service = FlightMonitoringService(check_interval_seconds=1)  # Very short interval for testing
    
    # Start service in background
    monitor_task = asyncio.create_task(service.start_monitoring())
    
    # Let it run briefly
    await asyncio.sleep(0.1)
    assert service.running
    
    # Stop service
    service.stop_monitoring()
    assert not service.running
    
    # Cancel the task
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

class TestPerformanceRequirements:
    """Test that service meets performance requirements (REQ-1.6)"""
    
    @pytest.mark.asyncio
    async def test_flight_status_check_within_5_seconds(self):
        """Test that flight status checks complete within 5 seconds (REQ-1.6)"""
        service = FlightMonitoringService()
        
        # Pre-populate cache
        now = datetime.now(timezone.utc)
        departure_date = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
        
        status_data = FlightStatusData(
            flight_id="AA123_20250115",
            status="ON TIME",
            delay_minutes=0,
            scheduled_departure=departure_date,
            actual_departure=None,
            scheduled_arrival=departure_date + timedelta(hours=2),
            actual_arrival=None,
            gate="A12",
            terminal="1",
            is_disrupted=False,
            disruption_type=None,
            last_updated=now,
            source="FlightAware",
            raw_data={}
        )
        
        await service.cache_flight_status(status_data)
        
        # Measure time for cached lookup
        start_time = datetime.now()
        result = await service.get_flight_status_multi_source("AA123", departure_date)
        end_time = datetime.now()
        
        execution_time = (end_time - start_time).total_seconds()
        
        assert result is not None
        assert execution_time < 5.0  # REQ-1.6: Within 5 seconds
        assert execution_time < 1.0  # Should be much faster with cache (sub-second)

if __name__ == "__main__":
    # Run specific test
    pytest.main([__file__, "-v"])
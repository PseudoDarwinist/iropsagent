"""
Tests for flight data provider interfaces and implementations.

Tests REQ-7.1: Flight Data Provider Interface
Tests REQ-7.2: Failover Logic Implementation
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Optional

from flight_agent.providers import (
    FlightDataProvider,
    ProviderStatus,
    MockFlightDataProvider,
    FlightAwareProvider,
    FailoverManager,
    FailoverConfig
)
from flight_agent.providers.interfaces import (
    FlightStatusData,
    ProviderError,
    RateLimitError,
    TimeoutError,
    AuthenticationError
)


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
            source="TestProvider",
            confidence_score=0.95,
            raw_data={"test": "data"}
        )
        
        assert data.flight_id == "AA123_20250115"
        assert data.status == "ON TIME"
        assert not data.is_disrupted
        assert data.source == "TestProvider"
        assert data.confidence_score == 0.95


class TestMockFlightDataProvider:
    """Test mock provider implementation"""
    
    @pytest.fixture
    def mock_provider(self):
        return MockFlightDataProvider(
            name="TestMock",
            simulate_errors=False,
            simulate_delays=False
        )
    
    @pytest.mark.asyncio
    async def test_basic_flight_status(self, mock_provider):
        """Test basic flight status retrieval"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        result = await mock_provider.get_flight_status("AA123", departure_date)
        
        assert result is not None
        assert result.flight_id == f"AA123_{departure_date.strftime('%Y%m%d')}"
        assert result.source == "TestMock"
        assert result.confidence_score > 0.8
        assert mock_provider.metrics.total_requests == 1
        assert mock_provider.metrics.success_rate == 1.0
    
    @pytest.mark.asyncio
    async def test_predefined_scenarios(self, mock_provider):
        """Test predefined flight scenarios"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        # Test on-time flight
        result = await mock_provider.get_flight_status("AA123", departure_date)
        assert result.status == "ON TIME"
        assert not result.is_disrupted
        
        # Test delayed flight
        result = await mock_provider.get_flight_status("UA456", departure_date)
        assert result.status == "DELAYED"
        assert result.is_disrupted
        assert result.disruption_type == "DELAYED"
        assert result.delay_minutes > 0
        
        # Test cancelled flight
        result = await mock_provider.get_flight_status("DL789", departure_date)
        assert result.status == "CANCELLED"
        assert result.is_disrupted
        assert result.disruption_type == "CANCELLED"
    
    @pytest.mark.asyncio
    async def test_error_simulation(self):
        """Test error simulation functionality"""
        provider = MockFlightDataProvider(
            simulate_errors=True,
            error_rate=1.0  # Always error
        )
        
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        result = await provider.get_flight_status("AA123", departure_date)
        
        # Should return None due to simulated error
        assert result is None
        assert provider.metrics.failed_requests > 0
        assert provider.metrics.success_rate < 1.0
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_provider):
        """Test health check functionality"""
        is_healthy = await mock_provider.health_check()
        assert is_healthy
        assert mock_provider.status == ProviderStatus.AVAILABLE
    
    @pytest.mark.asyncio
    async def test_multiple_flights(self, mock_provider):
        """Test batch flight status retrieval"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        flight_requests = [
            ("AA123", departure_date),
            ("UA456", departure_date),
            ("DL789", departure_date)
        ]
        
        results = await mock_provider.get_multiple_flights(flight_requests)
        
        assert len(results) == 3
        assert "AA123" in results
        assert "UA456" in results 
        assert "DL789" in results
        
        # Check that all results are valid
        for flight_number, result in results.items():
            assert result is not None
            assert result.source == "TestMock"
    
    def test_custom_scenarios(self, mock_provider):
        """Test adding custom scenarios"""
        custom_scenario = {
            "status": "DIVERTED", 
            "disrupted": True, 
            "type": "DIVERTED"
        }
        
        mock_provider.add_custom_scenario("TEST123", custom_scenario)
        assert "TEST123" in mock_provider.flight_scenarios
        assert mock_provider.flight_scenarios["TEST123"] == custom_scenario
    
    def test_metrics_tracking(self, mock_provider):
        """Test metrics are properly tracked"""
        # Initial metrics
        assert mock_provider.metrics.total_requests == 0
        assert mock_provider.metrics.success_rate == 0.0
        
        # Simulate successful request
        mock_provider.update_metrics(True, 0.5)
        assert mock_provider.metrics.total_requests == 1
        assert mock_provider.metrics.success_rate == 1.0
        assert mock_provider.metrics.average_response_time == 0.5
        
        # Simulate failed request
        mock_provider.update_metrics(False, 1.0, "Test error")
        assert mock_provider.metrics.total_requests == 2
        assert mock_provider.metrics.success_rate == 0.5
        assert mock_provider.metrics.last_error == "Test error"


class TestFlightAwareProvider:
    """Test FlightAware provider implementation"""
    
    @pytest.fixture
    def provider_with_key(self):
        return FlightAwareProvider(api_key="test_key_123")
    
    @pytest.fixture
    def provider_no_key(self):
        return FlightAwareProvider(api_key=None)
    
    def test_initialization_with_key(self, provider_with_key):
        """Test provider initialization with API key"""
        assert provider_with_key.api_key == "test_key_123"
        assert provider_with_key.name == "FlightAware"
        assert provider_with_key.priority == 10
        assert provider_with_key.is_available
    
    def test_initialization_without_key(self, provider_no_key):
        """Test provider initialization without API key"""
        assert not provider_no_key.is_available
        assert provider_no_key.status == ProviderStatus.UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_get_flight_status_unavailable_provider(self, provider_no_key):
        """Test that unavailable provider returns None"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        result = await provider_no_key.get_flight_status("AA123", departure_date)
        assert result is None
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_successful_api_call(self, mock_get, provider_with_key):
        """Test successful FlightAware API call"""
        
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "flights": [{
                "ident": "AA123",
                "status": "Scheduled",
                "scheduled_out": "2025-01-15T10:30:00Z",
                "scheduled_in": "2025-01-15T14:30:00Z",
                "actual_out": None,
                "actual_in": None,
                "cancelled": False,
                "diverted": False,
                "gate_dest": "A12",
                "terminal_dest": "1"
            }]
        }
        
        mock_get.return_value.__aenter__.return_value = mock_response
        
        departure_date = datetime(2025, 1, 15, 10, 30, timezone.utc)
        result = await provider_with_key.get_flight_status("AA123", departure_date)
        
        assert result is not None
        assert result.flight_id == "AA123_20250115"
        assert result.source == "FlightAware"
        assert not result.is_disrupted
        assert provider_with_key.metrics.success_rate == 1.0
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_rate_limit_error(self, mock_get, provider_with_key):
        """Test rate limit handling"""
        
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {"Retry-After": "300"}
        
        mock_get.return_value.__aenter__.return_value = mock_response
        
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        with pytest.raises(RateLimitError) as exc_info:
            await provider_with_key.get_flight_status("AA123", departure_date)
        
        assert exc_info.value.retry_after == 300
        assert provider_with_key.status == ProviderStatus.RATE_LIMITED
        assert provider_with_key.metrics.rate_limit_hits == 1
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_authentication_error(self, mock_get, provider_with_key):
        """Test authentication error handling"""
        
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text.return_value = "Invalid API key"
        
        mock_get.return_value.__aenter__.return_value = mock_response
        
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        with pytest.raises(AuthenticationError):
            await provider_with_key.get_flight_status("AA123", departure_date)
        
        assert provider_with_key.status == ProviderStatus.UNAVAILABLE
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_timeout_error(self, mock_get, provider_with_key):
        """Test timeout handling"""
        
        mock_get.side_effect = asyncio.TimeoutError()
        
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        with pytest.raises(TimeoutError):
            await provider_with_key.get_flight_status("AA123", departure_date)
        
        assert provider_with_key.metrics.failed_requests > 0
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_health_check_success(self, mock_get, provider_with_key):
        """Test successful health check"""
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        
        mock_get.return_value.__aenter__.return_value = mock_response
        
        is_healthy = await provider_with_key.health_check()
        
        assert is_healthy
        assert provider_with_key.status == ProviderStatus.AVAILABLE


class TestFailoverManager:
    """Test failover manager functionality"""
    
    @pytest.fixture
    def mock_providers(self):
        """Create mock providers for testing"""
        primary = MockFlightDataProvider("Primary", priority=10)
        secondary = MockFlightDataProvider("Secondary", priority=5) 
        backup = MockFlightDataProvider("Backup", priority=1)
        
        return [primary, secondary, backup]
    
    @pytest.fixture
    def failover_manager(self, mock_providers):
        """Create failover manager with mock providers"""
        config = FailoverConfig(
            max_retries_per_provider=2,
            timeout_between_retries=0.1,  # Fast for testing
            circuit_breaker_threshold=2
        )
        return FailoverManager(mock_providers, config)
    
    @pytest.mark.asyncio
    async def test_successful_primary_provider(self, failover_manager):
        """Test successful call using primary provider"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        result = await failover_manager.get_flight_status("AA123", departure_date)
        
        assert result is not None
        assert result.source == "Primary"  # Should use highest priority provider
    
    @pytest.mark.asyncio
    async def test_failover_to_secondary(self, failover_manager, mock_providers):
        """Test failover when primary provider fails"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        # Make primary provider always return None
        primary = mock_providers[0]
        original_get_status = primary.get_flight_status
        
        async def failing_get_status(flight_number, dep_date):
            raise ProviderError("Primary failed", "Primary")
        
        primary.get_flight_status = failing_get_status
        
        result = await failover_manager.get_flight_status("AA123", departure_date)
        
        # Should get result from secondary provider
        assert result is not None
        assert result.source == "Secondary"
        
        # Restore original method
        primary.get_flight_status = original_get_status
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_functionality(self, failover_manager, mock_providers):
        """Test circuit breaker opens after multiple failures"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        primary = mock_providers[0]
        
        # Make primary provider always fail
        async def always_fail(flight_number, dep_date):
            raise ProviderError("Always fails", "Primary")
        
        original_method = primary.get_flight_status
        primary.get_flight_status = always_fail
        
        # First few calls should try primary and failover to secondary
        for _ in range(3):
            result = await failover_manager.get_flight_status("AA123", departure_date)
            assert result is not None  # Should get from secondary
            assert result.source == "Secondary"
        
        # Circuit breaker should be open now
        circuit_breaker = failover_manager.circuit_breakers["Primary"]
        assert circuit_breaker.is_open
        assert circuit_breaker.failure_count >= 2
        
        # Restore method
        primary.get_flight_status = original_method
    
    @pytest.mark.asyncio
    async def test_multiple_flights_batch(self, failover_manager):
        """Test batch processing of multiple flights"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        flight_requests = [
            ("AA123", departure_date),
            ("UA456", departure_date),
            ("DL789", departure_date)
        ]
        
        results = await failover_manager.get_multiple_flights(flight_requests)
        
        assert len(results) == 3
        assert all(result is not None for result in results.values())
        
        # All should come from the same provider (batch operation)
        sources = {result.source for result in results.values() if result}
        assert len(sources) == 1  # Single provider used for batch
    
    @pytest.mark.asyncio
    async def test_health_check_all_providers(self, failover_manager):
        """Test health checking all providers"""
        health_results = await failover_manager.health_check_all()
        
        assert len(health_results) == 3
        assert "Primary" in health_results
        assert "Secondary" in health_results
        assert "Backup" in health_results
        
        # All mock providers should be healthy
        assert all(health_results.values())
    
    def test_provider_stats(self, failover_manager):
        """Test getting comprehensive provider statistics"""
        stats = failover_manager.get_provider_stats()
        
        assert "providers" in stats
        assert "circuit_breakers" in stats
        assert "performance_summary" in stats
        
        # Should have stats for all 3 providers
        assert len(stats["providers"]) == 3
        assert len(stats["circuit_breakers"]) == 3
        assert len(stats["performance_summary"]) == 3
        
        # Check structure
        for provider_name in ["Primary", "Secondary", "Backup"]:
            assert provider_name in stats["providers"]
            assert "priority" in stats["providers"][provider_name]
            assert "status" in stats["providers"][provider_name]
            assert "metrics" in stats["providers"][provider_name]
    
    def test_add_remove_provider(self, failover_manager, mock_providers):
        """Test adding and removing providers"""
        initial_count = len(failover_manager.providers)
        
        # Add new provider
        new_provider = MockFlightDataProvider("NewProvider", priority=15)
        failover_manager.add_provider(new_provider)
        
        assert len(failover_manager.providers) == initial_count + 1
        assert failover_manager.providers[0].name == "NewProvider"  # Should be first due to highest priority
        assert "NewProvider" in failover_manager.circuit_breakers
        
        # Remove provider
        failover_manager.remove_provider("NewProvider")
        
        assert len(failover_manager.providers) == initial_count
        assert "NewProvider" not in failover_manager.circuit_breakers
        assert not any(p.name == "NewProvider" for p in failover_manager.providers)
    
    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, failover_manager, mock_providers):
        """Test handling of rate limit errors"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        primary = mock_providers[0]
        
        # Make primary provider rate limited
        async def rate_limited(flight_number, dep_date):
            raise RateLimitError("Rate limited", "Primary", retry_after=60)
        
        original_method = primary.get_flight_status
        primary.get_flight_status = rate_limited
        
        result = await failover_manager.get_flight_status("AA123", departure_date)
        
        # Should failover to secondary immediately (no retries for rate limits)
        assert result is not None
        assert result.source == "Secondary"
        
        # Restore method
        primary.get_flight_status = original_method


class TestProviderInterfaces:
    """Test provider interface compliance"""
    
    def test_provider_status_enum(self):
        """Test ProviderStatus enum values"""
        assert ProviderStatus.AVAILABLE.value == "available"
        assert ProviderStatus.UNAVAILABLE.value == "unavailable"
        assert ProviderStatus.RATE_LIMITED.value == "rate_limited"
        assert ProviderStatus.DEGRADED.value == "degraded"
        assert ProviderStatus.MAINTENANCE.value == "maintenance"
    
    def test_provider_error_classes(self):
        """Test custom exception classes"""
        
        # Base provider error
        error = ProviderError("Test error", "TestProvider", retry_after=30)
        assert str(error) == "Test error"
        assert error.provider_name == "TestProvider"
        assert error.retry_after == 30
        
        # Rate limit error
        rate_error = RateLimitError("Rate limited", "TestProvider", retry_after=60)
        assert rate_error.retry_after == 60
        assert isinstance(rate_error, ProviderError)
        
        # Timeout error
        timeout_error = TimeoutError("Timeout", "TestProvider")
        assert isinstance(timeout_error, ProviderError)
        
        # Authentication error
        auth_error = AuthenticationError("Auth failed", "TestProvider")
        assert isinstance(auth_error, ProviderError)
    
    def test_failover_config(self):
        """Test failover configuration"""
        config = FailoverConfig(
            max_retries_per_provider=3,
            timeout_between_retries=2.0,
            health_check_interval=600,
            circuit_breaker_threshold=10
        )
        
        assert config.max_retries_per_provider == 3
        assert config.timeout_between_retries == 2.0
        assert config.health_check_interval == 600
        assert config.circuit_breaker_threshold == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
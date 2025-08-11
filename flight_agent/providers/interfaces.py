"""
Flight Data Provider interfaces and data structures.

Implements REQ-7.1: FlightDataProvider interface for external APIs
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class ProviderStatus(Enum):
    """Status of a flight data provider"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


@dataclass
class FlightStatusData:
    """Standardized flight status information from any provider"""
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
    source: str  # Provider name
    confidence_score: float  # 0.0-1.0, data reliability
    raw_data: Dict[str, Any]


@dataclass
class ProviderMetrics:
    """Performance metrics for a flight data provider"""
    success_rate: float  # 0.0-1.0
    average_response_time: float  # seconds
    last_successful_call: Optional[datetime]
    last_error: Optional[str]
    total_requests: int
    failed_requests: int
    rate_limit_hits: int


class FlightDataProvider(ABC):
    """
    Abstract base class for flight data providers.
    
    Implements REQ-7.1: FlightDataProvider interface for external APIs
    
    This interface standardizes access to different flight data sources
    (FlightAware, backup APIs, mock sources) with consistent error handling,
    metrics tracking, and failover support.
    """
    
    def __init__(self, name: str, priority: int = 0, timeout_seconds: float = 10.0):
        """
        Initialize the flight data provider.
        
        Args:
            name: Human-readable provider name
            priority: Priority for failover (higher = preferred)
            timeout_seconds: Request timeout in seconds
        """
        self.name = name
        self.priority = priority
        self.timeout_seconds = timeout_seconds
        self.status = ProviderStatus.AVAILABLE
        self._metrics = ProviderMetrics(
            success_rate=0.0,
            average_response_time=0.0,
            last_successful_call=None,
            last_error=None,
            total_requests=0,
            failed_requests=0,
            rate_limit_hits=0
        )
    
    @property
    def metrics(self) -> ProviderMetrics:
        """Get current provider metrics"""
        return self._metrics
    
    @property
    def is_available(self) -> bool:
        """Check if provider is currently available"""
        return self.status == ProviderStatus.AVAILABLE
    
    @abstractmethod
    async def get_flight_status(
        self, 
        flight_number: str, 
        departure_date: datetime
    ) -> Optional[FlightStatusData]:
        """
        Get flight status from this provider.
        
        Args:
            flight_number: IATA flight number (e.g., "AA123")
            departure_date: Scheduled departure date
            
        Returns:
            FlightStatusData if successful, None if failed
            
        Raises:
            ProviderError: If provider-specific error occurs
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform a health check on this provider.
        
        Returns:
            True if provider is healthy, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_multiple_flights(
        self, 
        flight_requests: List[tuple[str, datetime]]
    ) -> Dict[str, Optional[FlightStatusData]]:
        """
        Get status for multiple flights efficiently.
        
        Args:
            flight_requests: List of (flight_number, departure_date) tuples
            
        Returns:
            Dict mapping flight_number to FlightStatusData or None
        """
        pass
    
    def update_metrics(
        self, 
        success: bool, 
        response_time: float, 
        error_message: Optional[str] = None
    ):
        """Update provider performance metrics"""
        self._metrics.total_requests += 1
        
        if success:
            self._metrics.last_successful_call = datetime.utcnow()
            # Update rolling average response time
            if self._metrics.total_requests == 1:
                self._metrics.average_response_time = response_time
            else:
                self._metrics.average_response_time = (
                    (self._metrics.average_response_time * 0.9) + 
                    (response_time * 0.1)
                )
        else:
            self._metrics.failed_requests += 1
            self._metrics.last_error = error_message
        
        # Update success rate
        self._metrics.success_rate = (
            (self._metrics.total_requests - self._metrics.failed_requests) / 
            self._metrics.total_requests
        )
    
    def set_status(self, status: ProviderStatus, reason: Optional[str] = None):
        """Update provider status"""
        self.status = status
        if reason and status != ProviderStatus.AVAILABLE:
            self._metrics.last_error = reason


class ProviderError(Exception):
    """Base exception for provider-specific errors"""
    
    def __init__(self, message: str, provider_name: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.provider_name = provider_name
        self.retry_after = retry_after  # seconds to wait before retry


class RateLimitError(ProviderError):
    """Raised when provider rate limit is exceeded"""
    pass


class TimeoutError(ProviderError):
    """Raised when provider request times out"""
    pass


class AuthenticationError(ProviderError):
    """Raised when provider authentication fails"""
    pass
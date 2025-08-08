# Airline API Adapter Interface

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..types import BagStatus, BagLocation, BagTrackingRecord, APIResponse, AirlineCode


class AirlineAPIAdapter(ABC):
    """
    Abstract base class for integrating with airline baggage tracking APIs.
    
    This interface standardizes the integration with different airline systems,
    providing a unified way to access bag tracking data regardless of the
    underlying airline API implementation.
    
    Each airline implementation must provide:
    - API authentication and connection management
    - Bag status retrieval from airline systems
    - Real-time location updates
    - Error handling and retry logic
    """

    @abstractmethod
    def get_supported_airlines(self) -> List[AirlineCode]:
        """
        Get list of airline codes supported by this adapter.
        
        Returns:
            List of IATA airline codes (e.g., ["AA", "DL", "UA"])
        """
        pass

    @abstractmethod
    async def authenticate(self, airline_code: AirlineCode, credentials: Dict[str, str]) -> bool:
        """
        Authenticate with the airline's API system.
        
        Args:
            airline_code: IATA airline code
            credentials: Authentication credentials (API keys, tokens, etc.)
            
        Returns:
            True if authentication successful, False otherwise
            
        Raises:
            AuthenticationException: If credentials are invalid
            APIConnectionException: If unable to connect to airline API
        """
        pass

    @abstractmethod
    async def is_authenticated(self, airline_code: AirlineCode) -> bool:
        """
        Check if currently authenticated with the airline's API.
        
        Args:
            airline_code: IATA airline code
            
        Returns:
            True if authenticated and token is valid, False otherwise
        """
        pass

    @abstractmethod
    async def fetch_bag_status(self, bag_tag: str, airline_code: AirlineCode) -> APIResponse[BagStatus]:
        """
        Fetch current bag status from airline's system.
        
        Args:
            bag_tag: Unique bag tag identifier
            airline_code: IATA airline code
            
        Returns:
            APIResponse containing BagStatus or error information
            
        Raises:
            APINotFoundException: If bag tag is not found
            APIException: If airline API returns an error
        """
        pass

    @abstractmethod
    async def fetch_bag_location(self, bag_tag: str, airline_code: AirlineCode) -> APIResponse[BagLocation]:
        """
        Fetch current bag location from airline's system.
        
        Args:
            bag_tag: Unique bag tag identifier
            airline_code: IATA airline code
            
        Returns:
            APIResponse containing BagLocation or error information
            
        Raises:
            APINotFoundException: If bag tag is not found
            LocationUnavailableException: If location data is not available
        """
        pass

    @abstractmethod
    async def fetch_bag_history(
        self,
        bag_tag: str,
        airline_code: AirlineCode,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> APIResponse[List[BagLocation]]:
        """
        Fetch bag location history from airline's system.
        
        Args:
            bag_tag: Unique bag tag identifier
            airline_code: IATA airline code
            from_date: Start date for history (optional)
            to_date: End date for history (optional)
            
        Returns:
            APIResponse containing list of BagLocation objects
            
        Raises:
            APINotFoundException: If bag tag is not found
        """
        pass

    @abstractmethod
    async def fetch_flight_bags(
        self,
        flight_number: str,
        airline_code: AirlineCode,
        flight_date: datetime
    ) -> APIResponse[List[BagTrackingRecord]]:
        """
        Fetch all bags associated with a specific flight.
        
        Args:
            flight_number: Flight number
            airline_code: IATA airline code
            flight_date: Date of the flight
            
        Returns:
            APIResponse containing list of bag tracking records
            
        Raises:
            FlightNotFoundException: If flight is not found
        """
        pass

    @abstractmethod
    async def register_webhook(
        self,
        airline_code: AirlineCode,
        webhook_url: str,
        event_types: List[str]
    ) -> APIResponse[Dict[str, Any]]:
        """
        Register webhook for real-time bag status updates.
        
        Args:
            airline_code: IATA airline code
            webhook_url: URL to receive webhook notifications
            event_types: List of event types to subscribe to
            
        Returns:
            APIResponse containing webhook registration details
            
        Raises:
            WebhookRegistrationException: If webhook registration fails
        """
        pass

    @abstractmethod
    async def unregister_webhook(
        self,
        airline_code: AirlineCode,
        webhook_id: str
    ) -> APIResponse[bool]:
        """
        Unregister a previously registered webhook.
        
        Args:
            airline_code: IATA airline code
            webhook_id: ID of the webhook to unregister
            
        Returns:
            APIResponse indicating success or failure
        """
        pass

    @abstractmethod
    async def test_connection(self, airline_code: AirlineCode) -> APIResponse[Dict[str, Any]]:
        """
        Test connection to airline's API system.
        
        Args:
            airline_code: IATA airline code
            
        Returns:
            APIResponse containing connection test results
        """
        pass

    @abstractmethod
    def get_rate_limits(self, airline_code: AirlineCode) -> Dict[str, int]:
        """
        Get API rate limits for the airline.
        
        Args:
            airline_code: IATA airline code
            
        Returns:
            Dictionary containing rate limit information
            (e.g., {"requests_per_minute": 100, "daily_limit": 10000})
        """
        pass

    @abstractmethod
    async def get_api_health(self, airline_code: AirlineCode) -> APIResponse[Dict[str, Any]]:
        """
        Get health status of airline's API.
        
        Args:
            airline_code: IATA airline code
            
        Returns:
            APIResponse containing API health information
        """
        pass

    @abstractmethod
    def supports_real_time_updates(self, airline_code: AirlineCode) -> bool:
        """
        Check if airline supports real-time bag status updates.
        
        Args:
            airline_code: IATA airline code
            
        Returns:
            True if real-time updates are supported, False otherwise
        """
        pass

    @abstractmethod
    def get_supported_features(self, airline_code: AirlineCode) -> List[str]:
        """
        Get list of features supported by the airline's API.
        
        Args:
            airline_code: IATA airline code
            
        Returns:
            List of supported feature names
            (e.g., ["tracking", "history", "webhooks", "real_time"])
        """
        pass
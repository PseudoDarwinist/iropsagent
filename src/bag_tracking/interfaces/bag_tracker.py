# Core Bag Tracker Interface

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..types import BagStatus, BagLocation, BagTrackingRecord, APIResponse


class BagTracker(ABC):
    """
    Abstract base class for bag tracking operations.
    
    This interface defines the core functionality for tracking passenger bags
    throughout their journey, providing real-time location updates and status
    changes during normal operations and flight disruptions.
    
    Implementations must provide:
    - Real-time bag status tracking
    - Location history management  
    - Integration with airline bag systems
    - Event-driven status notifications
    """

    @abstractmethod
    async def track_bag(self, bag_tag: str, airline_code: str) -> BagTrackingRecord:
        """
        Track a bag by its tag number and airline code.
        
        Args:
            bag_tag: Unique bag tag identifier (e.g., "AA123456789")
            airline_code: IATA airline code (e.g., "AA", "DL", "UA")
            
        Returns:
            BagTrackingRecord containing current status and location history
            
        Raises:
            BagNotFoundException: If bag tag is not found in airline system
            AirlineAPIException: If airline API is unavailable or returns errors
        """
        pass

    @abstractmethod
    async def get_bag_status(self, bag_tag: str) -> BagStatus:
        """
        Get current status of a specific bag.
        
        Args:
            bag_tag: Unique bag tag identifier
            
        Returns:
            Current BagStatus (CHECKED_IN, IN_TRANSIT, ARRIVED, etc.)
            
        Raises:
            BagNotFoundException: If bag tag is not found
        """
        pass

    @abstractmethod
    async def get_bag_location(self, bag_tag: str) -> BagLocation:
        """
        Get current location of a specific bag.
        
        Args:
            bag_tag: Unique bag tag identifier
            
        Returns:
            Current BagLocation with airport code, facility, and timestamp
            
        Raises:
            BagNotFoundException: If bag tag is not found
            LocationUnavailableException: If location data is not available
        """
        pass

    @abstractmethod
    async def get_location_history(self, bag_tag: str) -> List[BagLocation]:
        """
        Get complete location history for a bag.
        
        Args:
            bag_tag: Unique bag tag identifier
            
        Returns:
            List of BagLocation objects in chronological order
            
        Raises:
            BagNotFoundException: If bag tag is not found
        """
        pass

    @abstractmethod
    async def track_multiple_bags(self, bag_tags: List[str]) -> Dict[str, BagTrackingRecord]:
        """
        Track multiple bags simultaneously.
        
        Args:
            bag_tags: List of bag tag identifiers
            
        Returns:
            Dictionary mapping bag tags to their tracking records
            
        Raises:
            AirlineAPIException: If airline APIs are unavailable
        """
        pass

    @abstractmethod
    async def register_bag_for_monitoring(
        self,
        bag_tag: str,
        airline_code: str,
        passenger_email: str,
        flight_number: str
    ) -> bool:
        """
        Register a bag for continuous monitoring and notifications.
        
        Args:
            bag_tag: Unique bag tag identifier
            airline_code: IATA airline code
            passenger_email: Email for notifications
            flight_number: Associated flight number
            
        Returns:
            True if registration successful, False otherwise
            
        Raises:
            ValidationException: If input parameters are invalid
        """
        pass

    @abstractmethod
    async def unregister_bag_monitoring(self, bag_tag: str) -> bool:
        """
        Stop monitoring a specific bag.
        
        Args:
            bag_tag: Unique bag tag identifier
            
        Returns:
            True if successfully unregistered, False if not found
        """
        pass

    @abstractmethod
    async def get_monitored_bags(self, passenger_email: str) -> List[str]:
        """
        Get all bag tags being monitored for a passenger.
        
        Args:
            passenger_email: Passenger's email address
            
        Returns:
            List of bag tag identifiers being monitored
        """
        pass

    @abstractmethod
    async def update_bag_status(
        self,
        bag_tag: str,
        new_status: BagStatus,
        location: BagLocation,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Update bag status and location (typically called by airline systems).
        
        Args:
            bag_tag: Unique bag tag identifier
            new_status: New bag status
            location: Current location information
            timestamp: When the status change occurred (defaults to now)
            
        Returns:
            True if update successful, False otherwise
            
        Raises:
            ValidationException: If status transition is invalid
        """
        pass

    @abstractmethod
    async def search_bags_by_flight(self, flight_number: str, date: datetime) -> List[BagTrackingRecord]:
        """
        Search for all bags associated with a specific flight.
        
        Args:
            flight_number: Flight number (e.g., "AA1234")
            date: Flight date
            
        Returns:
            List of bag tracking records for the flight
            
        Raises:
            FlightNotFoundException: If flight is not found
        """
        pass

    @abstractmethod
    async def get_disrupted_bags(self, flight_number: str) -> List[BagTrackingRecord]:
        """
        Get bags affected by flight disruptions (delays, cancellations).
        
        Args:
            flight_number: Disrupted flight number
            
        Returns:
            List of bag tracking records for bags needing attention
        """
        pass
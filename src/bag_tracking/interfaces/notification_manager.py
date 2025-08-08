# Notification Manager Interface

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from ..types import BagStatus, BagLocation, NotificationChannel, NotificationPriority


class NotificationManager(ABC):
    """
    Abstract base class for managing bag tracking notifications.
    
    This interface defines the notification system for keeping passengers
    informed about their bag status changes, location updates, and any
    issues that arise during transit or flight disruptions.
    
    Implementations must provide:
    - Multi-channel notification delivery (email, SMS, push)
    - Priority-based notification handling
    - Template management for different notification types
    - Delivery confirmation and retry logic
    """

    @abstractmethod
    async def send_bag_status_update(
        self,
        recipient_email: str,
        bag_tag: str,
        old_status: BagStatus,
        new_status: BagStatus,
        location: BagLocation,
        channels: List[NotificationChannel],
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[NotificationChannel, bool]:
        """
        Send bag status update notification to passenger.
        
        Args:
            recipient_email: Passenger's email address
            bag_tag: Bag tag identifier
            old_status: Previous bag status
            new_status: Current bag status
            location: Current bag location
            channels: List of notification channels to use
            priority: Notification priority level
            
        Returns:
            Dictionary mapping channels to delivery success status
            
        Raises:
            NotificationException: If all notification channels fail
        """
        pass

    @abstractmethod
    async def send_bag_delay_alert(
        self,
        recipient_email: str,
        bag_tag: str,
        expected_arrival: datetime,
        new_arrival: datetime,
        reason: str,
        channels: List[NotificationChannel]
    ) -> Dict[NotificationChannel, bool]:
        """
        Send bag delay notification to passenger.
        
        Args:
            recipient_email: Passenger's email address
            bag_tag: Bag tag identifier
            expected_arrival: Originally expected arrival time
            new_arrival: New expected arrival time
            reason: Reason for delay
            channels: List of notification channels to use
            
        Returns:
            Dictionary mapping channels to delivery success status
        """
        pass

    @abstractmethod
    async def send_bag_arrival_notification(
        self,
        recipient_email: str,
        bag_tag: str,
        arrival_location: BagLocation,
        carousel_number: Optional[str],
        channels: List[NotificationChannel]
    ) -> Dict[NotificationChannel, bool]:
        """
        Send bag arrival notification to passenger.
        
        Args:
            recipient_email: Passenger's email address
            bag_tag: Bag tag identifier
            arrival_location: Where the bag has arrived
            carousel_number: Baggage carousel number (if available)
            channels: List of notification channels to use
            
        Returns:
            Dictionary mapping channels to delivery success status
        """
        pass

    @abstractmethod
    async def send_bag_mishandling_alert(
        self,
        recipient_email: str,
        bag_tag: str,
        issue_type: str,
        description: str,
        compensation_info: Optional[Dict[str, Any]],
        channels: List[NotificationChannel]
    ) -> Dict[NotificationChannel, bool]:
        """
        Send bag mishandling alert (lost, damaged, etc.).
        
        Args:
            recipient_email: Passenger's email address
            bag_tag: Bag tag identifier
            issue_type: Type of issue (LOST, DAMAGED, DELAYED)
            description: Description of the issue
            compensation_info: Information about compensation (optional)
            channels: List of notification channels to use
            
        Returns:
            Dictionary mapping channels to delivery success status
        """
        pass

    @abstractmethod
    async def send_flight_disruption_bag_update(
        self,
        recipient_email: str,
        flight_number: str,
        bag_tags: List[str],
        disruption_type: str,
        bag_handling_plan: str,
        channels: List[NotificationChannel]
    ) -> Dict[NotificationChannel, bool]:
        """
        Send notification about bag handling during flight disruptions.
        
        Args:
            recipient_email: Passenger's email address
            flight_number: Affected flight number
            bag_tags: List of affected bag tags
            disruption_type: Type of disruption (CANCELLED, DELAYED, DIVERTED)
            bag_handling_plan: Plan for handling bags during disruption
            channels: List of notification channels to use
            
        Returns:
            Dictionary mapping channels to delivery success status
        """
        pass

    @abstractmethod
    async def register_notification_preferences(
        self,
        passenger_email: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Register passenger's notification preferences.
        
        Args:
            passenger_email: Passenger's email address
            preferences: Notification preferences (channels, times, types)
            
        Returns:
            True if preferences saved successfully, False otherwise
        """
        pass

    @abstractmethod
    async def get_notification_preferences(
        self,
        passenger_email: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get passenger's notification preferences.
        
        Args:
            passenger_email: Passenger's email address
            
        Returns:
            Dictionary containing notification preferences, None if not found
        """
        pass

    @abstractmethod
    async def update_contact_information(
        self,
        passenger_email: str,
        phone_number: Optional[str] = None,
        push_token: Optional[str] = None
    ) -> bool:
        """
        Update passenger's contact information for notifications.
        
        Args:
            passenger_email: Passenger's email address
            phone_number: Phone number for SMS (optional)
            push_token: Push notification token (optional)
            
        Returns:
            True if contact info updated successfully, False otherwise
        """
        pass

    @abstractmethod
    async def send_test_notification(
        self,
        recipient_email: str,
        channel: NotificationChannel
    ) -> bool:
        """
        Send test notification to verify delivery channel.
        
        Args:
            recipient_email: Passenger's email address
            channel: Notification channel to test
            
        Returns:
            True if test notification sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def get_notification_history(
        self,
        passenger_email: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get notification history for a passenger.
        
        Args:
            passenger_email: Passenger's email address
            from_date: Start date for history (optional)
            to_date: End date for history (optional)
            limit: Maximum number of notifications to return
            
        Returns:
            List of notification records
        """
        pass

    @abstractmethod
    async def retry_failed_notification(
        self,
        notification_id: str
    ) -> Dict[NotificationChannel, bool]:
        """
        Retry a previously failed notification.
        
        Args:
            notification_id: ID of the notification to retry
            
        Returns:
            Dictionary mapping channels to delivery success status
            
        Raises:
            NotificationNotFoundException: If notification ID is not found
        """
        pass

    @abstractmethod
    async def cancel_scheduled_notifications(
        self,
        passenger_email: str,
        bag_tag: str
    ) -> int:
        """
        Cancel any scheduled notifications for a specific bag.
        
        Args:
            passenger_email: Passenger's email address
            bag_tag: Bag tag identifier
            
        Returns:
            Number of notifications cancelled
        """
        pass

    @abstractmethod
    def get_supported_channels(self) -> List[NotificationChannel]:
        """
        Get list of supported notification channels.
        
        Returns:
            List of supported NotificationChannel values
        """
        pass

    @abstractmethod
    async def validate_contact_info(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Validate contact information format.
        
        Args:
            email: Email address to validate (optional)
            phone: Phone number to validate (optional)
            
        Returns:
            Dictionary mapping contact types to validation results
        """
        pass
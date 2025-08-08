# Test suite for bag tracking interfaces

import pytest
from abc import ABC
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock

from src.bag_tracking.interfaces.bag_tracker import BagTracker
from src.bag_tracking.interfaces.airline_api_adapter import AirlineAPIAdapter
from src.bag_tracking.interfaces.notification_manager import NotificationManager
from src.bag_tracking.types import (
    BagStatus, AirlineCode, LocationCode, NotificationChannel,
    NotificationPriority, APIResponseStatus, FacilityType,
    BagLocation, BagTrackingRecord, APIResponse
)


class TestBagTrackerInterface:
    """Test BagTracker interface definition."""
    
    def test_bag_tracker_is_abstract(self):
        """Test that BagTracker is an abstract base class."""
        assert issubclass(BagTracker, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            BagTracker()
    
    def test_bag_tracker_methods_are_abstract(self):
        """Test that all BagTracker methods are abstract."""
        # Create a partial implementation to test abstract methods
        class PartialBagTracker(BagTracker):
            pass
        
        # Should not be able to instantiate without implementing all methods
        with pytest.raises(TypeError):
            PartialBagTracker()
    
    def test_concrete_bag_tracker_implementation(self):
        """Test that a concrete implementation can be created."""
        
        class ConcreteBagTracker(BagTracker):
            async def track_bag(self, bag_tag: str, airline_code: str) -> BagTrackingRecord:
                return Mock()
            
            async def get_bag_status(self, bag_tag: str) -> BagStatus:
                return BagStatus.IN_TRANSIT
            
            async def get_bag_location(self, bag_tag: str) -> BagLocation:
                return Mock()
            
            async def get_location_history(self, bag_tag: str) -> List[BagLocation]:
                return []
            
            async def track_multiple_bags(self, bag_tags: List[str]) -> Dict[str, BagTrackingRecord]:
                return {}
            
            async def register_bag_for_monitoring(
                self, bag_tag: str, airline_code: str, passenger_email: str, flight_number: str
            ) -> bool:
                return True
            
            async def unregister_bag_monitoring(self, bag_tag: str) -> bool:
                return True
            
            async def get_monitored_bags(self, passenger_email: str) -> List[str]:
                return []
            
            async def update_bag_status(
                self, bag_tag: str, new_status: BagStatus, location: BagLocation, timestamp=None
            ) -> bool:
                return True
            
            async def search_bags_by_flight(self, flight_number: str, date: datetime) -> List[BagTrackingRecord]:
                return []
            
            async def get_disrupted_bags(self, flight_number: str) -> List[BagTrackingRecord]:
                return []
        
        # Should be able to instantiate concrete implementation
        tracker = ConcreteBagTracker()
        assert isinstance(tracker, BagTracker)


class TestAirlineAPIAdapterInterface:
    """Test AirlineAPIAdapter interface definition."""
    
    def test_airline_adapter_is_abstract(self):
        """Test that AirlineAPIAdapter is an abstract base class."""
        assert issubclass(AirlineAPIAdapter, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            AirlineAPIAdapter()
    
    def test_concrete_airline_adapter_implementation(self):
        """Test that a concrete implementation can be created."""
        
        class ConcreteAirlineAdapter(AirlineAPIAdapter):
            def get_supported_airlines(self) -> List[AirlineCode]:
                return [AirlineCode.AMERICAN, AirlineCode.DELTA]
            
            async def authenticate(self, airline_code: AirlineCode, credentials: Dict[str, str]) -> bool:
                return True
            
            async def is_authenticated(self, airline_code: AirlineCode) -> bool:
                return True
            
            async def fetch_bag_status(self, bag_tag: str, airline_code: AirlineCode) -> APIResponse[BagStatus]:
                return APIResponse(status=APIResponseStatus.SUCCESS, data=BagStatus.IN_TRANSIT)
            
            async def fetch_bag_location(self, bag_tag: str, airline_code: AirlineCode) -> APIResponse[BagLocation]:
                return APIResponse(status=APIResponseStatus.SUCCESS, data=Mock())
            
            async def fetch_bag_history(
                self, bag_tag: str, airline_code: AirlineCode, from_date=None, to_date=None
            ) -> APIResponse[List[BagLocation]]:
                return APIResponse(status=APIResponseStatus.SUCCESS, data=[])
            
            async def fetch_flight_bags(
                self, flight_number: str, airline_code: AirlineCode, flight_date: datetime
            ) -> APIResponse[List[BagTrackingRecord]]:
                return APIResponse(status=APIResponseStatus.SUCCESS, data=[])
            
            async def register_webhook(
                self, airline_code: AirlineCode, webhook_url: str, event_types: List[str]
            ) -> APIResponse[Dict[str, Any]]:
                return APIResponse(status=APIResponseStatus.SUCCESS, data={})
            
            async def unregister_webhook(
                self, airline_code: AirlineCode, webhook_id: str
            ) -> APIResponse[bool]:
                return APIResponse(status=APIResponseStatus.SUCCESS, data=True)
            
            async def test_connection(self, airline_code: AirlineCode) -> APIResponse[Dict[str, Any]]:
                return APIResponse(status=APIResponseStatus.SUCCESS, data={"status": "connected"})
            
            def get_rate_limits(self, airline_code: AirlineCode) -> Dict[str, int]:
                return {"requests_per_minute": 100, "daily_limit": 10000}
            
            async def get_api_health(self, airline_code: AirlineCode) -> APIResponse[Dict[str, Any]]:
                return APIResponse(status=APIResponseStatus.SUCCESS, data={"health": "ok"})
            
            def supports_real_time_updates(self, airline_code: AirlineCode) -> bool:
                return True
            
            def get_supported_features(self, airline_code: AirlineCode) -> List[str]:
                return ["tracking", "history", "webhooks"]
        
        # Should be able to instantiate concrete implementation
        adapter = ConcreteAirlineAdapter()
        assert isinstance(adapter, AirlineAPIAdapter)


class TestNotificationManagerInterface:
    """Test NotificationManager interface definition."""
    
    def test_notification_manager_is_abstract(self):
        """Test that NotificationManager is an abstract base class."""
        assert issubclass(NotificationManager, ABC)
        
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            NotificationManager()
    
    def test_concrete_notification_manager_implementation(self):
        """Test that a concrete implementation can be created."""
        
        class ConcreteNotificationManager(NotificationManager):
            async def send_bag_status_update(
                self, recipient_email: str, bag_tag: str, old_status: BagStatus,
                new_status: BagStatus, location: BagLocation, channels: List[NotificationChannel],
                priority=NotificationPriority.NORMAL
            ) -> Dict[NotificationChannel, bool]:
                return {channel: True for channel in channels}
            
            async def send_bag_delay_alert(
                self, recipient_email: str, bag_tag: str, expected_arrival: datetime,
                new_arrival: datetime, reason: str, channels: List[NotificationChannel]
            ) -> Dict[NotificationChannel, bool]:
                return {channel: True for channel in channels}
            
            async def send_bag_arrival_notification(
                self, recipient_email: str, bag_tag: str, arrival_location: BagLocation,
                carousel_number, channels: List[NotificationChannel]
            ) -> Dict[NotificationChannel, bool]:
                return {channel: True for channel in channels}
            
            async def send_bag_mishandling_alert(
                self, recipient_email: str, bag_tag: str, issue_type: str,
                description: str, compensation_info, channels: List[NotificationChannel]
            ) -> Dict[NotificationChannel, bool]:
                return {channel: True for channel in channels}
            
            async def send_flight_disruption_bag_update(
                self, recipient_email: str, flight_number: str, bag_tags: List[str],
                disruption_type: str, bag_handling_plan: str, channels: List[NotificationChannel]
            ) -> Dict[NotificationChannel, bool]:
                return {channel: True for channel in channels}
            
            async def register_notification_preferences(
                self, passenger_email: str, preferences: Dict[str, Any]
            ) -> bool:
                return True
            
            async def get_notification_preferences(
                self, passenger_email: str
            ) -> Dict[str, Any]:
                return {}
            
            async def update_contact_information(
                self, passenger_email: str, phone_number=None, push_token=None
            ) -> bool:
                return True
            
            async def send_test_notification(
                self, recipient_email: str, channel: NotificationChannel
            ) -> bool:
                return True
            
            async def get_notification_history(
                self, passenger_email: str, from_date=None, to_date=None, limit=100
            ) -> List[Dict[str, Any]]:
                return []
            
            async def retry_failed_notification(
                self, notification_id: str
            ) -> Dict[NotificationChannel, bool]:
                return {}
            
            async def cancel_scheduled_notifications(
                self, passenger_email: str, bag_tag: str
            ) -> int:
                return 0
            
            def get_supported_channels(self) -> List[NotificationChannel]:
                return [NotificationChannel.EMAIL, NotificationChannel.SMS]
            
            async def validate_contact_info(
                self, email=None, phone=None
            ) -> Dict[str, bool]:
                return {"email": email is not None, "phone": phone is not None}
        
        # Should be able to instantiate concrete implementation
        manager = ConcreteNotificationManager()
        assert isinstance(manager, NotificationManager)


class TestInterfaceIntegration:
    """Test how interfaces work together."""
    
    def test_interfaces_can_be_mocked(self):
        """Test that interfaces can be mocked for testing."""
        # Mock BagTracker
        mock_tracker = Mock(spec=BagTracker)
        mock_tracker.track_bag = AsyncMock(return_value=Mock())
        mock_tracker.get_bag_status = AsyncMock(return_value=BagStatus.IN_TRANSIT)
        
        assert hasattr(mock_tracker, 'track_bag')
        assert hasattr(mock_tracker, 'get_bag_status')
        
        # Mock AirlineAPIAdapter
        mock_adapter = Mock(spec=AirlineAPIAdapter)
        mock_adapter.get_supported_airlines.return_value = [AirlineCode.AMERICAN]
        mock_adapter.authenticate = AsyncMock(return_value=True)
        
        assert hasattr(mock_adapter, 'get_supported_airlines')
        assert hasattr(mock_adapter, 'authenticate')
        
        # Mock NotificationManager
        mock_notification = Mock(spec=NotificationManager)
        mock_notification.send_bag_status_update = AsyncMock(
            return_value={NotificationChannel.EMAIL: True}
        )
        
        assert hasattr(mock_notification, 'send_bag_status_update')
    
    def test_interface_method_signatures(self):
        """Test that interface methods have correct signatures."""
        # Test BagTracker method signatures
        import inspect
        
        track_bag_sig = inspect.signature(BagTracker.track_bag)
        assert 'bag_tag' in track_bag_sig.parameters
        assert 'airline_code' in track_bag_sig.parameters
        
        get_bag_status_sig = inspect.signature(BagTracker.get_bag_status)
        assert 'bag_tag' in get_bag_status_sig.parameters
        
        # Test AirlineAPIAdapter method signatures
        authenticate_sig = inspect.signature(AirlineAPIAdapter.authenticate)
        assert 'airline_code' in authenticate_sig.parameters
        assert 'credentials' in authenticate_sig.parameters
        
        # Test NotificationManager method signatures
        send_status_update_sig = inspect.signature(NotificationManager.send_bag_status_update)
        assert 'recipient_email' in send_status_update_sig.parameters
        assert 'bag_tag' in send_status_update_sig.parameters
        assert 'old_status' in send_status_update_sig.parameters
        assert 'new_status' in send_status_update_sig.parameters


if __name__ == "__main__":
    pytest.main([__file__])
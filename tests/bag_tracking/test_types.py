# Test suite for bag tracking type definitions

import pytest
from datetime import datetime, timedelta
from typing import List

from src.bag_tracking.types import (
    BagStatus, AirlineCode, LocationCode, NotificationChannel,
    NotificationPriority, APIResponseStatus, FacilityType,
    BagLocation, BagTrackingRecord, APIResponse, BagOwner,
    BagTrackingEvent, NotificationRequest, AirlineAPICredentials,
    parse_bag_tag, parse_airline_code, parse_airport_code,
    is_valid_email, is_valid_phone,
    ValidationException
)


class TestEnums:
    """Test enum definitions."""
    
    def test_bag_status_enum(self):
        """Test BagStatus enum values."""
        assert BagStatus.CHECKED_IN.value == "CHECKED_IN"
        assert BagStatus.IN_TRANSIT.value == "IN_TRANSIT"
        assert BagStatus.ARRIVED.value == "ARRIVED"
        assert BagStatus.READY_FOR_PICKUP.value == "READY_FOR_PICKUP"
        assert BagStatus.UNKNOWN.value == "UNKNOWN"
    
    def test_airline_code_enum(self):
        """Test AirlineCode enum values."""
        assert AirlineCode.AMERICAN.value == "AA"
        assert AirlineCode.DELTA.value == "DL"
        assert AirlineCode.UNITED.value == "UA"
        assert AirlineCode.LUFTHANSA.value == "LH"
        assert AirlineCode.UNKNOWN.value == "XX"
    
    def test_location_code_enum(self):
        """Test LocationCode enum values."""
        assert LocationCode.JFK.value == "JFK"
        assert LocationCode.LAX.value == "LAX"
        assert LocationCode.LHR.value == "LHR"
        assert LocationCode.CDG.value == "CDG"
        assert LocationCode.UNKNOWN.value == "XXX"
    
    def test_notification_channel_enum(self):
        """Test NotificationChannel enum values."""
        assert NotificationChannel.EMAIL.value == "EMAIL"
        assert NotificationChannel.SMS.value == "SMS"
        assert NotificationChannel.PUSH.value == "PUSH"
        assert NotificationChannel.WEBHOOK.value == "WEBHOOK"


class TestDataClasses:
    """Test data class definitions."""
    
    def test_bag_location_creation(self):
        """Test BagLocation data class creation."""
        timestamp = datetime.utcnow()
        location = BagLocation(
            airport_code=LocationCode.JFK,
            facility_type=FacilityType.CAROUSEL,
            facility_name="Baggage Claim A",
            timestamp=timestamp,
            terminal="1",
            carousel="5"
        )
        
        assert location.airport_code == LocationCode.JFK
        assert location.facility_type == FacilityType.CAROUSEL
        assert location.facility_name == "Baggage Claim A"
        assert location.timestamp == timestamp
        assert location.terminal == "1"
        assert location.carousel == "5"
    
    def test_bag_location_validation(self):
        """Test BagLocation validation."""
        timestamp = datetime.utcnow()
        
        # Should raise error if airport is UNKNOWN and no facility name
        with pytest.raises(ValueError):
            BagLocation(
                airport_code=LocationCode.UNKNOWN,
                facility_type=FacilityType.UNKNOWN,
                facility_name="",
                timestamp=timestamp
            )
    
    def test_bag_tracking_record_creation(self):
        """Test BagTrackingRecord data class creation."""
        timestamp = datetime.utcnow()
        location = BagLocation(
            airport_code=LocationCode.LAX,
            facility_type=FacilityType.CAROUSEL,
            facility_name="Baggage Claim 3",
            timestamp=timestamp
        )
        
        record = BagTrackingRecord(
            bag_tag="AA123456789",
            airline_code=AirlineCode.AMERICAN,
            current_status=BagStatus.ARRIVED,
            current_location=location,
            last_updated=timestamp,
            passenger_name="John Doe",
            flight_number="AA1234"
        )
        
        assert record.bag_tag == "AA123456789"
        assert record.airline_code == AirlineCode.AMERICAN
        assert record.current_status == BagStatus.ARRIVED
        assert record.current_location == location
        assert record.passenger_name == "John Doe"
        assert record.flight_number == "AA1234"
        assert isinstance(record.location_history, list)
        assert isinstance(record.status_history, list)
    
    def test_api_response_creation(self):
        """Test APIResponse data class creation."""
        data = {"test": "value"}
        response = APIResponse[dict](
            status=APIResponseStatus.SUCCESS,
            data=data,
            request_id="req-123"
        )
        
        assert response.status == APIResponseStatus.SUCCESS
        assert response.data == data
        assert response.request_id == "req-123"
        assert response.is_success is True
        assert response.is_error is False
        assert response.is_rate_limited is False
    
    def test_api_response_error_properties(self):
        """Test APIResponse error detection properties."""
        error_response = APIResponse[None](
            status=APIResponseStatus.ERROR,
            error_message="API Error",
            error_code="E001"
        )
        
        assert error_response.is_success is False
        assert error_response.is_error is True
        assert error_response.is_rate_limited is False
        
        rate_limit_response = APIResponse[None](
            status=APIResponseStatus.RATE_LIMITED
        )
        
        assert rate_limit_response.is_rate_limited is True
    
    def test_bag_owner_creation(self):
        """Test BagOwner data class creation."""
        owner = BagOwner(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            phone="+1-555-123-4567"
        )
        
        assert owner.email == "john.doe@example.com"
        assert owner.first_name == "John"
        assert owner.last_name == "Doe"
        assert owner.phone == "+1-555-123-4567"
        assert owner.full_name == "John Doe"
        assert isinstance(owner.notification_preferences, dict)
    
    def test_airline_api_credentials(self):
        """Test AirlineAPICredentials data class."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        past_time = datetime.utcnow() - timedelta(hours=1)
        
        # Test non-expired token
        credentials = AirlineAPICredentials(
            airline_code=AirlineCode.AMERICAN,
            access_token="token123",
            token_expires_at=future_time
        )
        assert credentials.is_token_expired is False
        
        # Test expired token
        credentials.token_expires_at = past_time
        assert credentials.is_token_expired is True
        
        # Test no expiration
        credentials.token_expires_at = None
        assert credentials.is_token_expired is False


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_parse_bag_tag(self):
        """Test bag tag parsing and validation."""
        # Valid bag tags
        assert parse_bag_tag("AA123456789") == "AA123456789"
        assert parse_bag_tag("  dl987654321  ") == "DL987654321"
        assert parse_bag_tag("ua12345678") == "UA12345678"
        
        # Invalid bag tags
        with pytest.raises(ValidationException):
            parse_bag_tag("")  # Empty
        
        with pytest.raises(ValidationException):
            parse_bag_tag("AA123")  # Too short
        
        with pytest.raises(ValidationException):
            parse_bag_tag("AA1234567890123456")  # Too long
    
    def test_parse_airline_code(self):
        """Test airline code parsing."""
        assert parse_airline_code("AA") == AirlineCode.AMERICAN
        assert parse_airline_code("dl") == AirlineCode.DELTA
        assert parse_airline_code("ua") == AirlineCode.UNITED
        assert parse_airline_code("XYZ") == AirlineCode.UNKNOWN
    
    def test_parse_airport_code(self):
        """Test airport code parsing."""
        assert parse_airport_code("JFK") == LocationCode.JFK
        assert parse_airport_code("lax") == LocationCode.LAX
        assert parse_airport_code("lhr") == LocationCode.LHR
        assert parse_airport_code("XYZ") == LocationCode.UNKNOWN
    
    def test_is_valid_email(self):
        """Test email validation."""
        # Valid emails
        assert is_valid_email("test@example.com") is True
        assert is_valid_email("user.name+tag@domain.co.uk") is True
        assert is_valid_email("test123@test-domain.org") is True
        
        # Invalid emails
        assert is_valid_email("invalid.email") is False
        assert is_valid_email("@domain.com") is False
        assert is_valid_email("test@") is False
        assert is_valid_email("test@domain") is False
    
    def test_is_valid_phone(self):
        """Test phone number validation."""
        # Valid phone numbers
        assert is_valid_phone("+1-555-123-4567") is True
        assert is_valid_phone("555-123-4567") is True
        assert is_valid_phone("+44 20 7946 0958") is True
        assert is_valid_phone("15551234567") is True
        
        # Invalid phone numbers
        assert is_valid_phone("123") is False  # Too short
        assert is_valid_phone("abc-def-ghij") is False  # Contains letters
        assert is_valid_phone("") is False  # Empty


class TestComplexScenarios:
    """Test complex scenarios and edge cases."""
    
    def test_bag_tracking_record_with_history(self):
        """Test BagTrackingRecord with location history."""
        timestamp = datetime.utcnow()
        
        # Create location history
        location1 = BagLocation(
            airport_code=LocationCode.JFK,
            facility_type=FacilityType.CHECK_IN,
            facility_name="Terminal 8 Check-in",
            timestamp=timestamp - timedelta(hours=2)
        )
        
        location2 = BagLocation(
            airport_code=LocationCode.JFK,
            facility_type=FacilityType.AIRCRAFT,
            facility_name="Gate 15",
            timestamp=timestamp - timedelta(hours=1)
        )
        
        current_location = BagLocation(
            airport_code=LocationCode.LAX,
            facility_type=FacilityType.CAROUSEL,
            facility_name="Carousel 5",
            timestamp=timestamp
        )
        
        record = BagTrackingRecord(
            bag_tag="AA123456789",
            airline_code=AirlineCode.AMERICAN,
            current_status=BagStatus.ARRIVED,
            current_location=current_location,
            last_updated=timestamp,
            location_history=[location1, location2, current_location]
        )
        
        assert len(record.location_history) == 3
        assert record.location_history[0].facility_type == FacilityType.CHECK_IN
        assert record.location_history[-1].facility_type == FacilityType.CAROUSEL
    
    def test_notification_request_creation(self):
        """Test NotificationRequest data class."""
        request = NotificationRequest(
            recipient_email="passenger@example.com",
            subject="Bag Status Update",
            message="Your bag has arrived at LAX",
            channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
            priority=NotificationPriority.HIGH,
            bag_tag="AA123456789",
            flight_number="AA1234"
        )
        
        assert request.recipient_email == "passenger@example.com"
        assert request.subject == "Bag Status Update"
        assert NotificationChannel.EMAIL in request.channels
        assert NotificationChannel.SMS in request.channels
        assert request.priority == NotificationPriority.HIGH
        assert isinstance(request.template_data, dict)


if __name__ == "__main__":
    pytest.main([__file__])
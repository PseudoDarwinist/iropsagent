# test_sms_notifications.py
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from flight_agent.models import (
    create_user, get_user_by_email, create_booking, 
    create_disruption_event, update_user_phone
)
from flight_agent.tools.communication_tools import (
    validate_phone_number, format_disruption_sms, send_manual_sms,
    update_sms_preferences, get_sms_status, send_disruption_sms,
    SMSRateLimiter
)

load_dotenv()

def test_phone_validation():
    """Test phone number validation and formatting"""
    print("=== TEST 1: Phone Number Validation ===")
    
    test_cases = [
        ("1234567890", "+11234567890"),
        ("+1234567890", "+1234567890"),
        ("(123) 456-7890", "+11234567890"),
        ("123-456-7890", "+11234567890"),
        ("+44 20 7946 0958", "+442079460958"),
        ("invalid", None),
        ("123", None)
    ]
    
    for input_phone, expected in test_cases:
        result = validate_phone_number(input_phone)
        status = "✅" if result == expected else "❌"
        print(f"{status} {input_phone} -> {result} (expected: {expected})")
    
    print("Phone validation test completed!\n")


def test_sms_preferences():
    """Test SMS preferences functionality"""
    print("=== TEST 2: SMS Preferences ===")
    
    test_email = "sms_test@example.com"
    test_phone = "+1234567890"
    
    # Create or get test user
    user = get_user_by_email(test_email)
    if not user:
        user = create_user(test_email, phone=test_phone)
        print(f"✅ Created test user: {user.user_id}")
    else:
        # Update phone if needed
        if not user.phone:
            update_user_phone(test_email, test_phone)
            print(f"✅ Updated phone for existing user: {user.user_id}")
    
    # Test enabling SMS preferences
    result = update_sms_preferences(test_email, enabled=True, urgent_only=True)
    print(f"✅ Enable SMS: {result}")
    
    # Test disabling SMS preferences
    result = update_sms_preferences(test_email, enabled=False, urgent_only=False)
    print(f"✅ Disable SMS: {result}")
    
    # Re-enable for further tests
    result = update_sms_preferences(test_email, enabled=True, urgent_only=True)
    print(f"✅ Re-enable SMS: {result}")
    
    print("SMS preferences test completed!\n")


def test_disruption_message_formatting():
    """Test disruption message formatting"""
    print("=== TEST 3: Disruption Message Formatting ===")
    
    # Create mock objects for testing
    class MockDisruption:
        def __init__(self, disruption_type, original_time=None, new_time=None):
            self.disruption_type = disruption_type
            self.original_departure = original_time
            self.new_departure = new_time
    
    class MockBooking:
        def __init__(self):
            self.flight_number = "UA1234"
            self.origin = "ORD"
            self.destination = "SFO"
    
    booking = MockBooking()
    
    # Test different disruption types
    test_cases = [
        ("CANCELLED", None, None),
        ("DELAYED", datetime.now(), datetime.now() + timedelta(hours=2)),
        ("DIVERTED", None, None),
        ("UNKNOWN", None, None)
    ]
    
    for disruption_type, orig_time, new_time in test_cases:
        disruption = MockDisruption(disruption_type, orig_time, new_time)
        message = format_disruption_sms(disruption, booking)
        print(f"✅ {disruption_type}: {message}")
    
    print("Message formatting test completed!\n")


def test_rate_limiting():
    """Test SMS rate limiting functionality"""
    print("=== TEST 4: SMS Rate Limiting ===")
    
    rate_limiter = SMSRateLimiter(max_sms_per_hour=2, max_sms_per_day=5)
    test_phone = "+1234567890"
    
    # Test initial sending (should be allowed)
    can_send = rate_limiter.can_send_sms(test_phone)
    print(f"✅ Initial send allowed: {can_send}")
    
    if can_send:
        rate_limiter.record_sms_sent(test_phone)
        print("✅ Recorded first SMS")
    
    # Test second send (should be allowed)
    can_send = rate_limiter.can_send_sms(test_phone)
    print(f"✅ Second send allowed: {can_send}")
    
    if can_send:
        rate_limiter.record_sms_sent(test_phone)
        print("✅ Recorded second SMS")
    
    # Test third send (should be blocked due to hourly limit)
    can_send = rate_limiter.can_send_sms(test_phone)
    print(f"✅ Third send blocked (expected): {not can_send}")
    
    print("Rate limiting test completed!\n")


def test_sms_system_status():
    """Test SMS system status reporting"""
    print("=== TEST 5: SMS System Status ===")
    
    status = get_sms_status()
    print("SMS System Status:")
    print(status)
    print("System status test completed!\n")


def test_disruption_sms_workflow():
    """Test complete disruption SMS workflow"""
    print("=== TEST 6: Complete Disruption SMS Workflow ===")
    
    test_email = "disruption_test@example.com"
    test_phone = "+1234567890"
    
    try:
        # Create or get test user
        user = get_user_by_email(test_email)
        if not user:
            user = create_user(test_email, phone=test_phone)
            print(f"✅ Created test user: {user.user_id}")
        
        # Enable SMS preferences
        update_sms_preferences(test_email, enabled=True, urgent_only=True)
        print("✅ Enabled SMS preferences")
        
        # Create test booking
        booking_data = {
            'pnr': 'TEST123',
            'airline': 'United',
            'flight_number': 'UA1234',
            'departure_date': datetime.now() + timedelta(hours=24),
            'origin': 'ORD',
            'destination': 'SFO',
            'class': 'Economy',
            'seat': '12A'
        }
        
        booking = create_booking(user.user_id, booking_data)
        print(f"✅ Created test booking: {booking.booking_id}")
        
        # Create high-priority disruption
        disruption_data = {
            'type': 'CANCELLED',
            'priority': 'HIGH',
            'original_departure': booking.departure_date,
            'new_departure': None
        }
        
        disruption = create_disruption_event(booking.booking_id, disruption_data)
        print(f"✅ Created disruption event: {disruption.event_id}")
        
        # Test SMS sending (will only work if Twilio is configured)
        result = send_disruption_sms(disruption.event_id)
        print(f"📱 SMS Result: {result}")
        
    except Exception as e:
        print(f"❌ Error in workflow test: {e}")
    
    print("Disruption SMS workflow test completed!\n")


def test_manual_sms():
    """Test manual SMS sending functionality"""
    print("=== TEST 7: Manual SMS Sending ===")
    
    test_email = "manual_sms_test@example.com"
    test_phone = "+1234567890"
    
    # Create or get test user
    user = get_user_by_email(test_email)
    if not user:
        user = create_user(test_email, phone=test_phone)
        print(f"✅ Created test user for manual SMS: {user.user_id}")
    
    # Test manual SMS (will only work if Twilio is configured)
    test_message = "This is a test SMS from the Flight Agent system."
    result = send_manual_sms(test_email, test_message)
    print(f"📱 Manual SMS Result: {result}")
    
    print("Manual SMS test completed!\n")


def run_all_tests():
    """Run all SMS notification tests"""
    print("🚀 Starting SMS Notification Tests...\n")
    
    test_phone_validation()
    test_sms_preferences()
    test_disruption_message_formatting()
    test_rate_limiting()
    test_sms_system_status()
    test_disruption_sms_workflow()
    test_manual_sms()
    
    print("🎉 All tests completed!")
    print("\nNote: SMS sending tests will only work if Twilio credentials are configured.")
    print("Check your .env file for TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER")


if __name__ == "__main__":
    run_all_tests()
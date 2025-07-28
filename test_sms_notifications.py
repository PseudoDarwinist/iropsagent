# test_sms_notifications.py
"""
Test script for SMS notification functionality
"""
import os
from dotenv import load_dotenv
from flight_agent.models import (
    create_user, get_user_by_email, update_user_phone, 
    enable_sms_notifications, disable_sms_notifications,
    get_user_sms_preferences
)
from flight_agent.tools.communication_tools import (
    validate_phone_number, is_phone_number_valid,
    create_disruption_sms_message, send_sms_notification,
    send_disruption_sms
)

load_dotenv()

def test_phone_validation():
    """Test phone number validation and formatting"""
    print("=== TEST 1: Phone Number Validation ===")
    
    test_cases = [
        "1234567890",        # US without country code
        "+1234567890",       # US with country code
        "11234567890",       # US with leading 1
        "+11234567890",      # US with +1
        "(123) 456-7890",    # US with formatting
        "+44 20 1234 5678",  # UK number
        "invalid",           # Invalid
        "",                  # Empty
        None                 # None
    ]
    
    for phone in test_cases:
        formatted = validate_phone_number(phone)
        valid = is_phone_number_valid(phone)
        print(f"  {phone} -> {formatted} (Valid: {valid})")
    
    print("✅ Phone validation test completed\n")


def test_sms_message_templates():
    """Test SMS message template generation"""
    print("=== TEST 2: SMS Message Templates ===")
    
    # Test different disruption types
    test_cases = [
        {
            "disruption_type": "CANCELLED",
            "flight_number": "UA1542",
            "origin": "ORD",
            "destination": "SFO",
            "original_time": "01/15 3:45PM"
        },
        {
            "disruption_type": "DELAYED",
            "flight_number": "DL2345",
            "origin": "JFK",
            "destination": "LAX",
            "original_time": "01/15 10:30AM",
            "new_time": "01/15 2:15PM"
        },
        {
            "disruption_type": "DIVERTED",
            "flight_number": "AA9876",
            "origin": "MIA",
            "destination": "SEA",
            "original_time": "01/15 6:20PM"
        }
    ]
    
    for case in test_cases:
        message = create_disruption_sms_message(**case)
        print(f"  {case['disruption_type']}: {message}")
        print(f"    Length: {len(message)} characters")
    
    print("✅ SMS template test completed\n")


def test_user_sms_preferences():
    """Test user SMS preference management"""
    print("=== TEST 3: User SMS Preferences ===")
    
    test_email = "sms_test@example.com"
    test_phone = "+1234567890"
    
    # Get or create test user
    user = get_user_by_email(test_email)
    if not user:
        user = create_user(test_email, test_phone)
        print(f"  ✅ Created test user: {user.user_id}")
    else:
        print(f"  ✅ Using existing user: {user.user_id}")
    
    # Test updating phone number
    success = update_user_phone(user.user_id, test_phone)
    print(f"  Phone update: {'✅ Success' if success else '❌ Failed'}")
    
    # Test enabling SMS notifications
    success = enable_sms_notifications(user.user_id, ["major", "minor"])
    print(f"  Enable SMS: {'✅ Success' if success else '❌ Failed'}")
    
    # Test getting preferences
    prefs = get_user_sms_preferences(user.user_id)
    print(f"  SMS Preferences: {prefs}")
    
    # Test disabling SMS notifications
    success = disable_sms_notifications(user.user_id)
    print(f"  Disable SMS: {'✅ Success' if success else '❌ Failed'}")
    
    # Test getting preferences after disabling
    prefs = get_user_sms_preferences(user.user_id)
    print(f"  SMS Preferences (after disable): {prefs}")
    
    print("✅ User SMS preferences test completed\n")


def test_sms_sending_simulation():
    """Test SMS sending functionality (simulation only)"""
    print("=== TEST 4: SMS Sending Simulation ===")
    
    # Check if Twilio credentials are configured
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")
    
    print(f"  TWILIO_ACCOUNT_SID: {'SET' if twilio_sid else 'NOT SET'}")
    print(f"  TWILIO_AUTH_TOKEN: {'SET' if twilio_token else 'NOT SET'}")
    print(f"  TWILIO_PHONE_NUMBER: {'SET' if twilio_phone else 'NOT SET'}")
    
    if not all([twilio_sid, twilio_token, twilio_phone]):
        print("  ⚠️  Twilio credentials not configured - skipping actual SMS test")
        print("  📝 To enable SMS testing, add these to your .env file:")
        print("     TWILIO_ACCOUNT_SID=your_account_sid")
        print("     TWILIO_AUTH_TOKEN=your_auth_token")
        print("     TWILIO_PHONE_NUMBER=+1xxxxxxxxxx")
    else:
        print("  ✅ Twilio credentials configured")
        
        # Test with fake user data (don't actually send)
        test_user_id = "test_user_123"
        test_phone = "+1234567890"
        test_message = "TEST: Flight UA1542 (ORD→SFO) CANCELLED. Check email for rebooking options."
        
        print(f"  Test message: {test_message}")
        print(f"  Message length: {len(test_message)} characters")
        print("  ⚠️  Not actually sending SMS in test mode")
    
    print("✅ SMS sending simulation completed\n")


def test_end_to_end_notification():
    """Test end-to-end disruption SMS notification"""
    print("=== TEST 5: End-to-End Notification Test ===")
    
    test_email = "e2e_test@example.com"
    test_phone = "+1234567890"
    
    # Create test user with SMS enabled
    user = get_user_by_email(test_email)
    if not user:
        user = create_user(test_email, test_phone)
    else:
        update_user_phone(user.user_id, test_phone)
    
    # Enable SMS notifications
    enable_sms_notifications(user.user_id, ["major"])
    
    print(f"  Test user: {user.user_id}")
    print(f"  Phone: {user.phone}")
    
    # Test sending disruption SMS
    result = send_disruption_sms(
        user_id=user.user_id,
        disruption_type="CANCELLED",
        flight_number="UA1542",
        origin="ORD",
        destination="SFO",
        original_time="01/15 3:45PM"
    )
    
    print(f"  SMS Result: {result}")
    
    if result["success"]:
        print("  ✅ SMS notification would be sent successfully")
    else:
        print(f"  ⚠️  SMS notification failed: {result['error']}")
    
    print("✅ End-to-end notification test completed\n")


def main():
    """Run all SMS notification tests"""
    print("🚀 SMS Notification System - Test Suite\n")
    
    try:
        test_phone_validation()
        test_sms_message_templates()
        test_user_sms_preferences()
        test_sms_sending_simulation()
        test_end_to_end_notification()
        
        print("✅ All SMS notification tests completed successfully!")
        print("\n📝 Next Steps:")
        print("1. Configure Twilio credentials in .env file to enable actual SMS sending")
        print("2. Test with real phone numbers in a controlled environment")
        print("3. Monitor SMS rate limits and costs in production")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
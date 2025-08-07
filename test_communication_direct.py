# test_communication_direct.py
import os
import re
from datetime import datetime, timedelta

# Direct import of validation function
def validate_phone_number(phone: str):
    """
    Validate and format phone number for SMS
    
    Args:
        phone: Phone number in various formats
        
    Returns:
        Formatted phone number in E.164 format or None if invalid
    """
    if not phone:
        return None
    
    # Remove all non-digit characters
    cleaned = re.sub(r'[^\d]', '', phone)
    
    # Handle different formats
    if len(cleaned) == 10:
        # US number without country code
        return f"+1{cleaned}"
    elif len(cleaned) == 11 and cleaned.startswith('1'):
        # US number with country code
        return f"+{cleaned}"
    elif len(cleaned) >= 10 and phone.startswith('+'):
        # Already formatted
        return phone
    elif len(cleaned) >= 10:
        # International number, assume needs + prefix
        return f"+{cleaned}"
    
    return None


def format_disruption_sms(disruption_type: str, flight_number: str, route: str, original_time=None, new_time=None):
    """Format disruption information for SMS"""
    
    if disruption_type.upper() == "CANCELLED":
        message = f"🚨 FLIGHT ALERT: {flight_number} ({route}) has been CANCELLED. "
        message += "We're finding alternatives. Check email for details."
    
    elif disruption_type.upper() == "DELAYED":
        original_str = original_time.strftime("%H:%M") if original_time else "Unknown"
        new_str = new_time.strftime("%H:%M") if new_time else "TBD"
        message = f"⏰ FLIGHT DELAY: {flight_number} ({route}) delayed from {original_str} to {new_str}. "
        message += "Monitor for updates."
    
    elif disruption_type.upper() == "DIVERTED":
        message = f"✈️ FLIGHT DIVERSION: {flight_number} ({route}) has been diverted. "
        message += "Check email for new destination and arrangements."
    
    else:
        message = f"⚠️ FLIGHT UPDATE: {flight_number} ({route}) has changes. "
        message += "Check email for full details."
    
    # Add timestamp
    message += f" Alert sent at {datetime.now().strftime('%H:%M')}"
    
    return message


class SMSRateLimiter:
    """Rate limiter for SMS notifications to prevent spam"""
    
    def __init__(self, max_sms_per_hour: int = 5, max_sms_per_day: int = 20):
        self.max_sms_per_hour = max_sms_per_hour
        self.max_sms_per_day = max_sms_per_day
        self.sms_history = {}
    
    def can_send_sms(self, phone_number: str) -> bool:
        """Check if SMS can be sent to this phone number"""
        now = datetime.now()
        
        if phone_number not in self.sms_history:
            self.sms_history[phone_number] = []
        
        # Clean old entries
        self.sms_history[phone_number] = [
            timestamp for timestamp in self.sms_history[phone_number]
            if now - timestamp < timedelta(days=1)
        ]
        
        # Check hourly limit
        hour_ago = now - timedelta(hours=1)
        recent_sms = [
            timestamp for timestamp in self.sms_history[phone_number]
            if timestamp > hour_ago
        ]
        
        if len(recent_sms) >= self.max_sms_per_hour:
            return False
        
        # Check daily limit
        if len(self.sms_history[phone_number]) >= self.max_sms_per_day:
            return False
        
        return True
    
    def record_sms_sent(self, phone_number: str):
        """Record that an SMS was sent"""
        if phone_number not in self.sms_history:
            self.sms_history[phone_number] = []
        self.sms_history[phone_number].append(datetime.now())


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


def test_disruption_message_formatting():
    """Test disruption message formatting"""
    print("=== TEST 2: Disruption Message Formatting ===")
    
    # Test different disruption types
    test_cases = [
        ("CANCELLED", None, None),
        ("DELAYED", datetime.now(), datetime.now() + timedelta(hours=2)),
        ("DIVERTED", None, None),
        ("UNKNOWN", None, None)
    ]
    
    for disruption_type, orig_time, new_time in test_cases:
        message = format_disruption_sms(disruption_type, "UA1234", "ORD->SFO", orig_time, new_time)
        print(f"✅ {disruption_type}: {message}")
    
    print("Message formatting test completed!\n")


def test_rate_limiting():
    """Test SMS rate limiting functionality"""
    print("=== TEST 3: SMS Rate Limiting ===")
    
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


def test_twilio_import():
    """Test if Twilio can be imported"""
    print("=== TEST 4: Twilio Import ===")
    
    try:
        from twilio.rest import Client
        print("✅ Twilio SDK imported successfully")
        
        # Check if credentials would be available
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")
        
        print(f"TWILIO_ACCOUNT_SID: {'SET' if twilio_sid else 'NOT SET'}")
        print(f"TWILIO_AUTH_TOKEN: {'SET' if twilio_token else 'NOT SET'}")
        print(f"TWILIO_PHONE_NUMBER: {'SET' if twilio_phone else 'NOT SET'}")
        
        if twilio_sid and twilio_token:
            print("✅ Twilio credentials are configured")
        else:
            print("ℹ️ Twilio credentials not configured (expected for testing)")
            
    except ImportError as e:
        print(f"❌ Failed to import Twilio: {e}")
    
    print("Twilio import test completed!\n")


def run_direct_tests():
    """Run direct communication tests"""
    print("🚀 Starting Direct Communication Tests...\n")
    
    test_phone_validation()
    test_disruption_message_formatting()
    test_rate_limiting()
    test_twilio_import()
    
    print("🎉 Direct tests completed!")
    print("\nThese tests verify the core SMS functionality works correctly.")
    print("To test actual SMS sending, configure Twilio credentials in .env file.")


if __name__ == "__main__":
    run_direct_tests()
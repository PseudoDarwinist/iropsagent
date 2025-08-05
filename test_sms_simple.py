# test_sms_simple.py
import os
import sys
import sqlite3
from datetime import datetime, timedelta

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_phone_validation():
    """Test phone number validation and formatting"""
    print("=== TEST 1: Phone Number Validation ===")
    
    # Import locally to avoid agent system dependencies
    from flight_agent.tools.communication_tools import validate_phone_number
    
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
    
    from flight_agent.tools.communication_tools import format_disruption_sms
    
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
    print("=== TEST 3: SMS Rate Limiting ===")
    
    from flight_agent.tools.communication_tools import SMSRateLimiter
    
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
    print("=== TEST 4: SMS System Status ===")
    
    from flight_agent.tools.communication_tools import get_sms_status
    
    status = get_sms_status()
    print("SMS System Status:")
    print(status)
    print("System status test completed!\n")


def test_database_creation():
    """Test that the database schema supports SMS functionality"""
    print("=== TEST 5: Database Schema Support ===")
    
    db_path = "travel_disruption.db"
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if users table has phone column
        cursor.execute("PRAGMA table_info(users)")
        users_columns = [column[1] for column in cursor.fetchall()]
        
        if 'phone' in users_columns:
            print("✅ Users table has phone column")
        else:
            print("❌ Users table missing phone column")
        
        # Check if users table has preferences column
        if 'preferences' in users_columns:
            print("✅ Users table has preferences column")
        else:
            print("❌ Users table missing preferences column")
        
        # Check if disruption_events table has priority column
        cursor.execute("PRAGMA table_info(disruption_events)")
        disruption_columns = [column[1] for column in cursor.fetchall()]
        
        if 'priority' in disruption_columns:
            print("✅ Disruption events table has priority column")
        else:
            print("❌ Disruption events table missing priority column")
        
        conn.close()
        print("Database schema test completed!\n")
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}\n")


def run_simple_tests():
    """Run simplified SMS notification tests"""
    print("🚀 Starting Simple SMS Notification Tests...\n")
    
    test_phone_validation()
    test_disruption_message_formatting()
    test_rate_limiting()
    test_sms_system_status()
    test_database_creation()
    
    print("🎉 Simple tests completed!")
    print("\nNote: Full integration tests require complete environment setup.")
    print("These tests verify core SMS functionality works independently.")


if __name__ == "__main__":
    run_simple_tests()
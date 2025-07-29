#!/usr/bin/env python3
"""
Test script for SMS notification functionality.

This script tests the SMS notification system for flight disruptions.
Run this after setting up Twilio credentials in your .env file.
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the flight_agent module to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flight_agent.tools.communication_tools import (
    validate_phone_number,
    format_phone_number,
    test_sms_functionality,
    process_high_priority_disruptions,
    update_user_sms_preferences,
    get_sms_status
)
from flight_agent.models import (
    create_user,
    create_booking,
    create_disruption_event,
    get_user_by_email
)

load_dotenv()

def test_phone_validation():
    """Test phone number validation and formatting."""
    print("=== Testing Phone Number Validation ===")
    
    test_numbers = [
        ("5551234567", True, "+15551234567"),  # US 10-digit
        ("15551234567", True, "+15551234567"), # US with country code
        ("555-123-4567", True, "+15551234567"), # US formatted
        ("(555) 123-4567", True, "+15551234567"), # US formatted with parens
        ("123456789", False, None),  # Too short
        ("abcd", False, None),  # Invalid
        ("", False, None),  # Empty
        ("+44 20 7946 0958", True, "+442079460958"), # UK number
    ]
    
    for phone, should_be_valid, expected_format in test_numbers:
        is_valid = validate_phone_number(phone)
        formatted = format_phone_number(phone)
        
        status = "✅" if is_valid == should_be_valid else "❌"
        print(f"{status} {phone:15} | Valid: {is_valid:5} | Formatted: {formatted}")
        
        if formatted != expected_format:
            print(f"   ⚠️  Expected: {expected_format}, Got: {formatted}")
    
    print()

def test_user_sms_setup():
    """Test setting up SMS preferences for a user."""
    print("=== Testing User SMS Setup ===")
    
    # Create test user
    test_email = "test.sms@example.com"
    test_phone = "555-123-4567"
    
    try:
        # Check if user exists, create if not
        user = get_user_by_email(test_email)
        if not user:
            user = create_user(test_email, test_phone)
            print(f"✅ Created test user: {user.email}")
        else:
            print(f"✅ Using existing test user: {user.email}")
        
        # Enable SMS notifications
        result = update_user_sms_preferences(user.user_id, True, test_phone)
        if result["success"]:
            print(f"✅ SMS preferences updated: {result}")
        else:
            print(f"❌ Failed to update SMS preferences: {result['error']}")
        
        # Check SMS status
        status = get_sms_status(user.user_id)
        if status["success"]:
            print(f"✅ SMS status: {status}")
        else:
            print(f"❌ Failed to get SMS status: {status['error']}")
        
        return user
        
    except Exception as e:
        print(f"❌ Error setting up user SMS: {e}")
        return None
    
    print()

def test_disruption_creation():
    """Test creating a disruption event."""
    print("=== Testing Disruption Event Creation ===")
    
    try:
        # Get or create test user
        test_email = "test.sms@example.com"
        user = get_user_by_email(test_email)
        
        if not user:
            print("❌ Test user not found. Run test_user_sms_setup first.")
            return None
        
        # Create test booking
        booking_data = {
            'pnr': 'TEST123',
            'airline': 'Test Airlines',
            'flight_number': 'TA123',
            'departure_date': datetime.utcnow() + timedelta(hours=2),
            'origin': 'LAX',
            'destination': 'JFK',
            'class': 'Economy',
            'seat': '12A'
        }
        
        booking = create_booking(user.user_id, booking_data)
        print(f"✅ Created test booking: {booking.flight_number}")
        
        # Create test disruption (cancellation - high priority)
        disruption = create_disruption_event(
            booking.booking_id,
            "CANCELLED",
            booking.departure_date,
            None
        )
        print(f"✅ Created disruption event: {disruption.event_id}")
        
        return disruption
        
    except Exception as e:
        print(f"❌ Error creating disruption: {e}")
        return None
    
    print()

def main():
    """Main test function."""
    print("🧪 Testing SMS Notification System")
    print("=" * 50)
    
    # Check Twilio configuration
    twilio_configured = all([
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN"),
        os.getenv("TWILIO_PHONE_NUMBER")
    ])
    
    if not twilio_configured:
        print("⚠️  Twilio credentials not fully configured.")
        print("   Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in .env")
        print("   Continuing with validation tests only...\n")
    
    # Run tests
    test_phone_validation()
    
    user = test_user_sms_setup()
    if user:
        disruption = test_disruption_creation()
    
    # Test SMS functionality (only if Twilio is configured)
    if twilio_configured and user:
        print("=== Testing SMS Functionality ===")
        
        # Test basic SMS
        result = test_sms_functionality(user.email, "🧪 Test SMS: SMS notifications working!")
        print(f"Test SMS result: {result}")
        
        # Test processing high-priority disruptions
        result = process_high_priority_disruptions()
        print(f"High-priority disruption processing result:\n{result}")
        
    elif not twilio_configured:
        print("⚠️  Skipping SMS tests - Twilio not configured")
    
    print("\n🎉 SMS notification system tests completed!")
    print("\nTo test with real SMS:")
    print("1. Set up a Twilio account and get credentials")
    print("2. Add credentials to .env file")
    print("3. Update test user with your real phone number")
    print("4. Run this script again")

if __name__ == "__main__":
    main()
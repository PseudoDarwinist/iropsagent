#!/usr/bin/env python3
"""
Test script for email notification functionality
"""
import sys
import os
from datetime import datetime, timedelta

# Add the current directory to Python path
sys.path.append('.')

from flight_agent.models import create_user, create_booking, SessionLocal
from flight_agent.tools.communication_tools import (
    test_email_configuration, 
    send_email_notification, 
    get_communication_history
)
from flight_agent.tools.monitor_tools import (
    create_disruption_event, 
    simulate_flight_disruption,
    get_disruption_events
)


def test_email_notification_system():
    """Test the complete email notification system"""
    print("🧪 Testing Email Notification System")
    print("=" * 50)
    
    # Test 1: Email configuration
    print("\n1. Testing email configuration...")
    config_result = test_email_configuration()
    print(f"   {config_result}")
    
    # Test 2: Create test user and booking
    print("\n2. Creating test user and booking...")
    try:
        test_email = "test.passenger@example.com"
        user = create_user(email=test_email, phone="+1234567890")
        print(f"   ✅ Created user: {user.user_id}")
        
        # Create test booking for tomorrow
        tomorrow = datetime.now() + timedelta(days=1)
        booking_data = {
            'pnr': 'TEST123',
            'airline': 'Test Airways',
            'flight_number': 'TA123',
            'departure_date': tomorrow,
            'origin': 'JFK',
            'destination': 'LAX',
            'class': 'Economy',
            'seat': '12A'
        }
        
        booking = create_booking(user.user_id, booking_data)
        print(f"   ✅ Created booking: {booking.booking_id}")
        
    except Exception as e:
        print(f"   ❌ Error creating test data: {e}")
        return
    
    # Test 3: Create disruption event (cancellation)
    print("\n3. Testing flight cancellation notification...")
    try:
        result = create_disruption_event(
            booking_id=booking.booking_id,
            disruption_type="CANCELLED",
            original_departure=tomorrow.isoformat()
        )
        print(f"   {result}")
    except Exception as e:
        print(f"   ❌ Error creating cancellation: {e}")
    
    # Test 4: Create disruption event (delay)
    print("\n4. Testing flight delay notification...")
    try:
        new_departure = tomorrow + timedelta(hours=3)
        result = create_disruption_event(
            booking_id=booking.booking_id,
            disruption_type="DELAYED",
            original_departure=tomorrow.isoformat(),
            new_departure=new_departure.isoformat()
        )
        print(f"   {result}")
    except Exception as e:
        print(f"   ❌ Error creating delay: {e}")
    
    # Test 5: Check communication history
    print("\n5. Checking communication history...")
    try:
        history = get_communication_history(user_id=user.user_id)
        print(f"   {history}")
    except Exception as e:
        print(f"   ❌ Error retrieving history: {e}")
    
    # Test 6: Check disruption events
    print("\n6. Checking disruption events...")
    try:
        events = get_disruption_events(user_id=user.user_id)
        print(f"   {events}")
    except Exception as e:
        print(f"   ❌ Error retrieving disruption events: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 Email notification system test completed!")
    print("\nTo test with real email delivery:")
    print("1. Set SMTP_USERNAME and SMTP_PASSWORD in your environment")
    print("2. Update test email address to a real one")
    print("3. Run this script again")


def test_simulation():
    """Test the flight simulation functionality"""
    print("\n\n🎭 Testing Flight Disruption Simulation")
    print("=" * 50)
    
    # Test simulate_flight_disruption
    print("\n1. Simulating flight cancellation...")
    try:
        result = simulate_flight_disruption("TA123", "CANCELLED")
        print(f"   {result}")
    except Exception as e:
        print(f"   ❌ Error simulating disruption: {e}")


if __name__ == "__main__":
    print("Flight Agent Email Notification Test Suite")
    print("=" * 60)
    
    # Check if email credentials are configured
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_username or not smtp_password:
        print("\n⚠️  WARNING: Email credentials not configured")
        print("Email notifications will be logged but not actually sent.")
        print("To test real email delivery, set these environment variables:")
        print("  - SMTP_USERNAME (your email)")
        print("  - SMTP_PASSWORD (your app password)")
        print("  - SMTP_SERVER (default: smtp.gmail.com)")
        print("  - SMTP_PORT (default: 587)")
    else:
        print(f"\n✅ Email configured for: {smtp_username}")
    
    # Run tests
    test_email_notification_system()
    test_simulation()
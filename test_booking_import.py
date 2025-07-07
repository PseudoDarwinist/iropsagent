# test_booking_import.py
import os
from dotenv import load_dotenv
from flight_agent.models import create_user, get_user_by_email, get_upcoming_bookings
from flight_agent.booking_import import sync_user_bookings

load_dotenv()

def test_database_setup():
    """Test 1: Create a user and verify database is working"""
    print("=== TEST 1: Database Setup ===")
    
    test_email = "test@example.com"
    
    # Check if user already exists
    user = get_user_by_email(test_email)
    if not user:
        # Create test user if it doesn't exist
        user = create_user(test_email, phone="+1234567890")
        print(f"✅ Created user: {user.user_id}")
    else:
        print(f"✅ User already exists: {user.user_id}")
    
    # Retrieve user to confirm
    retrieved_user = get_user_by_email(test_email)
    print(f"✅ Retrieved user: {retrieved_user.email}")
    
    print("Database setup successful!\n")


def test_manual_booking_creation():
    """Test 2: Manually create a booking"""
    print("=== TEST 2: Manual Booking Creation ===")
    
    from flight_agent.models import create_booking
    from datetime import datetime, timedelta
    
    # Get test user
    user = get_user_by_email("test@example.com")
    
    # Create test booking
    test_booking = {
        'pnr': 'ABC123',
        'airline': 'United',
        'flight_number': 'UA1542',
        'departure_date': datetime.now() + timedelta(days=3),
        'origin': 'ORD',
        'destination': 'SFO',
        'class': 'Economy',
        'seat': '23A'
    }
    
    booking = create_booking(user.user_id, test_booking)
    print(f"✅ Created booking: {booking.booking_id}")
    print(f"   Flight: {booking.flight_number}")
    print(f"   Route: {booking.origin} → {booking.destination}")
    print(f"   Date: {booking.departure_date}\n")


def test_email_import():
    """Test 3: Import bookings from email"""
    print("=== TEST 3: Email Import ===")
    
    # Get email credentials from environment
    email = input("Enter your email address: ")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    
    if not app_password:
        print("⚠️  GMAIL_APP_PASSWORD not found in .env file")
        print("To get an app password:")
        print("1. Go to https://myaccount.google.com/security")
        print("2. Enable 2-factor authentication")
        print("3. Generate an app-specific password")
        print("4. Add it to your .env file")
        return
    
    print(f"Importing bookings for {email}...")
    count = sync_user_bookings(email, app_password)
    print(f"✅ Imported {count} bookings\n")


def test_view_bookings():
    """Test 4: View all bookings in database"""
    print("=== TEST 4: View All Bookings ===")
    
    bookings = get_upcoming_bookings()
    
    if not bookings:
        print("No upcoming bookings found")
        return
    
    for booking in bookings:
        print(f"📅 {booking.flight_number}: {booking.origin} → {booking.destination}")
        print(f"   Date: {booking.departure_date}")
        print(f"   PNR: {booking.pnr}")
        print(f"   Status: {booking.status}")
        print()


def main():
    """Run all tests"""
    print("🚀 Travel Disruption Booking System - Test Suite\n")
    
    # Test 1: Database
    test_database_setup()
    
    # Test 2: Manual booking
    test_manual_booking_creation()
    
    # Test 3: Email import (optional)
    choice = input("Do you want to test email import? (y/n): ")
    if choice.lower() == 'y':
        test_email_import()
    
    # Test 4: View bookings
    test_view_bookings()
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    main()
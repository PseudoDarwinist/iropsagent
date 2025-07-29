# test_communication.py
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flight_agent.models import (
    create_user, get_user_by_email, create_booking, create_disruption_event,
    create_communication_log, SessionLocal, CommunicationLog
)
from flight_agent.tools.communication_tools import (
    send_email_notification, notify_flight_disruption, 
    send_rebooking_options_notification, render_email_template
)

load_dotenv()

def test_database_setup():
    """Test 1: Verify communication tables are created"""
    print("=== TEST 1: Database Setup with Communication Tables ===")
    
    db = SessionLocal()
    try:
        # Try to query communication logs to verify table exists
        logs = db.query(CommunicationLog).count()
        print(f"✅ CommunicationLog table exists with {logs} records")
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False
    finally:
        db.close()
    
    print("Database setup successful!\n")
    return True


def test_email_template_rendering():
    """Test 2: Test email template rendering"""
    print("=== TEST 2: Email Template Rendering ===")
    
    # Test cancellation template
    context = {
        'flight_number': 'UA1542',
        'origin': 'ORD',
        'destination': 'SFO',
        'original_departure': 'Monday, February 5, 2025 at 10:30 AM',
        'pnr': 'ABC123',
        'passenger_name': 'John'
    }
    
    try:
        subject, html = render_email_template('flight_cancelled', context)
        print(f"✅ Cancellation template rendered successfully")
        print(f"   Subject: {subject}")
        print(f"   HTML length: {len(html)} characters")
    except Exception as e:
        print(f"❌ Template rendering failed: {e}")
        return False
    
    # Test delay template with additional context
    context.update({
        'new_departure': 'Monday, February 5, 2025 at 2:30 PM',
        'original_departure': datetime.now() + timedelta(hours=24),
        'new_departure': datetime.now() + timedelta(hours=28)
    })
    
    try:
        subject, html = render_email_template('flight_delayed', context)
        print(f"✅ Delay template rendered successfully")
        print(f"   Subject: {subject}")
    except Exception as e:
        print(f"❌ Delay template rendering failed: {e}")
        return False
    
    print("Template rendering successful!\n")
    return True


def test_create_test_disruption():
    """Test 3: Create test booking and disruption event"""
    print("=== TEST 3: Create Test Disruption Event ===")
    
    test_email = "test.passenger@example.com"
    
    # Create or get test user
    user = get_user_by_email(test_email)
    if not user:
        user = create_user(test_email, phone="+1234567890")
        print(f"✅ Created test user: {user.user_id}")
    else:
        print(f"✅ Using existing user: {user.user_id}")
    
    # Create test booking
    test_booking_data = {
        'pnr': 'TEST123',
        'airline': 'United Airlines',
        'flight_number': 'UA9999',
        'departure_date': datetime.now() + timedelta(days=2),
        'origin': 'ORD',
        'destination': 'SFO',
        'class': 'Economy',
        'seat': '15A'
    }
    
    try:
        booking = create_booking(user.user_id, test_booking_data)
        print(f"✅ Created test booking: {booking.booking_id}")
        print(f"   Flight: {booking.flight_number} ({booking.origin} → {booking.destination})")
    except Exception as e:
        print(f"❌ Booking creation failed: {e}")
        return None, None
    
    # Create disruption event
    disruption_data = {
        'type': 'CANCELLED',
        'original_departure': booking.departure_date,
        'new_departure': None,
        'rebooking_options': [
            {
                'flight_number': 'UA1001',
                'departure_time': 'Monday, February 5, 2025 at 6:00 PM',
                'arrival_time': 'Monday, February 5, 2025 at 9:30 PM',
                'duration': '5h 30m',
                'stops': 'Direct'
            },
            {
                'flight_number': 'AA2002',
                'departure_time': 'Tuesday, February 6, 2025 at 8:00 AM',
                'arrival_time': 'Tuesday, February 6, 2025 at 11:15 AM',
                'duration': '5h 15m',
                'stops': 'Direct'
            }
        ]
    }
    
    try:
        disruption = create_disruption_event(booking.booking_id, disruption_data)
        print(f"✅ Created disruption event: {disruption.event_id}")
        print(f"   Type: {disruption.disruption_type}")
    except Exception as e:
        print(f"❌ Disruption creation failed: {e}")
        return booking, None
    
    print("Test data creation successful!\n")
    return booking, disruption


def test_communication_logging():
    """Test 4: Test communication logging"""
    print("=== TEST 4: Communication Logging ===")
    
    test_email = "test.passenger@example.com"
    user = get_user_by_email(test_email)
    
    if not user:
        print("❌ Test user not found. Run test 3 first.")
        return False
    
    # Create test communication log
    comm_data = {
        'type': 'EMAIL',
        'template': 'flight_cancelled',
        'recipient': user.email,
        'subject': 'Test Flight Cancellation',
        'content': '<html><body>Test email content</body></html>',
        'status': 'SENT'
    }
    
    try:
        log = create_communication_log(user.user_id, comm_data)
        print(f"✅ Created communication log: {log.log_id}")
        print(f"   Type: {log.communication_type}")
        print(f"   Status: {log.status}")
        print(f"   Recipient: {log.recipient}")
    except Exception as e:
        print(f"❌ Communication logging failed: {e}")
        return False
    
    print("Communication logging successful!\n")
    return True


def test_email_notification():
    """Test 5: Test email notification (without actually sending)"""
    print("=== TEST 5: Email Notification Test ===")
    
    test_email = "test.passenger@example.com"
    user = get_user_by_email(test_email)
    
    if not user:
        print("❌ Test user not found. Run test 3 first.")
        return False
    
    # Test context for email
    context = {
        'flight_number': 'UA9999',
        'origin': 'ORD',
        'destination': 'SFO',
        'original_departure': 'Wednesday, February 7, 2025 at 2:00 PM',
        'pnr': 'TEST123',
        'passenger_name': 'Test Passenger'
    }
    
    try:
        result = send_email_notification(
            user_id=user.user_id,
            template_name='flight_cancelled',
            context=context
        )
        print(f"✅ Email notification result: {result}")
        
        # Check if communication was logged
        db = SessionLocal()
        recent_log = db.query(CommunicationLog).filter(
            CommunicationLog.user_id == user.user_id
        ).order_by(CommunicationLog.created_at.desc()).first()
        
        if recent_log:
            print(f"✅ Communication logged: {recent_log.status}")
            print(f"   Template: {recent_log.template_used}")
            print(f"   Subject: {recent_log.subject}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Email notification failed: {e}")
        return False
    
    print("Email notification test successful!\n")
    return True


def test_disruption_notification():
    """Test 6: Test complete disruption notification workflow"""
    print("=== TEST 6: Disruption Notification Workflow ===")
    
    # Get test data from previous test
    test_email = "test.passenger@example.com"
    user = get_user_by_email(test_email)
    
    if not user:
        print("❌ Test user not found. Run test 3 first.")
        return False
    
    # Find the test disruption event
    db = SessionLocal()
    try:
        from flight_agent.models import DisruptionEvent, Booking
        
        disruption = db.query(DisruptionEvent).join(Booking).filter(
            Booking.user_id == user.user_id,
            Booking.flight_number == 'UA9999'
        ).first()
        
        if not disruption:
            print("❌ Test disruption not found. Run test 3 first.")
            return False
        
        print(f"✅ Found test disruption: {disruption.event_id}")
        
        # Test the complete notification workflow
        result = notify_flight_disruption(disruption.event_id)
        print(f"✅ Disruption notification result: {result}")
        
        # Verify the disruption was marked as notified
        db.refresh(disruption)
        if disruption.user_notified:
            print(f"✅ Disruption marked as notified")
        else:
            print(f"⚠️  Disruption not marked as notified")
        
    except Exception as e:
        print(f"❌ Disruption notification workflow failed: {e}")
        return False
    finally:
        db.close()
    
    print("Disruption notification workflow successful!\n")
    return True


def test_rebooking_notification():
    """Test 7: Test rebooking options notification"""
    print("=== TEST 7: Rebooking Options Notification ===")
    
    # Get test data
    test_email = "test.passenger@example.com"
    user = get_user_by_email(test_email)
    
    if not user:
        print("❌ Test user not found. Run test 3 first.")
        return False
    
    # Find the test disruption event
    db = SessionLocal()
    try:
        from flight_agent.models import DisruptionEvent, Booking
        
        disruption = db.query(DisruptionEvent).join(Booking).filter(
            Booking.user_id == user.user_id,
            Booking.flight_number == 'UA9999'
        ).first()
        
        if not disruption:
            print("❌ Test disruption not found. Run test 3 first.")
            return False
        
        # Test rebooking options notification
        result = send_rebooking_options_notification(disruption.event_id)
        print(f"✅ Rebooking notification result: {result}")
        
    except Exception as e:
        print(f"❌ Rebooking notification failed: {e}")
        return False
    finally:
        db.close()
    
    print("Rebooking notification successful!\n")
    return True


def view_communication_logs():
    """View all communication logs"""
    print("=== COMMUNICATION LOGS SUMMARY ===")
    
    db = SessionLocal()
    try:
        logs = db.query(CommunicationLog).order_by(CommunicationLog.created_at.desc()).limit(10).all()
        
        if not logs:
            print("No communication logs found")
            return
        
        for log in logs:
            print(f"📧 {log.log_id}")
            print(f"   Type: {log.communication_type}")
            print(f"   Template: {log.template_used}")
            print(f"   Recipient: {log.recipient}")
            print(f"   Status: {log.status}")
            print(f"   Created: {log.created_at}")
            if log.error_message:
                print(f"   Error: {log.error_message}")
            print()
        
    except Exception as e:
        print(f"❌ Failed to retrieve logs: {e}")
    finally:
        db.close()


def main():
    """Run all communication tests"""
    print("🚀 Flight Agent Communication System - Test Suite\n")
    
    # Run tests in sequence
    tests = [
        test_database_setup,
        test_email_template_rendering,
        test_create_test_disruption,
        test_communication_logging,
        test_email_notification,
        test_disruption_notification,
        test_rebooking_notification
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ {test.__name__} failed\n")
        except Exception as e:
            print(f"❌ {test.__name__} crashed: {e}\n")
    
    print(f"\n📊 Test Results: {passed}/{len(tests)} tests passed")
    
    # Show communication logs
    view_communication_logs()
    
    print("\n✅ Communication system testing completed!")
    
    # Show configuration notes
    print("\n📝 Configuration Notes:")
    print("• To send actual emails, set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env")
    print("• Default SMTP settings are for Gmail (smtp.gmail.com:587)")
    print("• All notifications are logged in the database regardless of email configuration")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Core test script for user communication preferences functionality.
Tests database models and core preference logic without ADK dependencies.

Usage:
    python3 test_preferences_core.py
"""
import sys
from datetime import datetime
from flight_agent.models import SessionLocal, User, create_user, get_user_by_email, get_user_by_id


def test_user_model_preferences():
    """Test the User model with new communication preference fields"""
    print("Testing User model with communication preferences...")
    
    # Create a test user directly with the database
    db = SessionLocal()
    try:
        test_email = f"model_test_{datetime.now().timestamp()}@example.com"
        
        user = User(
            user_id=f"test_user_{datetime.now().timestamp()}",
            email=test_email,
            phone="+1234567890",
            enable_email_notifications=True,
            enable_sms_notifications=False,
            notification_frequency="immediate",
            notification_types={
                "flight_delays": True,
                "flight_cancellations": True,
                "gate_changes": True,
                "rebooking_options": True,
                "check_in_reminders": False
            },
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            timezone="UTC"
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Verify the user was created with preferences
        assert user.enable_email_notifications == True
        assert user.enable_sms_notifications == False
        assert user.notification_frequency == "immediate"
        assert user.notification_types["flight_delays"] == True
        assert user.quiet_hours_start == "22:00"
        assert user.timezone == "UTC"
        
        print("✓ User model with communication preferences works")
        
        # Test updating preferences
        user.notification_frequency = "hourly"
        user.notification_types["gate_changes"] = False
        user.last_preference_update = datetime.utcnow()
        
        db.commit()
        db.refresh(user)
        
        assert user.notification_frequency == "hourly"
        assert user.notification_types["gate_changes"] == False
        assert user.last_preference_update is not None
        
        print("✓ User preference updates work")
        
        return True
        
    finally:
        db.close()


def test_preference_validation_logic():
    """Test preference validation without ADK tools"""
    print("Testing preference validation logic...")
    
    import re
    
    def validate_email(email):
        pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        return pattern.match(email) is not None
    
    def validate_phone(phone):
        clean_phone = re.sub(r'[^\d]', '', phone)
        return 10 <= len(clean_phone) <= 15
    
    def validate_time_format(time_str):
        pattern = re.compile(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
        return pattern.match(time_str) is not None
    
    def validate_frequency(frequency):
        return frequency in ["immediate", "hourly", "daily"]
    
    # Test email validation
    assert validate_email("test@example.com") == True
    assert validate_email("invalid-email") == False
    print("✓ Email validation works")
    
    # Test phone validation
    assert validate_phone("+1234567890") == True
    assert validate_phone("123-456-7890") == True
    assert validate_phone("123") == False
    print("✓ Phone validation works")
    
    # Test time format validation
    assert validate_time_format("22:00") == True
    assert validate_time_format("07:30") == True
    assert validate_time_format("25:00") == False
    assert validate_time_format("22:60") == False
    print("✓ Time format validation works")
    
    # Test frequency validation
    assert validate_frequency("immediate") == True
    assert validate_frequency("hourly") == True
    assert validate_frequency("invalid") == False
    print("✓ Frequency validation works")
    
    return True


def test_database_operations():
    """Test database operations for preferences"""
    print("Testing database operations...")
    
    # Test creating user with preferences
    test_email = f"db_test_{datetime.now().timestamp()}@example.com"
    user = create_user(email=test_email, phone="+1987654321")
    
    assert user is not None
    assert user.email == test_email
    print("✓ User creation works")
    
    # Test retrieving user
    retrieved_user = get_user_by_email(test_email)
    assert retrieved_user is not None
    assert retrieved_user.user_id == user.user_id
    print("✓ User retrieval by email works")
    
    retrieved_user_by_id = get_user_by_id(user.user_id)
    assert retrieved_user_by_id is not None
    assert retrieved_user_by_id.email == test_email
    print("✓ User retrieval by ID works")
    
    # Test updating user preferences in database
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.user_id == user.user_id).first()
        
        # Update preferences
        db_user.enable_email_notifications = False
        db_user.notification_frequency = "daily"
        db_user.notification_types = {
            "flight_delays": False,
            "flight_cancellations": True,
            "gate_changes": False,
            "rebooking_options": True,
            "check_in_reminders": True
        }
        db_user.last_preference_update = datetime.utcnow()
        
        db.commit()
        db.refresh(db_user)
        
        # Verify updates
        assert db_user.enable_email_notifications == False
        assert db_user.notification_frequency == "daily"
        assert db_user.notification_types["flight_delays"] == False
        assert db_user.notification_types["check_in_reminders"] == True
        
        print("✓ Database preference updates work")
        
    finally:
        db.close()
    
    return True


def test_default_preference_values():
    """Test that default preference values are correctly set"""
    print("Testing default preference values...")
    
    test_email = f"defaults_test_{datetime.now().timestamp()}@example.com"
    user = create_user(email=test_email)
    
    # Check that defaults are applied (from the model definition)
    assert user.enable_email_notifications == True  # Default should be True
    assert user.enable_sms_notifications == False   # Default should be False
    assert user.notification_frequency == "immediate"  # Default
    
    print("✓ Default preference values are correctly applied")
    
    return True


def run_core_tests():
    """Run all core preference tests"""
    print("=== Running Core Communication Preferences Tests ===\n")
    
    tests = [
        test_user_model_preferences,
        test_preference_validation_logic,
        test_database_operations,
        test_default_preference_values
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
            print(f"✓ {test.__name__} PASSED\n")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} FAILED: {e}\n")
    
    print(f"=== Test Results ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("🎉 All core tests passed!")
        return True
    else:
        print(f"❌ {failed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_core_tests()
    sys.exit(0 if success else 1)
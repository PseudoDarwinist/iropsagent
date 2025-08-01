#!/usr/bin/env python3
"""
Test script for user communication preferences functionality.
This script tests the preference tools, API, and validation logic.

Usage:
    python3 test_preferences.py
"""
import sys
from datetime import datetime
from flight_agent.models import create_user, get_user_by_email
from flight_agent.tools.preference_tools import (
    get_user_preferences,
    update_user_preferences,
    validate_notification_settings,
    get_default_preferences
)
from flight_agent.api.preference_api import PreferenceAPI


def test_default_preferences():
    """Test getting default preferences"""
    print("Testing default preferences...")
    
    defaults = get_default_preferences()
    
    assert "enable_email_notifications" in defaults
    assert "enable_sms_notifications" in defaults
    assert "notification_frequency" in defaults
    assert "notification_types" in defaults
    assert "quiet_hours_start" in defaults
    assert "quiet_hours_end" in defaults
    assert "timezone" in defaults
    
    assert defaults["notification_frequency"] in ["immediate", "hourly", "daily"]
    assert isinstance(defaults["notification_types"], dict)
    
    print("✓ Default preferences test passed")
    return True


def test_user_creation_and_preferences():
    """Test creating a user and managing their preferences"""
    print("Testing user creation and preference management...")
    
    # Create a test user
    test_email = f"test_{datetime.now().timestamp()}@example.com"
    user = create_user(email=test_email, phone="+1234567890")
    
    assert user is not None
    assert user.email == test_email
    print(f"✓ Created test user: {user.user_id}")
    
    # Test getting preferences for the new user
    prefs = get_user_preferences(user.user_id)
    assert "user_id" in prefs
    assert prefs["user_id"] == user.user_id
    assert prefs["email"] == test_email
    print("✓ Retrieved user preferences")
    
    # Test updating preferences
    new_prefs = {
        "enable_email_notifications": True,
        "enable_sms_notifications": True,
        "notification_frequency": "hourly",
        "notification_types": {
            "flight_delays": True,
            "flight_cancellations": True,
            "gate_changes": False,
            "rebooking_options": True,
            "check_in_reminders": False
        },
        "quiet_hours_start": "23:00",
        "quiet_hours_end": "06:00",
        "timezone": "America/New_York"
    }
    
    result = update_user_preferences(user.user_id, new_prefs)
    assert result.get("success") == True
    print("✓ Updated user preferences")
    
    # Verify the updates
    updated_prefs = get_user_preferences(user.user_id)
    assert updated_prefs["notification_frequency"] == "hourly"
    assert updated_prefs["quiet_hours_start"] == "23:00"
    assert updated_prefs["timezone"] == "America/New_York"
    assert updated_prefs["notification_types"]["flight_delays"] == True
    assert updated_prefs["notification_types"]["gate_changes"] == False
    print("✓ Verified preference updates")
    
    return True


def test_preference_validation():
    """Test preference validation logic"""
    print("Testing preference validation...")
    
    # Test valid email
    result = validate_notification_settings(
        email="valid@example.com",
        phone="+1234567890",
        enable_email=True,
        enable_sms=True
    )
    assert result.get("valid") == True
    print("✓ Valid email and phone validation passed")
    
    # Test invalid email
    result = validate_notification_settings(
        email="invalid-email",
        enable_email=True
    )
    assert "error" in result
    print("✓ Invalid email validation failed as expected")
    
    # Test missing email when email notifications enabled
    result = validate_notification_settings(
        email=None,
        enable_email=True
    )
    assert "error" in result
    print("✓ Missing email validation failed as expected")
    
    # Test invalid phone
    result = validate_notification_settings(
        phone="123",  # Too short
        enable_sms=True
    )
    assert "error" in result
    print("✓ Invalid phone validation failed as expected")
    
    return True


def test_preference_api():
    """Test the preference API class"""
    print("Testing PreferenceAPI...")
    
    # Create a test user
    test_email = f"api_test_{datetime.now().timestamp()}@example.com"
    user = create_user(email=test_email, phone="+1987654321")
    
    # Test API methods
    prefs = PreferenceAPI.get_preferences(user.user_id)
    assert "user_id" in prefs
    print("✓ API get_preferences works")
    
    # Test API update
    new_prefs = {
        "notification_frequency": "daily",
        "enable_sms_notifications": True
    }
    result = PreferenceAPI.update_preferences(user.user_id, new_prefs)
    assert result.get("success") == True
    print("✓ API update_preferences works")
    
    # Test get by email
    prefs_by_email = PreferenceAPI.get_preferences_by_email(test_email)
    assert prefs_by_email["user_id"] == user.user_id
    print("✓ API get_preferences_by_email works")
    
    return True


def test_invalid_preference_updates():
    """Test handling of invalid preference updates"""
    print("Testing invalid preference updates...")
    
    # Create a test user
    test_email = f"invalid_test_{datetime.now().timestamp()}@example.com"
    user = create_user(email=test_email)
    
    # Test invalid notification frequency
    invalid_prefs = {
        "notification_frequency": "invalid_frequency"
    }
    result = update_user_preferences(user.user_id, invalid_prefs)
    assert "error" in result
    print("✓ Invalid frequency rejected")
    
    # Test invalid time format
    invalid_prefs = {
        "quiet_hours_start": "25:00"  # Invalid hour
    }
    result = update_user_preferences(user.user_id, invalid_prefs)
    assert "error" in result
    print("✓ Invalid time format rejected")
    
    # Test invalid notification type
    invalid_prefs = {
        "notification_types": {
            "invalid_type": True
        }
    }
    result = update_user_preferences(user.user_id, invalid_prefs)
    assert "error" in result
    print("✓ Invalid notification type rejected")
    
    return True


def run_all_tests():
    """Run all preference tests"""
    print("=== Running Communication Preferences Tests ===\n")
    
    tests = [
        test_default_preferences,
        test_user_creation_and_preferences,
        test_preference_validation,
        test_preference_api,
        test_invalid_preference_updates
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
        print("🎉 All tests passed!")
        return True
    else:
        print(f"❌ {failed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
# flight_agent/tools/preference_tools.py
import re
from datetime import datetime
from typing import Dict, Any, Optional
from google.adk.tools import tool
from ..models import SessionLocal, User, get_user_by_id, get_user_by_email


@tool
def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """Get user communication preferences"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {"error": "User not found"}
        
        return {
            "user_id": user.user_id,
            "email": user.email,
            "phone": user.phone,
            "enable_email_notifications": user.enable_email_notifications,
            "enable_sms_notifications": user.enable_sms_notifications,
            "notification_frequency": user.notification_frequency,
            "notification_types": user.notification_types,
            "quiet_hours_start": user.quiet_hours_start,
            "quiet_hours_end": user.quiet_hours_end,
            "timezone": user.timezone,
            "last_preference_update": user.last_preference_update.isoformat() if user.last_preference_update else None
        }
    finally:
        db.close()


@tool
def update_user_preferences(user_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
    """Update user communication preferences"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {"error": "User not found"}
        
        # Validate preferences before updating
        validation_result = _validate_preferences(preferences, user.email, user.phone)
        if validation_result.get("error"):
            return validation_result
        
        # Update preferences
        if "enable_email_notifications" in preferences:
            user.enable_email_notifications = preferences["enable_email_notifications"]
        
        if "enable_sms_notifications" in preferences:
            user.enable_sms_notifications = preferences["enable_sms_notifications"]
        
        if "notification_frequency" in preferences:
            user.notification_frequency = preferences["notification_frequency"]
        
        if "notification_types" in preferences:
            # Merge with existing notification types
            if user.notification_types:
                user.notification_types.update(preferences["notification_types"])
            else:
                user.notification_types = preferences["notification_types"]
        
        if "quiet_hours_start" in preferences:
            user.quiet_hours_start = preferences["quiet_hours_start"]
        
        if "quiet_hours_end" in preferences:
            user.quiet_hours_end = preferences["quiet_hours_end"]
        
        if "timezone" in preferences:
            user.timezone = preferences["timezone"]
        
        user.last_preference_update = datetime.utcnow()
        
        db.commit()
        db.refresh(user)
        
        return {
            "success": True,
            "message": "Preferences updated successfully",
            "updated_preferences": {
                "enable_email_notifications": user.enable_email_notifications,
                "enable_sms_notifications": user.enable_sms_notifications,
                "notification_frequency": user.notification_frequency,
                "notification_types": user.notification_types,
                "quiet_hours_start": user.quiet_hours_start,
                "quiet_hours_end": user.quiet_hours_end,
                "timezone": user.timezone
            }
        }
    
    except Exception as e:
        db.rollback()
        return {"error": f"Failed to update preferences: {str(e)}"}
    finally:
        db.close()


@tool
def validate_notification_settings(email: str = None, phone: str = None, 
                                 enable_email: bool = False, enable_sms: bool = False) -> Dict[str, Any]:
    """Validate email and SMS notification settings"""
    return _validate_notification_contact_info(email, phone, enable_email, enable_sms)


@tool
def get_default_preferences() -> Dict[str, Any]:
    """Get default communication preferences for new users"""
    return {
        "enable_email_notifications": True,
        "enable_sms_notifications": False,
        "notification_frequency": "immediate",
        "notification_types": {
            "flight_delays": True,
            "flight_cancellations": True,
            "gate_changes": True,
            "rebooking_options": True,
            "check_in_reminders": False
        },
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "07:00", 
        "timezone": "UTC"
    }


def _validate_preferences(preferences: Dict[str, Any], user_email: str = None, user_phone: str = None) -> Dict[str, Any]:
    """Internal validation function for preference data"""
    
    # Validate notification frequency
    if "notification_frequency" in preferences:
        valid_frequencies = ["immediate", "hourly", "daily"]
        if preferences["notification_frequency"] not in valid_frequencies:
            return {"error": f"Invalid notification frequency. Must be one of: {', '.join(valid_frequencies)}"}
    
    # Validate quiet hours format
    time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    
    if "quiet_hours_start" in preferences:
        if not time_pattern.match(preferences["quiet_hours_start"]):
            return {"error": "Invalid quiet hours start time. Use HH:MM format (24-hour)"}
    
    if "quiet_hours_end" in preferences:
        if not time_pattern.match(preferences["quiet_hours_end"]):
            return {"error": "Invalid quiet hours end time. Use HH:MM format (24-hour)"}
    
    # Validate notification types
    if "notification_types" in preferences:
        valid_types = ["flight_delays", "flight_cancellations", "gate_changes", 
                      "rebooking_options", "check_in_reminders"]
        for notification_type in preferences["notification_types"]:
            if notification_type not in valid_types:
                return {"error": f"Invalid notification type '{notification_type}'. Valid types: {', '.join(valid_types)}"}
    
    # Validate contact information for enabled notifications
    enable_email = preferences.get("enable_email_notifications", False)
    enable_sms = preferences.get("enable_sms_notifications", False)
    
    contact_validation = _validate_notification_contact_info(
        user_email, user_phone, enable_email, enable_sms
    )
    if contact_validation.get("error"):
        return contact_validation
    
    return {"valid": True}


def _validate_notification_contact_info(email: str = None, phone: str = None, 
                                       enable_email: bool = False, enable_sms: bool = False) -> Dict[str, Any]:
    """Validate contact information for notifications"""
    
    if enable_email and not email:
        return {"error": "Email address is required to enable email notifications"}
    
    if enable_email and email:
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if not email_pattern.match(email):
            return {"error": "Invalid email address format"}
    
    if enable_sms and not phone:
        return {"error": "Phone number is required to enable SMS notifications"}
    
    if enable_sms and phone:
        # Basic phone validation - remove common formatting and check for reasonable length
        clean_phone = re.sub(r'[^\d]', '', phone)
        if len(clean_phone) < 10 or len(clean_phone) > 15:
            return {"error": "Invalid phone number. Must be 10-15 digits"}
    
    return {"valid": True}


@tool 
def get_user_preferences_by_email(email: str) -> Dict[str, Any]:
    """Get user communication preferences by email address"""
    user = get_user_by_email(email)
    if not user:
        return {"error": "User not found"}
    
    return get_user_preferences(user.user_id)


@tool
def update_user_preferences_by_email(email: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
    """Update user communication preferences by email address"""
    user = get_user_by_email(email)
    if not user:
        return {"error": "User not found"}
    
    return update_user_preferences(user.user_id, preferences)
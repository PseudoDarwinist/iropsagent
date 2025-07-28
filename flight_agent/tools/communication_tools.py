# flight_agent/tools/communication_tools.py
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from dotenv import load_dotenv
from ..models import SessionLocal, User

load_dotenv()

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Rate limiting configuration
SMS_RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
SMS_RATE_LIMIT_COUNT = 5  # Maximum 5 SMS per hour per user
sms_rate_limits = {}  # In-memory rate limiting store

# Initialize Twilio client
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("Twilio client initialized successfully")
    except Exception as e:
        print(f"ERROR initializing Twilio client: {e}")
else:
    print("WARNING: Twilio credentials not found in environment variables")


def validate_phone_number(phone: str) -> Optional[str]:
    """
    Validate and format phone number to E.164 format.
    
    Args:
        phone: Phone number in various formats
        
    Returns:
        Formatted phone number in E.164 format or None if invalid
    """
    if not phone:
        return None
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Handle different phone number formats
    if len(digits_only) == 10:
        # US number without country code
        return f"+1{digits_only}"
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        # US number with country code
        return f"+{digits_only}"
    elif len(digits_only) >= 10 and len(digits_only) <= 15:
        # International number (assuming it already includes country code)
        return f"+{digits_only}"
    
    return None


def is_phone_number_valid(phone: str) -> bool:
    """
    Check if a phone number is valid.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid, False otherwise
    """
    return validate_phone_number(phone) is not None


def check_sms_rate_limit(user_id: str) -> bool:
    """
    Check if user has exceeded SMS rate limits.
    
    Args:
        user_id: User ID to check
        
    Returns:
        True if within rate limits, False if exceeded
    """
    current_time = time.time()
    
    if user_id not in sms_rate_limits:
        sms_rate_limits[user_id] = []
    
    # Clean old entries outside the rate limit window
    sms_rate_limits[user_id] = [
        timestamp for timestamp in sms_rate_limits[user_id]
        if current_time - timestamp < SMS_RATE_LIMIT_WINDOW
    ]
    
    # Check if user has exceeded rate limit
    if len(sms_rate_limits[user_id]) >= SMS_RATE_LIMIT_COUNT:
        return False
    
    # Add current timestamp
    sms_rate_limits[user_id].append(current_time)
    return True


def create_disruption_sms_message(disruption_type: str, flight_number: str, 
                                origin: str, destination: str, 
                                original_time: str, new_time: str = None) -> str:
    """
    Create SMS message for flight disruption.
    
    Args:
        disruption_type: Type of disruption (CANCELLED, DELAYED, DIVERTED)
        flight_number: Flight number
        origin: Origin airport code
        destination: Destination airport code
        original_time: Original departure time
        new_time: New departure time (for delays)
        
    Returns:
        Formatted SMS message
    """
    base_msg = f"FLIGHT ALERT: {flight_number} ({origin}→{destination})"
    
    if disruption_type == "CANCELLED":
        return f"{base_msg} CANCELLED. Check email for rebooking options. Reply STOP to opt out."
    
    elif disruption_type == "DELAYED":
        if new_time:
            return f"{base_msg} DELAYED. New departure: {new_time}. Check email for updates. Reply STOP to opt out."
        else:
            return f"{base_msg} DELAYED. Check email for new departure time. Reply STOP to opt out."
    
    elif disruption_type == "DIVERTED":
        return f"{base_msg} DIVERTED. Check email for new destination details. Reply STOP to opt out."
    
    else:
        return f"{base_msg} STATUS CHANGED. Check email for details. Reply STOP to opt out."


def send_sms_notification(user_id: str, phone_number: str, message: str) -> Dict[str, any]:
    """
    Send SMS notification to user.
    
    Args:
        user_id: User ID for rate limiting
        phone_number: Phone number to send to
        message: SMS message content
        
    Returns:
        Dictionary with success status and details
    """
    # Validate Twilio client
    if not twilio_client:
        return {
            "success": False,
            "error": "Twilio client not initialized. Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables."
        }
    
    if not TWILIO_PHONE_NUMBER:
        return {
            "success": False,
            "error": "TWILIO_PHONE_NUMBER not configured in environment variables."
        }
    
    # Validate phone number
    formatted_phone = validate_phone_number(phone_number)
    if not formatted_phone:
        return {
            "success": False,
            "error": f"Invalid phone number format: {phone_number}"
        }
    
    # Check rate limits
    if not check_sms_rate_limit(user_id):
        return {
            "success": False,
            "error": f"SMS rate limit exceeded for user {user_id}. Maximum {SMS_RATE_LIMIT_COUNT} SMS per hour."
        }
    
    try:
        # Send SMS via Twilio
        message_obj = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=formatted_phone
        )
        
        return {
            "success": True,
            "message_sid": message_obj.sid,
            "status": message_obj.status,
            "phone_number": formatted_phone
        }
        
    except TwilioException as e:
        return {
            "success": False,
            "error": f"Twilio API error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error sending SMS: {str(e)}"
        }


def send_disruption_sms(user_id: str, disruption_type: str, flight_number: str,
                       origin: str, destination: str, original_time: str,
                       new_time: str = None) -> Dict[str, any]:
    """
    Send SMS notification for flight disruption.
    
    Args:
        user_id: User ID
        disruption_type: Type of disruption
        flight_number: Flight number
        origin: Origin airport code
        destination: Destination airport code
        original_time: Original departure time
        new_time: New departure time (for delays)
        
    Returns:
        Dictionary with success status and details
    """
    db = SessionLocal()
    try:
        # Get user from database
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {
                "success": False,
                "error": f"User {user_id} not found in database"
            }
        
        # Check if user has SMS notifications enabled
        sms_preferences = user.preferences.get("sms_notifications", {})
        if not sms_preferences.get("enabled", False):
            return {
                "success": False,
                "error": "SMS notifications disabled for user"
            }
        
        # Check if user has phone number
        if not user.phone:
            return {
                "success": False,
                "error": "No phone number on file for user"
            }
        
        # Check disruption severity preferences
        severity_preferences = sms_preferences.get("severity_levels", ["major"])
        disruption_severity = "major" if disruption_type in ["CANCELLED", "DIVERTED"] else "minor"
        
        if disruption_severity not in severity_preferences:
            return {
                "success": False,
                "error": f"SMS notifications disabled for {disruption_severity} disruptions"
            }
        
        # Create and send SMS message
        message = create_disruption_sms_message(
            disruption_type, flight_number, origin, destination, 
            original_time, new_time
        )
        
        result = send_sms_notification(user_id, user.phone, message)
        
        # Log the attempt
        if result["success"]:
            print(f"✅ SMS sent to {user_id}: {message}")
        else:
            print(f"❌ Failed to send SMS to {user_id}: {result['error']}")
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        db.close()


def get_user_sms_preferences(user_id: str) -> Dict[str, any]:
    """
    Get user's SMS notification preferences.
    
    Args:
        user_id: User ID
        
    Returns:
        Dictionary with SMS preferences
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {"error": f"User {user_id} not found"}
        
        return user.preferences.get("sms_notifications", {
            "enabled": False,
            "severity_levels": ["major"],
            "quiet_hours": {"enabled": False, "start": "22:00", "end": "08:00"}
        })
        
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    finally:
        db.close()


def update_user_sms_preferences(user_id: str, sms_preferences: Dict[str, any]) -> bool:
    """
    Update user's SMS notification preferences.
    
    Args:
        user_id: User ID
        sms_preferences: New SMS preferences
        
    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return False
        
        # Update SMS preferences
        if not user.preferences:
            user.preferences = {}
        
        user.preferences["sms_notifications"] = sms_preferences
        db.commit()
        
        print(f"✅ Updated SMS preferences for {user_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating SMS preferences: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()
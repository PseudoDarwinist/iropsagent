# flight_agent/tools/communication_tools.py
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from dotenv import load_dotenv
from ..models import SessionLocal, User, DisruptionEvent, Booking, get_unnotified_high_priority_disruptions, mark_disruption_sms_sent

load_dotenv()

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Rate limiting configuration (max 5 SMS per user per hour)
SMS_RATE_LIMIT = 5
SMS_RATE_WINDOW = 3600  # 1 hour in seconds

# In-memory rate limiting store (in production, use Redis or database)
_sms_rate_limiter = {}

def get_twilio_client() -> Optional[Client]:
    """Initialize and return Twilio client if credentials are available."""
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        print("Warning: Twilio credentials not fully configured")
        return None
    
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        return client
    except Exception as e:
        print(f"Error initializing Twilio client: {e}")
        return None

def validate_phone_number(phone: str) -> bool:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not phone:
        return False
    
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', phone)
    
    # Check if it's a valid length (10-15 digits)
    if len(cleaned) < 10 or len(cleaned) > 15:
        return False
    
    # For US numbers, ensure they start with 1 or have 10 digits
    if len(cleaned) == 10:
        return True
    elif len(cleaned) == 11 and cleaned.startswith('1'):
        return True
    elif len(cleaned) > 11:
        # International numbers
        return True
    
    return False

def format_phone_number(phone: str) -> Optional[str]:
    """
    Format phone number to E.164 format for Twilio.
    
    Args:
        phone: Raw phone number string
        
    Returns:
        Formatted phone number or None if invalid
    """
    if not validate_phone_number(phone):
        return None
    
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', phone)
    
    # Add country code if missing
    if len(cleaned) == 10:
        # Assume US number
        cleaned = '1' + cleaned
    
    return '+' + cleaned

def check_sms_rate_limit(user_id: str) -> bool:
    """
    Check if user has exceeded SMS rate limit.
    
    Args:
        user_id: User ID to check
        
    Returns:
        True if within rate limit, False if exceeded
    """
    current_time = time.time()
    
    if user_id not in _sms_rate_limiter:
        _sms_rate_limiter[user_id] = []
    
    # Clean old timestamps outside the rate window
    user_timestamps = _sms_rate_limiter[user_id]
    user_timestamps[:] = [ts for ts in user_timestamps if current_time - ts < SMS_RATE_WINDOW]
    
    # Check if under rate limit
    if len(user_timestamps) >= SMS_RATE_LIMIT:
        return False
    
    # Add current timestamp
    user_timestamps.append(current_time)
    return True

def create_disruption_sms_message(disruption_event: DisruptionEvent, booking: Booking) -> str:
    """
    Create concise SMS message for flight disruption.
    
    Args:
        disruption_event: DisruptionEvent instance
        booking: Booking instance
        
    Returns:
        Formatted SMS message
    """
    disruption_type = disruption_event.disruption_type.upper()
    flight_number = booking.flight_number
    route = f"{booking.origin}-{booking.destination}"
    
    if disruption_type == "CANCELLED":
        message = f"🚨 URGENT: Flight {flight_number} ({route}) has been CANCELLED. "
        message += "We're finding alternatives. Check app for rebooking options."
        
    elif disruption_type == "DELAYED":
        if disruption_event.new_departure:
            new_time = disruption_event.new_departure.strftime("%I:%M %p")
            message = f"⏰ Flight {flight_number} ({route}) DELAYED to {new_time}. "
            message += "Monitor for updates."
        else:
            message = f"⏰ Flight {flight_number} ({route}) is DELAYED. "
            message += "New time TBD. Check app for updates."
            
    elif disruption_type == "DIVERTED":
        message = f"✈️ Flight {flight_number} ({route}) has been DIVERTED. "
        message += "Check app for new arrival details."
        
    else:
        message = f"⚠️ Flight {flight_number} ({route}) status changed. "
        message += "Check app for details."
    
    # Add footer with opt-out info
    message += " Reply STOP to opt out."
    
    return message

def send_sms_notification(user_id: str, message: str) -> Dict[str, any]:
    """
    Send SMS notification to user.
    
    Args:
        user_id: User ID to send SMS to
        message: SMS message content
        
    Returns:
        Dict with success status and details
    """
    db = SessionLocal()
    try:
        # Get user from database
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {"success": False, "error": "User not found"}
        
        # Check if user has SMS enabled and phone number
        preferences = user.preferences or {}
        if not preferences.get("sms_notifications_enabled", False):
            return {"success": False, "error": "SMS notifications disabled for user"}
        
        if not user.phone:
            return {"success": False, "error": "No phone number on file"}
        
        # Format phone number
        formatted_phone = format_phone_number(user.phone)
        if not formatted_phone:
            return {"success": False, "error": "Invalid phone number format"}
        
        # Check rate limit
        if not check_sms_rate_limit(user_id):
            return {"success": False, "error": "SMS rate limit exceeded"}
        
        # Get Twilio client
        client = get_twilio_client()
        if not client:
            return {"success": False, "error": "SMS service not configured"}
        
        # Send SMS
        try:
            sms_message = client.messages.create(
                body=message,
                from_=TWILIO_PHONE_NUMBER,
                to=formatted_phone
            )
            
            return {
                "success": True,
                "message_sid": sms_message.sid,
                "phone_number": formatted_phone,
                "sent_at": datetime.utcnow().isoformat()
            }
            
        except TwilioException as e:
            return {"success": False, "error": f"Twilio error: {str(e)}"}
            
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
    finally:
        db.close()

def send_disruption_sms(disruption_event_id: str) -> Dict[str, any]:
    """
    Send SMS notification for a specific disruption event.
    
    Args:
        disruption_event_id: ID of the disruption event
        
    Returns:
        Dict with success status and details
    """
    db = SessionLocal()
    try:
        # Get disruption event and related booking
        disruption_event = db.query(DisruptionEvent).filter(
            DisruptionEvent.event_id == disruption_event_id
        ).first()
        
        if not disruption_event:
            return {"success": False, "error": "Disruption event not found"}
        
        booking = db.query(Booking).filter(
            Booking.booking_id == disruption_event.booking_id
        ).first()
        
        if not booking:
            return {"success": False, "error": "Booking not found"}
        
        # Check if this is a high-priority disruption
        if not is_high_priority_disruption(disruption_event):
            return {"success": False, "error": "Not a high-priority disruption"}
        
        # Create SMS message
        message = create_disruption_sms_message(disruption_event, booking)
        
        # Send SMS
        result = send_sms_notification(booking.user_id, message)
        
        # Update disruption event if SMS sent successfully
        if result["success"]:
            disruption_event.user_notified = True
            disruption_event.sms_sent = True
            db.commit()
        
        return result
        
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
    finally:
        db.close()

def is_high_priority_disruption(disruption_event: DisruptionEvent) -> bool:
    """
    Determine if a disruption event is high priority and requires SMS notification.
    
    Args:
        disruption_event: DisruptionEvent instance
        
    Returns:
        True if high priority, False otherwise
    """
    # Always high priority: cancellations
    if disruption_event.disruption_type == "CANCELLED":
        return True
    
    # High priority: diversions
    if disruption_event.disruption_type == "DIVERTED":
        return True
    
    # High priority: delays of 2+ hours or same-day departures
    if disruption_event.disruption_type == "DELAYED":
        if disruption_event.original_departure and disruption_event.new_departure:
            delay_hours = (disruption_event.new_departure - disruption_event.original_departure).total_seconds() / 3600
            
            # Delays of 2+ hours are high priority
            if delay_hours >= 2:
                return True
            
            # Same-day departures with any delay are high priority
            if disruption_event.original_departure.date() == datetime.utcnow().date():
                return True
    
    return False

def update_user_sms_preferences(user_id: str, sms_enabled: bool, phone: str = None) -> Dict[str, any]:
    """
    Update user's SMS notification preferences.
    
    Args:
        user_id: User ID
        sms_enabled: Whether to enable SMS notifications
        phone: Optional phone number to update
        
    Returns:
        Dict with success status and details
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {"success": False, "error": "User not found"}
        
        # Update phone number if provided
        if phone is not None:
            formatted_phone = format_phone_number(phone) if phone else None
            if phone and not formatted_phone:
                return {"success": False, "error": "Invalid phone number format"}
            user.phone = formatted_phone
        
        # Update preferences
        preferences = user.preferences or {}
        preferences["sms_notifications_enabled"] = sms_enabled
        user.preferences = preferences
        
        db.commit()
        
        return {
            "success": True,
            "sms_enabled": sms_enabled,
            "phone_number": user.phone
        }
        
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
    finally:
        db.close()

def get_sms_status(user_id: str) -> Dict[str, any]:
    """
    Get user's SMS notification status and remaining rate limit.
    
    Args:
        user_id: User ID
        
    Returns:
        Dict with SMS status information
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {"success": False, "error": "User not found"}
        
        preferences = user.preferences or {}
        sms_enabled = preferences.get("sms_notifications_enabled", False)
        
        # Calculate remaining rate limit
        current_time = time.time()
        user_timestamps = _sms_rate_limiter.get(user_id, [])
        recent_sms = [ts for ts in user_timestamps if current_time - ts < SMS_RATE_WINDOW]
        remaining_sms = max(0, SMS_RATE_LIMIT - len(recent_sms))
        
        return {
            "success": True,
            "sms_enabled": sms_enabled,
            "phone_number": user.phone,
            "remaining_sms_today": remaining_sms,
            "sms_rate_limit": SMS_RATE_LIMIT,
            "rate_limit_window_hours": SMS_RATE_WINDOW / 3600
        }
        
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
    finally:
        db.close()

def process_high_priority_disruptions() -> str:
    """
    Process all unnotified high-priority disruption events and send SMS notifications.
    
    This function should be called periodically to check for new high-priority 
    disruptions and send SMS alerts.
    
    Returns:
        Summary of SMS notifications sent
    """
    try:
        # Get all high-priority disruptions that haven't been SMS notified
        disruptions = get_unnotified_high_priority_disruptions()
        
        if not disruptions:
            return "No high-priority disruptions requiring SMS notification found."
        
        results = []
        successful_sms = 0
        failed_sms = 0
        
        for disruption in disruptions:
            result = send_disruption_sms(disruption.event_id)
            
            if result["success"]:
                successful_sms += 1
                # Mark as SMS sent in database
                mark_disruption_sms_sent(disruption.event_id)
                results.append(f"✅ SMS sent for {disruption.disruption_type} disruption (Event: {disruption.event_id[:8]})")
            else:
                failed_sms += 1
                results.append(f"❌ SMS failed for {disruption.disruption_type} disruption: {result['error']}")
        
        summary = f"SMS Notification Summary:\n"
        summary += f"• Processed {len(disruptions)} high-priority disruptions\n"
        summary += f"• Successfully sent: {successful_sms} SMS\n"
        summary += f"• Failed: {failed_sms} SMS\n\n"
        summary += "Details:\n" + "\n".join(results)
        
        return summary
        
    except Exception as e:
        return f"Error processing high-priority disruptions: {str(e)}"

def test_sms_functionality(user_email: str, test_message: str = None) -> str:
    """
    Test SMS functionality by sending a test message to a user.
    
    Args:
        user_email: Email of user to send test SMS to
        test_message: Optional custom test message
        
    Returns:
        Status message about the test SMS
    """
    from ..models import get_user_by_email
    
    try:
        # Get user
        user = get_user_by_email(user_email)
        if not user:
            return f"User with email {user_email} not found."
        
        # Use default test message if none provided
        if not test_message:
            test_message = "🧪 Test SMS from Flight Agent: Your SMS notifications are working correctly! Reply STOP to opt out."
        
        # Send test SMS
        result = send_sms_notification(user.user_id, test_message)
        
        if result["success"]:
            return f"✅ Test SMS sent successfully to {result['phone_number']} (Message SID: {result['message_sid']})"
        else:
            return f"❌ Test SMS failed: {result['error']}"
            
    except Exception as e:
        return f"Error testing SMS functionality: {str(e)}"
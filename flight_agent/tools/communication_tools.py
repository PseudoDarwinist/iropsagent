import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from twilio.rest import Client
from dotenv import load_dotenv
from ..models import SessionLocal, User, DisruptionEvent, Booking

# Load environment variables
load_dotenv()

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Rate limiting storage (in production, use Redis or database)
sms_rate_limit = {}

# Initialize Twilio client
try:
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("Twilio client initialized successfully")
    else:
        twilio_client = None
        print("Twilio credentials not found in environment variables")
except Exception as e:
    print(f"ERROR initializing Twilio client: {e}")
    twilio_client = None


class SMSRateLimiter:
    """Rate limiter for SMS notifications to prevent spam"""
    
    def __init__(self, max_sms_per_hour: int = 5, max_sms_per_day: int = 20):
        self.max_sms_per_hour = max_sms_per_hour
        self.max_sms_per_day = max_sms_per_day
    
    def can_send_sms(self, phone_number: str) -> bool:
        """Check if SMS can be sent to this phone number"""
        now = datetime.now()
        
        if phone_number not in sms_rate_limit:
            sms_rate_limit[phone_number] = []
        
        # Clean old entries
        sms_rate_limit[phone_number] = [
            timestamp for timestamp in sms_rate_limit[phone_number]
            if now - timestamp < timedelta(days=1)
        ]
        
        # Check hourly limit
        hour_ago = now - timedelta(hours=1)
        recent_sms = [
            timestamp for timestamp in sms_rate_limit[phone_number]
            if timestamp > hour_ago
        ]
        
        if len(recent_sms) >= self.max_sms_per_hour:
            return False
        
        # Check daily limit
        if len(sms_rate_limit[phone_number]) >= self.max_sms_per_day:
            return False
        
        return True
    
    def record_sms_sent(self, phone_number: str):
        """Record that an SMS was sent"""
        if phone_number not in sms_rate_limit:
            sms_rate_limit[phone_number] = []
        sms_rate_limit[phone_number].append(datetime.now())


def validate_phone_number(phone: str) -> Optional[str]:
    """
    Validate and format phone number for SMS
    
    Args:
        phone: Phone number in various formats
        
    Returns:
        Formatted phone number in E.164 format or None if invalid
    """
    if not phone:
        return None
    
    # Remove all non-digit characters
    cleaned = re.sub(r'[^\d]', '', phone)
    
    # Handle different formats
    if len(cleaned) == 10:
        # US number without country code
        return f"+1{cleaned}"
    elif len(cleaned) == 11 and cleaned.startswith('1'):
        # US number with country code
        return f"+{cleaned}"
    elif len(cleaned) >= 10 and cleaned.startswith('+'):
        # Already formatted
        return phone
    elif len(cleaned) >= 10:
        # International number, assume needs + prefix
        return f"+{cleaned}"
    
    return None


def format_disruption_sms(disruption_event: DisruptionEvent, booking: Booking) -> str:
    """
    Format disruption information for SMS
    
    Args:
        disruption_event: The disruption event
        booking: The associated booking
        
    Returns:
        Formatted SMS message
    """
    disruption_type = disruption_event.disruption_type.upper()
    flight_number = booking.flight_number
    route = f"{booking.origin}->{booking.destination}"
    
    if disruption_type == "CANCELLED":
        message = f"🚨 FLIGHT ALERT: {flight_number} ({route}) has been CANCELLED. "
        message += "We're finding alternatives. Check email for details."
    
    elif disruption_type == "DELAYED":
        original_time = disruption_event.original_departure.strftime("%H:%M") if disruption_event.original_departure else "Unknown"
        new_time = disruption_event.new_departure.strftime("%H:%M") if disruption_event.new_departure else "TBD"
        message = f"⏰ FLIGHT DELAY: {flight_number} ({route}) delayed from {original_time} to {new_time}. "
        message += "Monitor for updates."
    
    elif disruption_type == "DIVERTED":
        message = f"✈️ FLIGHT DIVERSION: {flight_number} ({route}) has been diverted. "
        message += "Check email for new destination and arrangements."
    
    else:
        message = f"⚠️ FLIGHT UPDATE: {flight_number} ({route}) has changes. "
        message += "Check email for full details."
    
    # Add timestamp
    message += f" Alert sent at {datetime.now().strftime('%H:%M')}"
    
    return message


def send_sms_notification(phone_number: str, message: str, user_id: str = None) -> Dict[str, any]:
    """
    Send SMS notification using Twilio
    
    Args:
        phone_number: Phone number to send SMS to
        message: SMS message content
        user_id: Optional user ID for logging
        
    Returns:
        Dictionary with success status and details
    """
    if not twilio_client:
        return {
            "success": False,
            "error": "Twilio client not initialized. Check credentials."
        }
    
    if not TWILIO_PHONE_NUMBER:
        return {
            "success": False,
            "error": "Twilio phone number not configured"
        }
    
    # Validate phone number
    validated_phone = validate_phone_number(phone_number)
    if not validated_phone:
        return {
            "success": False,
            "error": f"Invalid phone number format: {phone_number}"
        }
    
    # Check rate limits
    rate_limiter = SMSRateLimiter()
    if not rate_limiter.can_send_sms(validated_phone):
        return {
            "success": False,
            "error": "SMS rate limit exceeded for this phone number"
        }
    
    try:
        # Send SMS
        message_obj = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=validated_phone
        )
        
        # Record SMS sent for rate limiting
        rate_limiter.record_sms_sent(validated_phone)
        
        print(f"SMS sent successfully. SID: {message_obj.sid}, To: {validated_phone}")
        
        return {
            "success": True,
            "message_sid": message_obj.sid,
            "to": validated_phone,
            "status": message_obj.status
        }
        
    except Exception as e:
        error_msg = f"Error sending SMS: {str(e)}"
        print(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


def send_disruption_sms(disruption_event_id: str) -> str:
    """
    Send SMS notification for a flight disruption
    
    Args:
        disruption_event_id: ID of the disruption event
        
    Returns:
        Status message about SMS sending
    """
    db = SessionLocal()
    try:
        # Get disruption event with related booking and user
        disruption = db.query(DisruptionEvent).filter(
            DisruptionEvent.event_id == disruption_event_id
        ).first()
        
        if not disruption:
            return f"Disruption event {disruption_event_id} not found"
        
        booking = disruption.booking
        if not booking:
            return f"No booking found for disruption {disruption_event_id}"
        
        user = db.query(User).filter(User.user_id == booking.user_id).first()
        if not user:
            return f"No user found for booking {booking.booking_id}"
        
        # Check if user has SMS preferences enabled
        preferences = user.preferences or {}
        sms_preferences = preferences.get('sms', {})
        
        if not sms_preferences.get('enabled', False):
            return f"SMS notifications disabled for user {user.email}"
        
        if not user.phone:
            return f"No phone number on file for user {user.email}"
        
        # Check if this is a high-priority disruption
        priority_disruptions = ['CANCELLED', 'DIVERTED']
        if disruption.disruption_type.upper() not in priority_disruptions:
            # For delays, check if it's significant (>30 minutes)
            if disruption.disruption_type.upper() == 'DELAYED':
                if disruption.original_departure and disruption.new_departure:
                    delay_minutes = (disruption.new_departure - disruption.original_departure).total_seconds() / 60
                    if delay_minutes < 30:  # Less than 30 minute delay
                        return f"Delay of {int(delay_minutes)} minutes is below SMS threshold"
        
        # Format and send SMS
        sms_message = format_disruption_sms(disruption, booking)
        result = send_sms_notification(user.phone, sms_message, user.user_id)
        
        if result["success"]:
            # Update disruption event to mark user as notified
            disruption.user_notified = True
            db.commit()
            return f"✅ SMS sent to {user.email} ({result['to']}) - SID: {result['message_sid']}"
        else:
            return f"❌ Failed to send SMS to {user.email}: {result['error']}"
            
    except Exception as e:
        return f"Error sending disruption SMS: {str(e)}"
    finally:
        db.close()


def send_manual_sms(user_email: str, message: str) -> str:
    """
    Send manual SMS to a user (for testing or admin purposes)
    
    Args:
        user_email: Email of the user to send SMS to
        message: Message content
        
    Returns:
        Status message
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            return f"User with email {user_email} not found"
        
        if not user.phone:
            return f"No phone number on file for user {user_email}"
        
        result = send_sms_notification(user.phone, message, user.user_id)
        
        if result["success"]:
            return f"✅ SMS sent to {user_email} ({result['to']}) - SID: {result['message_sid']}"
        else:
            return f"❌ Failed to send SMS to {user_email}: {result['error']}"
            
    except Exception as e:
        return f"Error sending manual SMS: {str(e)}"
    finally:
        db.close()


def update_sms_preferences(user_email: str, enabled: bool = True, urgent_only: bool = True) -> str:
    """
    Update SMS notification preferences for a user
    
    Args:
        user_email: Email of the user
        enabled: Whether SMS notifications are enabled
        urgent_only: Whether to only send SMS for urgent disruptions
        
    Returns:
        Status message
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            return f"User with email {user_email} not found"
        
        # Get current preferences or create empty dict
        preferences = user.preferences or {}
        
        # Update SMS preferences
        preferences['sms'] = {
            'enabled': enabled,
            'urgent_only': urgent_only,
            'updated_at': datetime.now().isoformat()
        }
        
        user.preferences = preferences
        db.commit()
        db.refresh(user)
        
        status = "enabled" if enabled else "disabled"
        urgency = "urgent disruptions only" if urgent_only else "all disruptions"
        
        return f"✅ SMS notifications {status} for {user_email} ({urgency})"
        
    except Exception as e:
        return f"Error updating SMS preferences: {str(e)}"
    finally:
        db.close()


def get_sms_status() -> str:
    """
    Get status of SMS notification system
    
    Returns:
        System status information
    """
    status = []
    
    # Check Twilio configuration
    if twilio_client:
        status.append("✅ Twilio client: Connected")
    else:
        status.append("❌ Twilio client: Not configured")
    
    if TWILIO_PHONE_NUMBER:
        status.append(f"✅ Twilio phone number: {TWILIO_PHONE_NUMBER}")
    else:
        status.append("❌ Twilio phone number: Not configured")
    
    # Check rate limiting stats
    total_numbers = len(sms_rate_limit)
    total_sms_today = sum(
        len([t for t in timestamps if datetime.now() - t < timedelta(days=1)])
        for timestamps in sms_rate_limit.values()
    )
    
    status.append(f"📊 Rate limiting: {total_numbers} numbers tracked, {total_sms_today} SMS sent today")
    
    return "\n".join(status)
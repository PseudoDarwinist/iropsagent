import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
from ..models import create_communication_log, SessionLocal, User, DisruptionEvent, Booking

load_dotenv()

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

print(f"=== COMMUNICATION_TOOLS.PY INITIALIZATION ===")
print(f"SMTP_SERVER: {SMTP_SERVER}")
print(f"SMTP_PORT: {SMTP_PORT}")
print(f"EMAIL_HOST_USER: {'SET' if EMAIL_HOST_USER else 'NOT SET'}")
print(f"EMAIL_HOST_PASSWORD: {'SET' if EMAIL_HOST_PASSWORD else 'NOT SET'}")


# Email templates
EMAIL_TEMPLATES = {
    "flight_cancelled": {
        "subject": "URGENT: Your flight {flight_number} has been cancelled",
        "html_template": """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f8f9fa; }}
                .flight-details {{ background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid #dc3545; }}
                .action-button {{ display: inline-block; background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Flight Cancellation Alert</h1>
                </div>
                <div class="content">
                    <p>Dear {passenger_name},</p>
                    <p>We regret to inform you that your flight has been cancelled.</p>
                    
                    <div class="flight-details">
                        <h3>Cancelled Flight Details</h3>
                        <p><strong>Flight:</strong> {flight_number}</p>
                        <p><strong>Route:</strong> {origin} → {destination}</p>
                        <p><strong>Original Departure:</strong> {original_departure}</p>
                        <p><strong>PNR:</strong> {pnr}</p>
                    </div>
                    
                    <p>Our team is actively working to find you alternative flights. We will notify you as soon as we have rebooking options available.</p>
                    
                    <p>We sincerely apologize for the inconvenience and appreciate your patience.</p>
                </div>
                <div class="footer">
                    <p>Flight Agent - Your Travel Disruption Management Assistant</p>
                    <p>This is an automated notification. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
    },
    
    "flight_delayed": {
        "subject": "Flight Update: {flight_number} is delayed",
        "html_template": """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #ffc107; color: #212529; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f8f9fa; }}
                .flight-details {{ background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid #ffc107; }}
                .delay-info {{ background-color: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Flight Delay Notification</h1>
                </div>
                <div class="content">
                    <p>Dear {passenger_name},</p>
                    <p>Your flight has been delayed. Here are the updated details:</p>
                    
                    <div class="flight-details">
                        <h3>Updated Flight Information</h3>
                        <p><strong>Flight:</strong> {flight_number}</p>
                        <p><strong>Route:</strong> {origin} → {destination}</p>
                        <p><strong>Original Departure:</strong> {original_departure}</p>
                        <p><strong>New Departure:</strong> {new_departure}</p>
                        <p><strong>PNR:</strong> {pnr}</p>
                    </div>
                    
                    <div class="delay-info">
                        <p><strong>Delay Duration:</strong> {delay_duration}</p>
                        <p>Please arrive at the airport according to the new departure time.</p>
                    </div>
                    
                    <p>We apologize for any inconvenience this may cause and thank you for your understanding.</p>
                </div>
                <div class="footer">
                    <p>Flight Agent - Your Travel Disruption Management Assistant</p>
                    <p>This is an automated notification. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
    },
    
    "rebooking_options": {
        "subject": "Rebooking Options Available for {flight_number}",
        "html_template": """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f8f9fa; }}
                .flight-details {{ background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid #28a745; }}
                .option {{ background-color: white; padding: 15px; margin: 10px 0; border: 1px solid #dee2e6; border-radius: 5px; }}
                .action-button {{ display: inline-block; background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Rebooking Options Available</h1>
                </div>
                <div class="content">
                    <p>Dear {passenger_name},</p>
                    <p>We have found alternative flight options for your disrupted travel:</p>
                    
                    <div class="flight-details">
                        <h3>Original Flight (Disrupted)</h3>
                        <p><strong>Flight:</strong> {flight_number}</p>
                        <p><strong>Route:</strong> {origin} → {destination}</p>
                        <p><strong>PNR:</strong> {pnr}</p>
                    </div>
                    
                    <h3>Available Alternatives:</h3>
                    {rebooking_options_html}
                    
                    <p>Our system will automatically select the best option based on your preferences. You will receive a confirmation once your rebooking is complete.</p>
                    
                    <p>Thank you for your patience as we work to get you to your destination.</p>
                </div>
                <div class="footer">
                    <p>Flight Agent - Your Travel Disruption Management Assistant</p>
                    <p>This is an automated notification. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
    }
}


def calculate_delay_duration(original_time: datetime, new_time: datetime) -> str:
    """Calculate human-readable delay duration"""
    if not original_time or not new_time:
        return "Unknown delay"
    
    delta = new_time - original_time
    hours = delta.total_seconds() / 3600
    
    if hours < 1:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minutes"
    elif hours < 24:
        return f"{int(hours)} hours {int((hours % 1) * 60)} minutes"
    else:
        days = int(hours / 24)
        remaining_hours = int(hours % 24)
        return f"{days} days {remaining_hours} hours"


def render_email_template(template_name: str, context: dict) -> tuple:
    """
    Render an email template with provided context
    
    Args:
        template_name: Name of the template to use
        context: Dictionary with template variables
        
    Returns:
        tuple: (subject, html_content)
    """
    if template_name not in EMAIL_TEMPLATES:
        raise ValueError(f"Template '{template_name}' not found")
    
    # Make a copy of context to avoid modifying the original
    template_context = context.copy()
    
    # Handle delay duration calculation for delay template
    if template_name == "flight_delayed":
        if 'original_departure' in template_context and 'new_departure' in template_context:
            original = template_context['original_departure']
            new = template_context['new_departure']
            
            # Convert to datetime if they're strings
            if isinstance(original, str):
                try:
                    original = datetime.fromisoformat(original.replace('Z', '+00:00'))
                except:
                    original = None
            if isinstance(new, str):
                try:
                    new = datetime.fromisoformat(new.replace('Z', '+00:00'))
                except:
                    new = None
            
            if original and new:
                template_context['delay_duration'] = calculate_delay_duration(original, new)
            else:
                template_context['delay_duration'] = "Unknown delay"
        else:
            template_context['delay_duration'] = "Unknown delay"
    
    # Handle rebooking options formatting
    if template_name == "rebooking_options" and 'rebooking_options' in template_context:
        template_context['rebooking_options_html'] = format_rebooking_options_html(template_context['rebooking_options'])
    
    template = EMAIL_TEMPLATES[template_name]
    
    # Render subject
    subject = template["subject"].format(**template_context)
    
    # Render HTML content
    html_content = template["html_template"].format(**template_context)
    
    return subject, html_content


def format_rebooking_options_html(rebooking_options: list) -> str:
    """Format rebooking options as HTML"""
    if not rebooking_options:
        return "<p>No alternative options available at this time.</p>"
    
    html = ""
    for i, option in enumerate(rebooking_options, 1):
        html += f"""
        <div class="option">
            <h4>Option {i}</h4>
            <p><strong>Flight:</strong> {option.get('flight_number', 'TBD')}</p>
            <p><strong>Departure:</strong> {option.get('departure_time', 'TBD')}</p>
            <p><strong>Arrival:</strong> {option.get('arrival_time', 'TBD')}</p>
            <p><strong>Duration:</strong> {option.get('duration', 'TBD')}</p>
            <p><strong>Stops:</strong> {option.get('stops', 'Direct')}</p>
        </div>
        """
    
    return html


def send_email_notification(user_id: str, template_name: str, context: dict, disruption_event_id: str = None) -> str:
    """
    Send email notification to user
    
    Args:
        user_id: User ID to send notification to
        template_name: Email template to use
        context: Template context variables
        disruption_event_id: Optional disruption event ID for logging
        
    Returns:
        Status message
    """
    print(f"\n=== SEND_EMAIL_NOTIFICATION CALLED ===")
    print(f"User ID: {user_id}")
    print(f"Template: {template_name}")
    print(f"Context keys: {list(context.keys())}")
    print(f"Disruption Event ID: {disruption_event_id}")
    
    try:
        # Get user from database
        db = SessionLocal()
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return f"ERROR: User {user_id} not found"
        
        recipient_email = user.email
        
        # Add default context values
        context.setdefault('passenger_name', user.email.split('@')[0].title())
        
        # Render email template
        subject, html_content = render_email_template(template_name, context)
        
        # Create communication log entry
        comm_data = {
            'disruption_event_id': disruption_event_id,
            'type': 'EMAIL',
            'template': template_name,
            'recipient': recipient_email,
            'subject': subject,
            'content': html_content,
            'status': 'PENDING'
        }
        
        # Check if email credentials are configured
        if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
            comm_data['status'] = 'FAILED'
            comm_data['error_message'] = 'Email credentials not configured'
            create_communication_log(user_id, comm_data)
            return "WARNING: Email credentials not configured. Notification logged but not sent."
        
        # Send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_HOST_USER
        msg['To'] = recipient_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send via SMTP
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            server.send_message(msg)
        
        # Update communication log
        comm_data['status'] = 'SENT'
        comm_data['sent_at'] = datetime.utcnow()
        create_communication_log(user_id, comm_data)
        
        result = f"Email notification sent successfully to {recipient_email}"
        print(f"SUCCESS: {result}")
        return result
        
    except Exception as e:
        error_msg = f"ERROR sending email notification: {str(e)}"
        print(error_msg)
        
        # Log the error
        try:
            comm_data = {
                'disruption_event_id': disruption_event_id,
                'type': 'EMAIL',
                'template': template_name,
                'recipient': user.email if 'user' in locals() else 'unknown',
                'subject': subject if 'subject' in locals() else 'Failed to render',
                'content': str(context),
                'status': 'FAILED',
                'error_message': error_msg
            }
            create_communication_log(user_id, comm_data)
        except:
            pass  # Don't fail completely if logging fails
        
        return error_msg
    
    finally:
        if 'db' in locals():
            db.close()


def notify_flight_disruption(disruption_event_id: str) -> str:
    """
    Send notification for a flight disruption event
    
    Args:
        disruption_event_id: ID of the disruption event
        
    Returns:
        Status message
    """
    print(f"\n=== NOTIFY_FLIGHT_DISRUPTION CALLED ===")
    print(f"Disruption Event ID: {disruption_event_id}")
    
    try:
        db = SessionLocal()
        
        # Get disruption event with related booking and user
        disruption = db.query(DisruptionEvent).filter(
            DisruptionEvent.event_id == disruption_event_id
        ).first()
        
        if not disruption:
            return f"ERROR: Disruption event {disruption_event_id} not found"
        
        booking = db.query(Booking).filter(
            Booking.booking_id == disruption.booking_id
        ).first()
        
        if not booking:
            return f"ERROR: Booking {disruption.booking_id} not found"
        
        user = db.query(User).filter(User.user_id == booking.user_id).first()
        
        if not user:
            return f"ERROR: User {booking.user_id} not found"
        
        # Determine template based on disruption type
        template_name = "flight_cancelled"
        if disruption.disruption_type == "DELAYED":
            template_name = "flight_delayed"
        elif disruption.disruption_type == "CANCELLED":
            template_name = "flight_cancelled"
        
        # Prepare context
        context = {
            'flight_number': booking.flight_number,
            'origin': booking.origin,
            'destination': booking.destination,
            'pnr': booking.pnr,
            'original_departure': disruption.original_departure.strftime('%A, %B %d, %Y at %I:%M %p') if disruption.original_departure else 'Unknown',
            'passenger_name': user.email.split('@')[0].title()
        }
        
        # Add new departure for delays
        if disruption.new_departure and template_name == "flight_delayed":
            context['new_departure'] = disruption.new_departure.strftime('%A, %B %d, %Y at %I:%M %p')
            context['original_departure'] = disruption.original_departure
            context['new_departure'] = disruption.new_departure
        
        # Send notification
        result = send_email_notification(
            user_id=user.user_id,
            template_name=template_name,
            context=context,
            disruption_event_id=disruption_event_id
        )
        
        # Mark user as notified
        disruption.user_notified = True
        db.commit()
        
        return result
        
    except Exception as e:
        error_msg = f"ERROR in notify_flight_disruption: {str(e)}"
        print(error_msg)
        return error_msg
    
    finally:
        if 'db' in locals():
            db.close()


def send_rebooking_options_notification(disruption_event_id: str) -> str:
    """
    Send notification with rebooking options
    
    Args:
        disruption_event_id: ID of the disruption event
        
    Returns:
        Status message
    """
    print(f"\n=== SEND_REBOOKING_OPTIONS_NOTIFICATION CALLED ===")
    print(f"Disruption Event ID: {disruption_event_id}")
    
    try:
        db = SessionLocal()
        
        # Get disruption event with related booking and user
        disruption = db.query(DisruptionEvent).filter(
            DisruptionEvent.event_id == disruption_event_id
        ).first()
        
        if not disruption:
            return f"ERROR: Disruption event {disruption_event_id} not found"
        
        booking = db.query(Booking).filter(
            Booking.booking_id == disruption.booking_id
        ).first()
        
        if not booking:
            return f"ERROR: Booking {disruption.booking_id} not found"
        
        user = db.query(User).filter(User.user_id == booking.user_id).first()
        
        if not user:
            return f"ERROR: User {booking.user_id} not found"
        
        # Prepare context
        context = {
            'flight_number': booking.flight_number,
            'origin': booking.origin,
            'destination': booking.destination,
            'pnr': booking.pnr,
            'passenger_name': user.email.split('@')[0].title(),
            'rebooking_options': disruption.rebooking_options or []
        }
        
        # Send notification
        result = send_email_notification(
            user_id=user.user_id,
            template_name="rebooking_options",
            context=context,
            disruption_event_id=disruption_event_id
        )
        
        return result
        
    except Exception as e:
        error_msg = f"ERROR in send_rebooking_options_notification: {str(e)}"
        print(error_msg)
        return error_msg
    
    finally:
        if 'db' in locals():
            db.close()
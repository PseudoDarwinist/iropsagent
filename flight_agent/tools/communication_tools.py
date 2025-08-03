"""
Communication tools for sending emails and tracking notifications
"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Dict, Optional
from ..models import create_communication_log, update_communication_status, SessionLocal, User, DisruptionEvent, Booking


def send_email_notification(user_id: str, disruption_event_id: str, template_name: str = "flight_disruption") -> str:
    """
    Send email notification to user about flight disruption
    
    Args:
        user_id: ID of the user to notify
        disruption_event_id: ID of the disruption event
        template_name: Name of the email template to use
        
    Returns:
        Status message about the email sending attempt
    """
    try:
        db = SessionLocal()
        
        # Get user and disruption event data
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return f"Error: User {user_id} not found"
            
        disruption_event = db.query(DisruptionEvent).filter(DisruptionEvent.event_id == disruption_event_id).first()
        if not disruption_event:
            return f"Error: Disruption event {disruption_event_id} not found"
            
        booking = db.query(Booking).filter(Booking.booking_id == disruption_event.booking_id).first()
        if not booking:
            return f"Error: Booking not found for disruption event"
        
        # Generate email content using template
        email_data = _render_email_template(template_name, {
            'user': user,
            'booking': booking,
            'disruption_event': disruption_event
        })
        
        # Create communication log entry
        log = create_communication_log(
            user_id=user_id,
            disruption_event_id=disruption_event_id,
            communication_type="EMAIL",
            recipient=user.email,
            subject=email_data['subject'],
            content=email_data['content'],
            template_used=template_name
        )
        
        # Send the email
        success = _send_smtp_email(
            to_email=user.email,
            subject=email_data['subject'],
            html_content=email_data['content']
        )
        
        if success:
            update_communication_status(log.log_id, "DELIVERED")
            return f"✅ Email notification sent successfully to {user.email}"
        else:
            update_communication_status(log.log_id, "FAILED", "SMTP sending failed")
            return f"❌ Failed to send email to {user.email}"
            
    except Exception as e:
        if 'log' in locals():
            update_communication_status(log.log_id, "FAILED", str(e))
        return f"❌ Error sending email notification: {str(e)}"
    finally:
        if 'db' in locals():
            db.close()


def _send_smtp_email(to_email: str, subject: str, html_content: str, from_email: str = None) -> bool:
    """
    Send email using SMTP configuration
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        from_email: Sender email (defaults to environment variable)
        
    Returns:
        True if email was sent successfully, False otherwise
    """
    try:
        # Email configuration from environment variables
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        from_email = from_email or os.getenv("FROM_EMAIL", smtp_username)
        
        if not smtp_username or not smtp_password:
            print("⚠️  Email credentials not configured. Set SMTP_USERNAME and SMTP_PASSWORD in environment")
            return False
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
            
        return True
        
    except Exception as e:
        print(f"SMTP Error: {str(e)}")
        return False


def _render_email_template(template_name: str, context: Dict) -> Dict[str, str]:
    """
    Render email template with context data
    
    Args:
        template_name: Name of the template to render
        context: Dictionary containing template context variables
        
    Returns:
        Dictionary with 'subject' and 'content' keys
    """
    templates = {
        "flight_disruption": _flight_disruption_template,
        "flight_cancellation": _flight_cancellation_template,
        "flight_delay": _flight_delay_template
    }
    
    template_func = templates.get(template_name, _flight_disruption_template)
    return template_func(context)


def _flight_disruption_template(context: Dict) -> Dict[str, str]:
    """Generic flight disruption email template"""
    user = context['user']
    booking = context['booking']
    disruption = context['disruption_event']
    
    disruption_type = disruption.disruption_type.title()
    
    subject = f"✈️ Flight {disruption_type}: {booking.flight_number} ({booking.origin} → {booking.destination})"
    
    content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #f8f9fa; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .flight-info {{ background-color: #e9ecef; padding: 15px; margin: 15px 0; border-radius: 5px; }}
            .disruption-alert {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin: 15px 0; border-radius: 5px; }}
            .footer {{ background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #6c757d; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛩️ Flight Disruption Alert</h1>
        </div>
        
        <div class="content">
            <p>Dear {user.email.split('@')[0].title()},</p>
            
            <div class="disruption-alert">
                <h3>⚠️ Your flight has been {disruption_type.lower()}</h3>
                <p>We've detected a disruption to your upcoming flight and wanted to notify you immediately.</p>
            </div>
            
            <div class="flight-info">
                <h3>Flight Details</h3>
                <ul>
                    <li><strong>Flight:</strong> {booking.airline} {booking.flight_number}</li>
                    <li><strong>Route:</strong> {booking.origin} → {booking.destination}</li>
                    <li><strong>Original Departure:</strong> {disruption.original_departure.strftime('%Y-%m-%d %H:%M')}</li>
                    {f'<li><strong>New Departure:</strong> {disruption.new_departure.strftime("%Y-%m-%d %H:%M")}</li>' if disruption.new_departure else ''}
                    <li><strong>Booking Reference:</strong> {booking.pnr}</li>
                    <li><strong>Disruption Type:</strong> {disruption_type}</li>
                </ul>
            </div>
            
            <h3>What happens next?</h3>
            <p>Our travel disruption system is automatically working to find you the best alternative options. 
            You'll receive another notification shortly with rebooking suggestions.</p>
            
            <p>In the meantime, you can:</p>
            <ul>
                <li>Check directly with {booking.airline} for updates</li>
                <li>Review your travel insurance options</li>
                <li>Monitor our system for rebooking suggestions</li>
            </ul>
        </div>
        
        <div class="footer">
            <p>This notification was sent by the Travel Disruption Management System</p>
            <p>Detected at: {disruption.detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </body>
    </html>
    """
    
    return {"subject": subject, "content": content}


def _flight_cancellation_template(context: Dict) -> Dict[str, str]:
    """Specific template for flight cancellations"""
    user = context['user']
    booking = context['booking']
    disruption = context['disruption_event']
    
    subject = f"🚫 Flight Cancelled: {booking.flight_number} - Immediate Action Required"
    
    content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .flight-info {{ background-color: #e9ecef; padding: 15px; margin: 15px 0; border-radius: 5px; }}
            .urgent {{ background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; margin: 15px 0; border-radius: 5px; }}
            .footer {{ background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #6c757d; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚫 FLIGHT CANCELLED</h1>
        </div>
        
        <div class="content">
            <p>Dear {user.email.split('@')[0].title()},</p>
            
            <div class="urgent">
                <h3>❗ Urgent: Your flight has been cancelled</h3>
                <p>Your upcoming flight has been cancelled by the airline. We're immediately working on rebooking options for you.</p>
            </div>
            
            <div class="flight-info">
                <h3>Cancelled Flight Details</h3>
                <ul>
                    <li><strong>Flight:</strong> {booking.airline} {booking.flight_number}</li>
                    <li><strong>Route:</strong> {booking.origin} → {booking.destination}</li>
                    <li><strong>Scheduled Departure:</strong> {disruption.original_departure.strftime('%Y-%m-%d %H:%M')}</li>
                    <li><strong>Booking Reference:</strong> {booking.pnr}</li>
                </ul>
            </div>
            
            <h3>Immediate Actions:</h3>
            <ol>
                <li><strong>Don't go to the airport</strong> - Your flight will not depart</li>
                <li><strong>Wait for rebooking options</strong> - We're finding alternatives now</li>
                <li><strong>Contact the airline</strong> - Call {booking.airline} customer service for official rebooking</li>
                <li><strong>Check compensation rights</strong> - You may be entitled to compensation depending on the reason</li>
            </ol>
        </div>
        
        <div class="footer">
            <p>Cancellation detected at: {disruption.detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </body>
    </html>
    """
    
    return {"subject": subject, "content": content}


def _flight_delay_template(context: Dict) -> Dict[str, str]:
    """Specific template for flight delays"""
    user = context['user']
    booking = context['booking']
    disruption = context['disruption_event']
    
    if disruption.new_departure and disruption.original_departure:
        delay_hours = (disruption.new_departure - disruption.original_departure).total_seconds() / 3600
        delay_text = f"delayed by {delay_hours:.1f} hours"
    else:
        delay_text = "delayed"
    
    subject = f"⏰ Flight Delayed: {booking.flight_number} - {delay_text}"
    
    content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #ffc107; color: #212529; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .flight-info {{ background-color: #e9ecef; padding: 15px; margin: 15px 0; border-radius: 5px; }}
            .delay-info {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin: 15px 0; border-radius: 5px; }}
            .footer {{ background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #6c757d; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⏰ FLIGHT DELAYED</h1>
        </div>
        
        <div class="content">
            <p>Dear {user.email.split('@')[0].title()},</p>
            
            <div class="delay-info">
                <h3>⏰ Your flight has been {delay_text}</h3>
                <p>We've detected a delay to your upcoming flight. Please adjust your travel plans accordingly.</p>
            </div>
            
            <div class="flight-info">
                <h3>Updated Flight Details</h3>
                <ul>
                    <li><strong>Flight:</strong> {booking.airline} {booking.flight_number}</li>
                    <li><strong>Route:</strong> {booking.origin} → {booking.destination}</li>
                    <li><strong>Original Departure:</strong> {disruption.original_departure.strftime('%Y-%m-%d %H:%M')}</li>
                    {f'<li><strong>New Departure:</strong> {disruption.new_departure.strftime("%Y-%m-%d %H:%M")}</li>' if disruption.new_departure else '<li><strong>New Departure:</strong> TBA</li>'}
                    <li><strong>Booking Reference:</strong> {booking.pnr}</li>
                </ul>
            </div>
            
            <h3>What to do:</h3>
            <ul>
                <li><strong>Adjust arrival plans</strong> - Notify anyone picking you up</li>
                <li><strong>Check connecting flights</strong> - If you have connections, they may be affected</li>
                <li><strong>Monitor for updates</strong> - Delays can change, so stay informed</li>
                <li><strong>Know your rights</strong> - Long delays may entitle you to compensation</li>
            </ul>
        </div>
        
        <div class="footer">
            <p>Delay detected at: {disruption.detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </body>
    </html>
    """
    
    return {"subject": subject, "content": content}


def test_email_configuration() -> str:
    """
    Test the email configuration and connectivity
    
    Returns:
        Status message about the email configuration test
    """
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        
        if not smtp_username or not smtp_password:
            return "❌ Email configuration incomplete. Missing SMTP_USERNAME or SMTP_PASSWORD"
        
        # Test SMTP connection
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            
        return f"✅ Email configuration test successful. Connected to {smtp_server}:{smtp_port} as {smtp_username}"
        
    except Exception as e:
        return f"❌ Email configuration test failed: {str(e)}"


def get_communication_history(user_id: str = None, disruption_event_id: str = None) -> str:
    """
    Get communication history for a user or disruption event
    
    Args:
        user_id: Filter by user ID (optional)
        disruption_event_id: Filter by disruption event ID (optional)
        
    Returns:
        Formatted communication history
    """
    try:
        from ..models import CommunicationLog
        
        db = SessionLocal()
        query = db.query(CommunicationLog)
        
        if user_id:
            query = query.filter(CommunicationLog.user_id == user_id)
        if disruption_event_id:
            query = query.filter(CommunicationLog.disruption_event_id == disruption_event_id)
            
        logs = query.order_by(CommunicationLog.sent_at.desc()).limit(10).all()
        
        if not logs:
            return "No communication history found"
        
        result = f"Found {len(logs)} recent communications:\n\n"
        
        for log in logs:
            status_emoji = "✅" if log.delivery_status == "DELIVERED" else "❌" if log.delivery_status == "FAILED" else "⏳"
            result += f"{status_emoji} {log.communication_type} to {log.recipient}\n"
            result += f"   Subject: {log.subject}\n"
            result += f"   Sent: {log.sent_at.strftime('%Y-%m-%d %H:%M')}\n"
            result += f"   Status: {log.delivery_status}\n"
            if log.error_message:
                result += f"   Error: {log.error_message}\n"
            result += "\n"
        
        return result.strip()
        
    except Exception as e:
        return f"Error retrieving communication history: {str(e)}"
    finally:
        if 'db' in locals():
            db.close()
def check_all_monitored_flights() -> str:
    """
    Check all monitored flights in the database for the next 48 hours
    
    Returns:
        Summary of all upcoming flights and their status
    """
    from datetime import datetime, timedelta, timezone
    from ..models import SessionLocal, Booking
    
    db = SessionLocal()
    try:
        # Get flights in next 48 hours
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=48)
        
        upcoming_flights = db.query(Booking).filter(
            Booking.departure_date > now,
            Booking.departure_date < cutoff,
            Booking.status == "CONFIRMED"
        ).all()
        
        if not upcoming_flights:
            return "No flights to monitor in the next 48 hours"
        
        result = f"Found {len(upcoming_flights)} flights to monitor:\n\n"
        
        for booking in upcoming_flights:
            time_until = booking.departure_date.replace(tzinfo=timezone.utc) - now
            hours_until = int(time_until.total_seconds() / 3600)
            
            result += f"✈️ {booking.flight_number}\n"
            result += f"   Route: {booking.origin} → {booking.destination}\n"
            result += f"   Departure: {booking.departure_date.strftime('%Y-%m-%d %H:%M')}\n"
            result += f"   Time until departure: {hours_until} hours\n"
            result += f"   Status: {booking.status}\n"
            result += f"   Passenger: {booking.user_id}\n\n"
        
        return result.strip()
        
    except Exception as e:
        return f"Error checking flights: {str(e)}"
    finally:
        db.close()


def detect_and_process_disruptions() -> str:
    """
    Detect flight disruptions and process them including SMS notifications
    
    Returns:
        Summary of disruptions detected and processed
    """
    from datetime import datetime, timedelta
    from ..models import (
        SessionLocal, Booking, DisruptionEvent, create_disruption_event,
        get_high_priority_disruptions
    )
    from .flight_tools import get_flight_status
    from .communication_tools import send_disruption_sms
    
    db = SessionLocal()
    try:
        # Get upcoming flights to check for disruptions
        now = datetime.now()
        cutoff = now + timedelta(hours=48)
        
        upcoming_flights = db.query(Booking).filter(
            Booking.departure_date > now,
            Booking.departure_date < cutoff,
            Booking.status == "CONFIRMED"
        ).all()
        
        if not upcoming_flights:
            return "No upcoming flights to check for disruptions"
        
        disruptions_found = 0
        sms_sent = 0
        results = []
        
        for booking in upcoming_flights:
            # Check flight status
            flight_status = get_flight_status(booking.flight_number)
            
            # Simple disruption detection based on status
            is_disrupted = False
            disruption_type = "UNKNOWN"
            priority = "MEDIUM"
            
            if "CANCELLED" in flight_status.upper():
                is_disrupted = True
                disruption_type = "CANCELLED"
                priority = "HIGH"
            elif "DELAYED" in flight_status.upper():
                is_disrupted = True
                disruption_type = "DELAYED"
                priority = "MEDIUM"
            elif "DIVERTED" in flight_status.upper():
                is_disrupted = True
                disruption_type = "DIVERTED"
                priority = "HIGH"
            
            if is_disrupted:
                # Check if we already have a disruption event for this booking
                existing_disruption = db.query(DisruptionEvent).filter(
                    DisruptionEvent.booking_id == booking.booking_id,
                    DisruptionEvent.disruption_type == disruption_type
                ).first()
                
                if not existing_disruption:
                    # Create new disruption event
                    disruption_data = {
                        'type': disruption_type,
                        'priority': priority,
                        'original_departure': booking.departure_date
                    }
                    
                    disruption = create_disruption_event(booking.booking_id, disruption_data)
                    disruptions_found += 1
                    
                    results.append(f"🚨 New {disruption_type}: {booking.flight_number} ({booking.origin}->{booking.destination})")
                    
                    # Try to send SMS if high priority
                    if priority == "HIGH":
                        sms_result = send_disruption_sms(disruption.event_id)
                        if "SMS sent" in sms_result:
                            sms_sent += 1
                            results.append(f"   📱 SMS notification sent")
                        else:
                            results.append(f"   📱 SMS failed: {sms_result}")
        
        # Also process any existing high-priority disruptions that haven't been notified
        unnotified_disruptions = get_high_priority_disruptions()
        for disruption in unnotified_disruptions:
            sms_result = send_disruption_sms(disruption.event_id)
            if "SMS sent" in sms_result:
                sms_sent += 1
                results.append(f"📱 SMS sent for existing disruption: {disruption.event_id}")
        
        summary = f"Disruption Detection Summary:\n"
        summary += f"- Flights checked: {len(upcoming_flights)}\n"
        summary += f"- New disruptions found: {disruptions_found}\n"
        summary += f"- SMS notifications sent: {sms_sent}\n\n"
        
        if results:
            summary += "Details:\n" + "\n".join(results)
        else:
            summary += "No disruptions detected."
        
        return summary
        
    except Exception as e:
        return f"Error detecting disruptions: {str(e)}"
    finally:
        db.close()


def send_pending_sms_notifications() -> str:
    """
    Send SMS notifications for any pending high-priority disruptions
    
    Returns:
        Summary of SMS notifications sent
    """
    from ..models import get_high_priority_disruptions
    from .communication_tools import send_disruption_sms
    
    try:
        pending_disruptions = get_high_priority_disruptions()
        
        if not pending_disruptions:
            return "No pending high-priority disruptions for SMS notification"
        
        sms_sent = 0
        results = []
        
        for disruption in pending_disruptions:
            sms_result = send_disruption_sms(disruption.event_id)
            if "SMS sent" in sms_result:
                sms_sent += 1
                results.append(f"✅ {sms_result}")
            else:
                results.append(f"❌ {sms_result}")
        
        summary = f"SMS Notification Summary:\n"
        summary += f"- Pending disruptions: {len(pending_disruptions)}\n"
        summary += f"- SMS notifications sent: {sms_sent}\n\n"
        
        if results:
            summary += "Details:\n" + "\n".join(results)
        
        return summary
        
    except Exception as e:
        return f"Error sending pending SMS notifications: {str(e)}"
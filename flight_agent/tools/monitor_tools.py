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


def create_disruption_event(booking_id: str, disruption_type: str, original_departure: str = None, 
                          new_departure: str = None) -> str:
    """
    Create a disruption event and trigger email notification
    
    Args:
        booking_id: ID of the affected booking
        disruption_type: Type of disruption (CANCELLED, DELAYED, DIVERTED)
        original_departure: Original departure time (ISO format)
        new_departure: New departure time if applicable (ISO format)
        
    Returns:
        Status message about disruption event creation and notification
    """
    from datetime import datetime
    from ..models import SessionLocal, Booking, DisruptionEvent
    from .communication_tools import send_email_notification
    
    try:
        db = SessionLocal()
        
        # Get the booking
        booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
        if not booking:
            return f"Error: Booking {booking_id} not found"
        
        # Check if disruption already exists for this booking
        existing_disruption = db.query(DisruptionEvent).filter(
            DisruptionEvent.booking_id == booking_id,
            DisruptionEvent.disruption_type == disruption_type
        ).first()
        
        if existing_disruption:
            return f"Disruption event already exists for booking {booking_id} with type {disruption_type}"
        
        # Parse datetime strings if provided
        orig_dt = None
        new_dt = None
        
        if original_departure:
            try:
                orig_dt = datetime.fromisoformat(original_departure.replace('Z', '+00:00'))
            except:
                orig_dt = booking.departure_date
        else:
            orig_dt = booking.departure_date
            
        if new_departure:
            try:
                new_dt = datetime.fromisoformat(new_departure.replace('Z', '+00:00'))
            except:
                new_dt = None
        
        # Create disruption event
        event_id = f"disruption_{booking_id}_{datetime.now().timestamp()}"
        disruption_event = DisruptionEvent(
            event_id=event_id,
            booking_id=booking_id,
            disruption_type=disruption_type.upper(),
            original_departure=orig_dt,
            new_departure=new_dt,
            rebooking_status="PENDING"
        )
        
        db.add(disruption_event)
        db.commit()
        db.refresh(disruption_event)
        
        # Trigger email notification
        template_map = {
            "CANCELLED": "flight_cancellation",
            "DELAYED": "flight_delay",
            "DIVERTED": "flight_disruption"
        }
        
        template_name = template_map.get(disruption_type.upper(), "flight_disruption")
        
        # Send notification
        notification_result = send_email_notification(
            user_id=booking.user_id,
            disruption_event_id=event_id,
            template_name=template_name
        )
        
        result = f"✅ Disruption event created successfully\n"
        result += f"   Event ID: {event_id}\n"
        result += f"   Flight: {booking.flight_number} ({booking.origin} → {booking.destination})\n"
        result += f"   Disruption Type: {disruption_type.upper()}\n"
        result += f"   Affected Passenger: {booking.user_id}\n\n"
        result += f"📧 Email Notification: {notification_result}"
        
        return result
        
    except Exception as e:
        return f"Error creating disruption event: {str(e)}"
    finally:
        if 'db' in locals():
            db.close()


def simulate_flight_disruption(flight_number: str, disruption_type: str, new_departure: str = None) -> str:
    """
    Simulate a flight disruption for testing purposes
    
    Args:
        flight_number: Flight number to disrupt
        disruption_type: Type of disruption (CANCELLED, DELAYED, DIVERTED)
        new_departure: New departure time if applicable (ISO format)
        
    Returns:
        Status message about the simulated disruption
    """
    from ..models import SessionLocal, Booking
    
    try:
        db = SessionLocal()
        
        # Find bookings for this flight number
        bookings = db.query(Booking).filter(
            Booking.flight_number == flight_number,
            Booking.status == "CONFIRMED"
        ).all()
        
        if not bookings:
            return f"No confirmed bookings found for flight {flight_number}"
        
        results = []
        for booking in bookings:
            result = create_disruption_event(
                booking_id=booking.booking_id,
                disruption_type=disruption_type,
                original_departure=booking.departure_date.isoformat(),
                new_departure=new_departure
            )
            results.append(result)
        
        summary = f"🚨 Simulated {disruption_type.upper()} for flight {flight_number}\n"
        summary += f"Affected {len(bookings)} booking(s)\n\n"
        summary += "\n".join(results)
        
        return summary
        
    except Exception as e:
        return f"Error simulating disruption: {str(e)}"
    finally:
        if 'db' in locals():
            db.close()


def get_disruption_events(booking_id: str = None, user_id: str = None) -> str:
    """
    Get disruption events from the database
    
    Args:
        booking_id: Filter by booking ID (optional)
        user_id: Filter by user ID (optional)
        
    Returns:
        List of disruption events
    """
    from ..models import SessionLocal, DisruptionEvent, Booking
    
    try:
        db = SessionLocal()
        
        query = db.query(DisruptionEvent).join(Booking)
        
        if booking_id:
            query = query.filter(DisruptionEvent.booking_id == booking_id)
        if user_id:
            query = query.filter(Booking.user_id == user_id)
            
        events = query.order_by(DisruptionEvent.detected_at.desc()).limit(10).all()
        
        if not events:
            return "No disruption events found"
        
        result = f"Found {len(events)} disruption event(s):\n\n"
        
        for event in events:
            booking = db.query(Booking).filter(Booking.booking_id == event.booking_id).first()
            
            result += f"🚨 {event.disruption_type}\n"
            result += f"   Event ID: {event.event_id}\n"
            result += f"   Flight: {booking.flight_number if booking else 'Unknown'}\n"
            result += f"   Route: {booking.origin} → {booking.destination}\n" if booking else ""
            result += f"   Detected: {event.detected_at.strftime('%Y-%m-%d %H:%M')}\n"
            result += f"   Original Departure: {event.original_departure.strftime('%Y-%m-%d %H:%M') if event.original_departure else 'Unknown'}\n"
            if event.new_departure:
                result += f"   New Departure: {event.new_departure.strftime('%Y-%m-%d %H:%M')}\n"
            result += f"   Rebooking Status: {event.rebooking_status}\n"
            result += f"   User Notified: {'Yes' if event.user_notified else 'No'}\n\n"
        
        return result.strip()
        
    except Exception as e:
        return f"Error retrieving disruption events: {str(e)}"
    finally:
        if 'db' in locals():
            db.close()
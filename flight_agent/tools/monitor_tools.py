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


def detect_and_log_disruptions() -> str:
    """
    Check all monitored flights for disruptions and log them to the database
    
    Returns:
        Summary of detected disruptions
    """
    from datetime import datetime, timedelta, timezone
    from ..models import SessionLocal, Booking, DisruptionEvent, create_disruption_event
    from ..tools.flight_tools import get_flight_status
    import re
    
    print(f"\n=== DETECT_AND_LOG_DISRUPTIONS CALLED ===")
    
    db = SessionLocal()
    try:
        # Get flights in next 48 hours that haven't been checked recently
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=48)
        
        upcoming_flights = db.query(Booking).filter(
            Booking.departure_date > now,
            Booking.departure_date < cutoff,
            Booking.status == "CONFIRMED"
        ).all()
        
        if not upcoming_flights:
            return "No flights to monitor for disruptions"
        
        disruptions_found = []
        
        for booking in upcoming_flights:
            print(f"Checking flight {booking.flight_number} for disruptions...")
            
            # Check if we already have a recent disruption event for this booking
            existing_disruption = db.query(DisruptionEvent).filter(
                DisruptionEvent.booking_id == booking.booking_id
            ).first()
            
            if existing_disruption:
                print(f"Disruption already logged for {booking.flight_number}")
                continue
            
            # Get current flight status
            status_result = get_flight_status(booking.flight_number)
            print(f"Status result: {status_result}")
            
            # Parse status for disruptions
            disruption_detected = False
            disruption_type = None
            
            # Check for cancellation
            if "CANCELLED" in status_result.upper() or "CANCELED" in status_result.upper():
                disruption_type = "CANCELLED"
                disruption_detected = True
                print(f"CANCELLATION detected for {booking.flight_number}")
            
            # Check for delays (look for delay indicators in status)
            elif "DELAY" in status_result.upper() or "LATE" in status_result.upper():
                disruption_type = "DELAYED"
                disruption_detected = True
                print(f"DELAY detected for {booking.flight_number}")
            
            # If disruption detected, log it
            if disruption_detected:
                disruption_data = {
                    'type': disruption_type,
                    'original_departure': booking.departure_date,
                    'new_departure': booking.departure_date if disruption_type == "CANCELLED" else None
                }
                
                # Create disruption event
                disruption_event = create_disruption_event(booking.booking_id, disruption_data)
                
                disruption_info = {
                    'event_id': disruption_event.event_id,
                    'booking_id': booking.booking_id,
                    'flight_number': booking.flight_number,
                    'route': f"{booking.origin} → {booking.destination}",
                    'disruption_type': disruption_type,
                    'passenger_email': booking.user_id  # Note: this is actually user_id, would need to join to get email
                }
                
                disruptions_found.append(disruption_info)
                print(f"Logged disruption event: {disruption_event.event_id}")
        
        if not disruptions_found:
            return "No disruptions detected in monitored flights"
        
        # Format result
        result = f"DISRUPTIONS DETECTED - {len(disruptions_found)} flight(s) affected:\n\n"
        
        for disruption in disruptions_found:
            result += f"🚨 {disruption['flight_number']} ({disruption['disruption_type']})\n"
            result += f"   Route: {disruption['route']}\n"
            result += f"   Event ID: {disruption['event_id']}\n"
            result += f"   Passenger: {disruption['passenger_email']}\n\n"
        
        result += "⚠️  IMMEDIATE ACTION REQUIRED: Send notifications to affected passengers"
        
        return result.strip()
        
    except Exception as e:
        error_msg = f"ERROR in detect_and_log_disruptions: {str(e)}"
        print(error_msg)
        return error_msg
    finally:
        db.close()
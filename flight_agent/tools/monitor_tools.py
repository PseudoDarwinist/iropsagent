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
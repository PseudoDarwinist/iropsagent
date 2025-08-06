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


def detect_flight_disruption(booking_id: str, flight_status_data: dict) -> dict:
    """
    Detect flight disruption and automatically process compensation if applicable
    
    Args:
        booking_id: Booking ID to check for disruption
        flight_status_data: Current flight status information
    
    Returns:
        Dictionary containing disruption detection and compensation results
    """
    from datetime import datetime, timezone
    from uuid import uuid4
    from ..models import SessionLocal, Booking, DisruptionEvent
    from .wallet_tools import process_compensation
    
    db = SessionLocal()
    try:
        # Get the booking
        booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
        if not booking:
            return {'error': 'Booking not found'}
        
        # Analyze flight status for disruptions
        disruption_detected = False
        disruption_type = None
        delay_hours = 0
        new_departure = None
        
        # Check for cancellation
        if flight_status_data.get('status', '').upper() in ['CANCELLED', 'CANCELED']:
            disruption_detected = True
            disruption_type = 'CANCELLED'
        
        # Check for significant delays (>2 hours)
        elif flight_status_data.get('delayed_by_minutes', 0) > 120:
            disruption_detected = True
            disruption_type = 'DELAYED'
            delay_hours = flight_status_data['delayed_by_minutes'] / 60
            if flight_status_data.get('new_departure_time'):
                new_departure = datetime.fromisoformat(flight_status_data['new_departure_time'])
        
        # Check for diversion
        elif (flight_status_data.get('diverted') or 
              flight_status_data.get('destination_airport') != booking.destination):
            disruption_detected = True
            disruption_type = 'DIVERTED'
        
        if not disruption_detected:
            return {
                'disruption_detected': False,
                'message': 'No significant disruption detected'
            }
        
        # Check if we already processed this disruption
        existing_event = db.query(DisruptionEvent).filter(
            DisruptionEvent.booking_id == booking_id,
            DisruptionEvent.disruption_type == disruption_type
        ).first()
        
        if existing_event:
            return {
                'disruption_detected': True,
                'disruption_type': disruption_type,
                'message': 'Disruption already processed',
                'event_id': existing_event.event_id
            }
        
        # Create disruption event
        event_id = f"event_{uuid4().hex[:12]}_{int(datetime.now().timestamp())}"
        disruption_event = DisruptionEvent(
            event_id=event_id,
            booking_id=booking_id,
            disruption_type=disruption_type,
            original_departure=booking.departure_date,
            new_departure=new_departure,
            rebooking_status='PENDING'
        )
        
        db.add(disruption_event)
        db.commit()
        
        # Prepare disruption data for compensation calculation
        disruption_data = {
            'disruption_type': disruption_type,
            'booking_class': booking.booking_class,
            'delay_hours': delay_hours,
            'is_international': _is_international_flight(booking.origin, booking.destination),
            'airline': booking.airline,
            'flight_distance_km': _estimate_flight_distance(booking.origin, booking.destination)
        }
        
        # Process automatic compensation
        compensation_result = process_compensation(
            user_id=booking.user_id,
            booking_id=booking_id,
            disruption_event_id=event_id,
            disruption_data=disruption_data
        )
        
        return {
            'disruption_detected': True,
            'disruption_type': disruption_type,
            'event_id': event_id,
            'delay_hours': delay_hours,
            'compensation_processed': compensation_result.get('success', False),
            'compensation_amount': compensation_result.get('amount_credited', 0),
            'compensation_details': compensation_result,
            'message': f"Disruption detected and compensation processed: {compensation_result.get('message', 'Unknown result')}"
        }
    
    except Exception as e:
        db.rollback()
        return {
            'error': f'Error processing disruption: {str(e)}',
            'disruption_detected': True,
            'disruption_type': disruption_type
        }
    finally:
        db.close()


def monitor_and_compensate_disruptions() -> str:
    """
    Monitor all active bookings for disruptions and automatically process compensation
    
    Returns:
        Summary of monitoring and compensation activities
    """
    from datetime import datetime, timedelta, timezone
    from ..models import SessionLocal, Booking
    
    db = SessionLocal()
    results = []
    
    try:
        # Get upcoming flights that haven't been checked recently
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=48)
        check_threshold = now - timedelta(hours=1)  # Check flights not checked in last hour
        
        flights_to_check = db.query(Booking).filter(
            Booking.departure_date > now,
            Booking.departure_date < cutoff,
            Booking.status == "CONFIRMED",
            Booking.last_checked < check_threshold  # or Booking.last_checked.is_(None)
        ).all()
        
        if not flights_to_check:
            return "No flights need disruption monitoring at this time."
        
        results.append(f"Monitoring {len(flights_to_check)} flights for disruptions:\n")
        
        for booking in flights_to_check:
            # Simulate flight status check (in real implementation, would call FlightAware API)
            flight_status = _simulate_flight_status_check(booking)
            
            # Update last checked timestamp
            booking.last_checked = now
            
            # Check for disruptions
            disruption_result = detect_flight_disruption(booking.booking_id, flight_status)
            
            if disruption_result.get('disruption_detected'):
                compensation_msg = ""
                if disruption_result.get('compensation_processed'):
                    amount = disruption_result.get('compensation_amount', 0)
                    compensation_msg = f" | 💰 ${amount:.2f} credited to wallet"
                
                results.append(
                    f"🚨 {booking.flight_number}: {disruption_result['disruption_type']}"
                    f"{compensation_msg}"
                )
            else:
                results.append(f"✅ {booking.flight_number}: No disruption detected")
        
        db.commit()
        return '\n'.join(results)
    
    except Exception as e:
        db.rollback()
        return f"Error monitoring flights: {str(e)}"
    finally:
        db.close()


def _is_international_flight(origin: str, destination: str) -> bool:
    """
    Determine if flight is international based on airport codes
    
    Args:
        origin: Origin airport code
        destination: Destination airport code
    
    Returns:
        True if international flight, False otherwise
    """
    # US airport codes typically start with 'K' in ICAO format or are 3-letter IATA codes
    # This is a simplified check - in production, would use proper airport database
    
    us_airports = {
        'JFK', 'LAX', 'ORD', 'ATL', 'DFW', 'DEN', 'SFO', 'SEA', 'LAS', 'MCO',
        'EWR', 'CLT', 'PHX', 'IAH', 'MIA', 'BOS', 'MSP', 'FLL', 'DTW', 'PHL'
    }
    
    origin_domestic = origin in us_airports or (len(origin) == 4 and origin.startswith('K'))
    dest_domestic = destination in us_airports or (len(destination) == 4 and destination.startswith('K'))
    
    return not (origin_domestic and dest_domestic)


def _estimate_flight_distance(origin: str, destination: str) -> int:
    """
    Estimate flight distance in kilometers
    
    Args:
        origin: Origin airport code
        destination: Destination airport code
    
    Returns:
        Estimated distance in kilometers
    """
    # Simplified distance estimation - in production would use proper airport coordinates
    # This provides reasonable estimates for compensation calculation
    
    distance_map = {
        # Common US domestic routes
        ('JFK', 'LAX'): 3944,
        ('ORD', 'LAX'): 2802,
        ('ATL', 'LAX'): 3088,
        ('JFK', 'SFO'): 4139,
        ('ORD', 'JFK'): 1185,
        
        # International examples
        ('JFK', 'LHR'): 5545,
        ('LAX', 'NRT'): 8815,
        ('JFK', 'CDG'): 5850,
        ('SFO', 'FRA'): 9080,
    }
    
    # Try direct lookup
    key = (origin, destination)
    if key in distance_map:
        return distance_map[key]
    
    # Try reverse lookup
    reverse_key = (destination, origin)
    if reverse_key in distance_map:
        return distance_map[reverse_key]
    
    # Default estimates based on route type
    if _is_international_flight(origin, destination):
        return 6000  # Assume trans-oceanic
    else:
        return 1500  # Assume domestic medium-haul


def _simulate_flight_status_check(booking) -> dict:
    """
    Simulate flight status check for testing purposes
    In production, this would call the FlightAware API
    
    Args:
        booking: Booking object
    
    Returns:
        Simulated flight status data
    """
    import random
    from datetime import datetime, timedelta
    
    # Simulate various scenarios for testing
    scenarios = [
        # Normal flight (80% probability)
        {
            'probability': 0.8,
            'status': 'ON_TIME',
            'delayed_by_minutes': 0
        },
        # Minor delay (10% probability)
        {
            'probability': 0.1,
            'status': 'DELAYED',
            'delayed_by_minutes': 45
        },
        # Major delay - triggers compensation (5% probability)
        {
            'probability': 0.05,
            'status': 'DELAYED',
            'delayed_by_minutes': 240  # 4 hours
        },
        # Cancellation - triggers compensation (5% probability)
        {
            'probability': 0.05,
            'status': 'CANCELLED',
            'delayed_by_minutes': 0
        }
    ]
    
    # Select scenario based on probability
    rand = random.random()
    cumulative_prob = 0
    selected_scenario = scenarios[0]  # Default to on-time
    
    for scenario in scenarios:
        cumulative_prob += scenario['probability']
        if rand <= cumulative_prob:
            selected_scenario = scenario
            break
    
    result = {
        'flight_number': booking.flight_number,
        'status': selected_scenario['status'],
        'delayed_by_minutes': selected_scenario['delayed_by_minutes'],
        'destination_airport': booking.destination,
        'diverted': False
    }
    
    # Add new departure time if delayed
    if selected_scenario['delayed_by_minutes'] > 0:
        new_departure = booking.departure_date + timedelta(minutes=selected_scenario['delayed_by_minutes'])
        result['new_departure_time'] = new_departure.isoformat()
    
    return result
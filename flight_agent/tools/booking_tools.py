def manual_booking_entry(flight_number: str, departure_date: str, origin: str, 
                        destination: str, user_email: str) -> str:
    """
    Manually add a flight booking for a user
    
    Args:
        flight_number: Flight number (e.g., "UA100")
        departure_date: Date in YYYY-MM-DD format
        origin: Origin airport code (e.g., "ORD")
        destination: Destination airport code (e.g., "SFO")
        user_email: User's email address
    
    Returns:
        Success or error message
    """
    from datetime import datetime
    from ..models import get_user_by_email, create_booking, create_user
    
    try:
        # Get or create user
        user = get_user_by_email(user_email)
        if not user:
            user = create_user(user_email)
        
        # Parse date
        departure_dt = datetime.strptime(departure_date, "%Y-%m-%d")
        
        # Extract airline from flight number
        airline_codes = {
            'UA': 'United',
            'AA': 'American',
            'DL': 'Delta',
            'WN': 'Southwest',
            'B6': 'JetBlue'
        }
        airline_code = flight_number[:2]
        airline = airline_codes.get(airline_code, 'Unknown')
        
        # Create booking
        booking_data = {
            'pnr': f"MANUAL{datetime.now().strftime('%H%M%S')}",
            'airline': airline,
            'flight_number': flight_number,
            'departure_date': departure_dt,
            'origin': origin,
            'destination': destination,
            'class': 'Economy',
            'seat': 'TBD'
        }
        
        booking = create_booking(user.user_id, booking_data)
        
        return f"✅ Successfully added {flight_number} from {origin} to {destination} on {departure_date}"
        
    except Exception as e:
        return f"❌ Error adding booking: {str(e)}"
    
    # Turn the BookingImporter class methods into tool functions:
def scan_email_for_bookings(user_email: str, password: str) -> str:
    """Tool function for booking import agent"""
    importer = BookingImporter()
    bookings = importer.import_from_imap(user_email, password)
    return f"Found {len(bookings)} bookings: {bookings}"

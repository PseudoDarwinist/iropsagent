# add_test_bookings.py
from datetime import datetime, timedelta
from flight_agent.models import create_user, get_user_by_email, create_booking

def add_test_bookings():
    """Add some test bookings that the monitor will find"""
    
    # Get or create test user
    test_email = "monitor_test@example.com"
    user = get_user_by_email(test_email)
    if not user:
        user = create_user(test_email, phone="+1234567890")
        print(f"Created user: {user.email}")
    
    # Add bookings for the next few days
    test_flights = [
        {
            'pnr': 'TEST01',
            'airline': 'United',
            'flight_number': 'UA100',
            'departure_date': datetime.now() + timedelta(hours=3),  # 3 hours from now
            'origin': 'ORD',
            'destination': 'SFO',
            'class': 'Economy',
            'seat': '23A'
        },
        {
            'pnr': 'TEST02',
            'airline': 'American',
            'flight_number': 'AA2341',
            'departure_date': datetime.now() + timedelta(hours=12),  # 12 hours from now
            'origin': 'JFK',
            'destination': 'LAX',
            'class': 'Business',
            'seat': '2B'
        },
        {
            'pnr': 'TEST03',
            'airline': 'Delta',
            'flight_number': 'DL456',
            'departure_date': datetime.now() + timedelta(hours=24),  # Tomorrow
            'origin': 'ATL',
            'destination': 'MIA',
            'class': 'Economy',
            'seat': '15C'
        }
    ]
    
    for flight_data in test_flights:
        try:
            booking = create_booking(user.user_id, flight_data)
            print(f"✅ Added {booking.flight_number} departing at {booking.departure_date}")
        except Exception as e:
            print(f"❌ Error adding flight: {e}")

if __name__ == "__main__":
    add_test_bookings()
    print("\n🎯 Now run the monitor again: python -m flight_agent.monitor")
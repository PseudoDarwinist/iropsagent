#!/usr/bin/env python3
"""
Test suite for Flight Monitoring Data Models

Tests the new Flight, Traveler, and TripMonitor models along with
their relationships and helper functions.
"""

import unittest
import tempfile
import os
from datetime import datetime, timedelta
from flight_agent.models import (
    Base, engine, SessionLocal,
    User, Flight, Traveler, Booking, TripMonitor, DisruptionEvent,
    create_user, create_flight, create_traveler, create_booking,
    create_trip_monitor, get_flight_by_details, update_flight_status,
    get_active_trip_monitors, get_upcoming_bookings
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestFlightMonitoringModels(unittest.TestCase):
    """Test cases for flight monitoring data models"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        # Create test database in memory
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        
        # Create all tables
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        """Set up test data for each test"""
        self.session = self.TestSession()
        
        # Create unique user for each test to avoid conflicts
        unique_id = str(int(datetime.now().timestamp() * 1000000))
        
        # Create test user
        self.test_user = User(
            user_id=f"test_user_{unique_id}",
            email=f"test_{unique_id}@example.com",
            phone="+1234567890",
            preferences={"sms": {"enabled": True}}
        )
        self.session.add(self.test_user)
        self.session.commit()
        
        # Create test flight
        self.test_flight_data = {
            'airline': 'AA',
            'flight_number': '1234',
            'departure_airport': 'JFK',
            'arrival_airport': 'LAX',
            'scheduled_departure': datetime(2025, 8, 15, 8, 30),
            'scheduled_arrival': datetime(2025, 8, 15, 11, 45),
            'aircraft_type': 'Boeing 737',
            'gate': 'A12',
            'terminal': '1'
        }
        
        self.test_flight = Flight(
            flight_id=f"AA_1234_{unique_id}",
            **self.test_flight_data
        )
        self.session.add(self.test_flight)
        self.session.commit()
        
        # Create test traveler
        self.test_traveler_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'middle_name': 'Smith',
            'date_of_birth': datetime(1990, 5, 15),
            'passport_number': 'US123456789',
            'passport_country': 'US',
            'passport_expiry': datetime(2030, 5, 15),
            'known_traveler_number': 'KTN123456',
            'frequent_flyer_numbers': {"AA": "12345678", "DL": "87654321"},
            'dietary_restrictions': ['vegetarian', 'nut-free'],
            'mobility_assistance': False,
            'emergency_contact': {
                'name': 'Jane Doe',
                'phone': '+1987654321',
                'relationship': 'Spouse'
            },
            'preferences': {
                'seat': 'aisle',
                'meal': 'vegetarian'
            }
        }
        
        self.test_traveler = Traveler(
            traveler_id=f"traveler_{unique_id}",
            user_id=self.test_user.user_id,
            **self.test_traveler_data
        )
        self.session.add(self.test_traveler)
        self.session.commit()
    
    def tearDown(self):
        """Clean up after each test"""
        self.session.rollback()
        self.session.close()
    
    def test_flight_model_creation(self):
        """Test Flight model creation and attributes"""
        flight = self.session.query(Flight).filter_by(flight_id=self.test_flight.flight_id).first()
        
        self.assertIsNotNone(flight)
        self.assertEqual(flight.airline, 'AA')
        self.assertEqual(flight.flight_number, '1234')
        self.assertEqual(flight.departure_airport, 'JFK')
        self.assertEqual(flight.arrival_airport, 'LAX')
        self.assertEqual(flight.flight_status, 'SCHEDULED')
        self.assertEqual(flight.delay_minutes, 0)
        self.assertEqual(flight.gate, 'A12')
        self.assertEqual(flight.terminal, '1')
        self.assertIsNotNone(flight.created_at)
        self.assertIsNotNone(flight.updated_at)
    
    def test_traveler_model_creation(self):
        """Test Traveler model creation and attributes"""
        traveler = self.session.query(Traveler).filter_by(traveler_id=self.test_traveler.traveler_id).first()
        
        self.assertIsNotNone(traveler)
        self.assertEqual(traveler.first_name, 'John')
        self.assertEqual(traveler.last_name, 'Doe')
        self.assertEqual(traveler.middle_name, 'Smith')
        self.assertEqual(traveler.passport_number, 'US123456789')
        self.assertEqual(traveler.passport_country, 'US')
        self.assertEqual(traveler.known_traveler_number, 'KTN123456')
        self.assertEqual(traveler.frequent_flyer_numbers, {"AA": "12345678", "DL": "87654321"})
        self.assertEqual(traveler.dietary_restrictions, ['vegetarian', 'nut-free'])
        self.assertEqual(traveler.mobility_assistance, False)
        self.assertEqual(traveler.emergency_contact['name'], 'Jane Doe')
        self.assertEqual(traveler.preferences['seat'], 'aisle')
        self.assertIsNotNone(traveler.created_at)
        self.assertIsNotNone(traveler.updated_at)
    
    def test_booking_model_with_relationships(self):
        """Test Booking model with Flight and Traveler relationships"""
        # Create booking (fix the 'class' keyword issue)
        booking_data = {
            'pnr': 'ABC123',
            'airline': 'AA',
            'flight_number': '1234',
            'departure_date': datetime(2025, 8, 15, 8, 30),
            'origin': 'JFK',
            'destination': 'LAX',
            'booking_class': 'Economy',  # Changed from 'class' to 'booking_class'
            'seat': '12A',
            'ticket_number': 'TKT789456',
            'fare_amount': 350.00,
            'currency': 'USD'
        }
        
        booking = Booking(
            booking_id="booking_test_123",
            user_id=self.test_user.user_id,
            flight_id=self.test_flight.flight_id,
            traveler_id=self.test_traveler.traveler_id,
            **booking_data
        )
        self.session.add(booking)
        self.session.commit()
        
        # Test relationships
        retrieved_booking = self.session.query(Booking).filter_by(booking_id="booking_test_123").first()
        self.assertIsNotNone(retrieved_booking)
        self.assertEqual(retrieved_booking.user.email, self.test_user.email)
        self.assertEqual(retrieved_booking.flight.airline, 'AA')
        self.assertEqual(retrieved_booking.traveler.first_name, 'John')
        self.assertEqual(retrieved_booking.fare_amount, 350.00)
        self.assertEqual(retrieved_booking.currency, 'USD')
        self.assertEqual(retrieved_booking.status, 'CONFIRMED')
    
    def test_trip_monitor_model_creation(self):
        """Test TripMonitor model creation and relationships"""
        # Create booking first
        booking = Booking(
            booking_id="booking_monitor_test",
            user_id=self.test_user.user_id,
            flight_id=self.test_flight.flight_id,
            traveler_id=self.test_traveler.traveler_id,
            pnr='MON123',
            airline='AA',
            flight_number='1234',
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin='JFK',
            destination='LAX'
        )
        self.session.add(booking)
        self.session.commit()
        
        # Create trip monitor
        monitor_data = {
            'monitor_type': 'FULL',
            'check_frequency_minutes': 15,
            'notification_preferences': {"email": True, "sms": True},
            'escalation_rules': {"delay_threshold": 30},
            'auto_rebooking_enabled': True,
            'rebooking_preferences': {"prefer_direct": True},
            'notes': 'Important business travel',
            'expires_at': datetime.now() + timedelta(days=2)
        }
        
        trip_monitor = TripMonitor(
            monitor_id="monitor_test_123",
            user_id=self.test_user.user_id,
            booking_id=booking.booking_id,
            flight_id=self.test_flight.flight_id,
            **monitor_data
        )
        self.session.add(trip_monitor)
        self.session.commit()
        
        # Test monitor attributes
        retrieved_monitor = self.session.query(TripMonitor).filter_by(monitor_id="monitor_test_123").first()
        self.assertIsNotNone(retrieved_monitor)
        self.assertEqual(retrieved_monitor.monitor_type, 'FULL')
        self.assertEqual(retrieved_monitor.check_frequency_minutes, 15)
        self.assertTrue(retrieved_monitor.is_active)
        self.assertEqual(retrieved_monitor.notification_preferences['email'], True)
        self.assertEqual(retrieved_monitor.notification_preferences['sms'], True)
        self.assertTrue(retrieved_monitor.auto_rebooking_enabled)
        self.assertEqual(retrieved_monitor.notes, 'Important business travel')
        
        # Test relationships
        self.assertEqual(retrieved_monitor.booking.pnr, 'MON123')
        self.assertEqual(retrieved_monitor.flight.airline, 'AA')
    
    def test_model_relationships_consistency(self):
        """Test that all model relationships are consistent"""
        # Create complete data chain: User -> Traveler -> Booking -> TripMonitor
        booking = Booking(
            booking_id="rel_test_booking",
            user_id=self.test_user.user_id,
            flight_id=self.test_flight.flight_id,
            traveler_id=self.test_traveler.traveler_id,
            pnr='REL123',
            airline='AA',
            flight_number='1234',
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin='JFK',
            destination='LAX'
        )
        self.session.add(booking)
        
        trip_monitor = TripMonitor(
            monitor_id="rel_test_monitor",
            user_id=self.test_user.user_id,
            booking_id=booking.booking_id,
            flight_id=self.test_flight.flight_id
        )
        self.session.add(trip_monitor)
        self.session.commit()
        
        # Test forward relationships
        user = self.session.query(User).filter_by(user_id=self.test_user.user_id).first()
        self.assertGreater(len(user.bookings), 0)
        self.assertGreater(len(user.travelers), 0)
        
        flight = self.session.query(Flight).filter_by(flight_id=self.test_flight.flight_id).first()
        self.assertGreater(len(flight.bookings), 0)
        self.assertGreater(len(flight.trip_monitors), 0)
        
        # Test backward relationships
        retrieved_booking = self.session.query(Booking).filter_by(booking_id="rel_test_booking").first()
        self.assertEqual(retrieved_booking.user.user_id, self.test_user.user_id)
        self.assertEqual(retrieved_booking.flight.flight_id, self.test_flight.flight_id)
        self.assertEqual(retrieved_booking.traveler.traveler_id, self.test_traveler.traveler_id)
        
        retrieved_monitor = self.session.query(TripMonitor).filter_by(monitor_id="rel_test_monitor").first()
        self.assertEqual(retrieved_monitor.booking.booking_id, "rel_test_booking")
        self.assertEqual(retrieved_monitor.flight.flight_id, self.test_flight.flight_id)
    
    def test_enhanced_disruption_event(self):
        """Test enhanced DisruptionEvent model with new fields"""
        # Create booking first
        booking = Booking(
            booking_id="disruption_test_booking",
            user_id=self.test_user.user_id,
            flight_id=self.test_flight.flight_id,
            pnr='DIS123',
            airline='AA',
            flight_number='1234',
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin='JFK',
            destination='LAX'
        )
        self.session.add(booking)
        self.session.commit()
        
        # Create disruption event with enhanced fields
        disruption = DisruptionEvent(
            event_id="disruption_test_123",
            booking_id=booking.booking_id,
            disruption_type='DELAYED',
            original_departure=datetime(2025, 8, 15, 8, 30),
            new_departure=datetime(2025, 8, 15, 10, 30),
            delay_minutes=120,
            reason='Weather conditions',
            priority='HIGH',
            compensation_eligible=True,
            compensation_amount=200.0,
            compensation_status='PENDING'
        )
        self.session.add(disruption)
        self.session.commit()
        
        # Test enhanced attributes
        retrieved_disruption = self.session.query(DisruptionEvent).filter_by(event_id="disruption_test_123").first()
        self.assertEqual(retrieved_disruption.delay_minutes, 120)
        self.assertEqual(retrieved_disruption.reason, 'Weather conditions')
        self.assertTrue(retrieved_disruption.compensation_eligible)
        self.assertEqual(retrieved_disruption.compensation_amount, 200.0)
        self.assertEqual(retrieved_disruption.compensation_status, 'PENDING')
        self.assertIsNone(retrieved_disruption.notification_sent_at)


def run_simple_validation():
    """Run simple validation that doesn't rely on the full database"""
    print("Running simple model validation...")
    
    # Test model imports
    from flight_agent.models import Flight, Traveler, TripMonitor, Booking
    print("✓ All new models imported successfully")
    
    # Test basic model instantiation
    try:
        flight = Flight(
            flight_id="test_flight_123",
            airline="AA", 
            flight_number="1234",
            departure_airport="JFK",
            arrival_airport="LAX", 
            scheduled_departure=datetime.now(),
            scheduled_arrival=datetime.now() + timedelta(hours=6)
        )
        print("✓ Flight model instantiation works")
    except Exception as e:
        print(f"✗ Flight model instantiation failed: {e}")
        
    try:
        traveler = Traveler(
            traveler_id="test_traveler_123",
            user_id="test_user",
            first_name="John",
            last_name="Doe"
        )
        print("✓ Traveler model instantiation works")
    except Exception as e:
        print(f"✗ Traveler model instantiation failed: {e}")
        
    try:
        monitor = TripMonitor(
            monitor_id="test_monitor_123",
            user_id="test_user",
            booking_id="test_booking",
            flight_id="test_flight"
        )
        print("✓ TripMonitor model instantiation works")
    except Exception as e:
        print(f"✗ TripMonitor model instantiation failed: {e}")

    print("✓ Simple validation completed!")


if __name__ == '__main__':
    # First run simple validation
    run_simple_validation()
    
    print("\n" + "="*50 + "\n")
    
    # Run unit tests
    print("Running unit tests...")
    unittest.main(exit=False, verbosity=2)
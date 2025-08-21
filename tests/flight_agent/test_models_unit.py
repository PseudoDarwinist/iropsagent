#!/usr/bin/env python3
"""
Unit Tests for Flight Agent Data Models and Validation - Task 1.4
Comprehensive test suite covering all data models, validation, and business logic

Requirements Coverage:
- REQ-1.1-1.6: Core flight monitoring models
- REQ-2.1-2.6: Alternative flight and disruption models  
- REQ-5.1-5.6: Policy compliance and approval workflow models

Testing Categories:
1. Model validation (field constraints, data types, required fields)
2. Database operations (CRUD operations, queries)
3. Relationship integrity (foreign keys, joins, cascades)
4. Edge cases and error handling
5. Helper function testing
"""

import unittest
import tempfile
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Import all models and helper functions
from flight_agent.models import (
    Base, SessionLocal,
    User, EmailConnection, Flight, Traveler, Booking, TripMonitor, 
    DisruptionEvent, DisruptionAlert, AlternativeFlight, FlightHold,
    Wallet, WalletTransaction, CompensationRule, CompensationRuleHistory,
    TravelPolicy, ApprovalRequest, PolicyException,
    # Helper functions
    create_user, create_flight, create_traveler, create_booking, create_trip_monitor,
    create_disruption_event, create_disruption_alert, create_alternative_flight,
    create_flight_hold, get_or_create_wallet, create_compensation_rule,
    create_travel_policy, create_approval_request, create_policy_exception,
    get_active_travel_policies, get_pending_approval_requests, 
    check_policy_compliance, validate_compensation_rule, update_flight_status,
    get_upcoming_bookings, get_active_trip_monitors
)


class TestCoreModels(unittest.TestCase):
    """Test core model validation and constraints"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        
        # Enable foreign key constraints for SQLite
        @cls.test_engine.event.listens_for(cls.test_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        """Set up test data for each test"""
        self.session = self.TestSession()
        self.unique_id = str(int(datetime.now().timestamp() * 1000000))
        
        # Create test user for relationships
        self.test_user = User(
            user_id=f"test_user_{self.unique_id}",
            email=f"test_{self.unique_id}@example.com",
            phone="+1234567890",
            preferences={"sms": {"enabled": True}}
        )
        self.session.add(self.test_user)
        self.session.commit()
    
    def tearDown(self):
        """Clean up after each test"""
        self.session.rollback()
        self.session.close()

    def test_user_model_creation_and_validation(self):
        """Test User model creation with required and optional fields"""
        # Test minimum required fields
        user = User(
            user_id="minimal_user",
            email="minimal@example.com"
        )
        self.session.add(user)
        self.session.commit()
        
        retrieved = self.session.query(User).filter_by(user_id="minimal_user").first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.email, "minimal@example.com")
        self.assertIsNotNone(retrieved.created_at)
        self.assertEqual(retrieved.preferences, {})
        
        # Test with all fields
        complete_user = User(
            user_id="complete_user",
            email="complete@example.com",
            phone="+1987654321",
            preferences={
                "sms": {"enabled": True, "frequency": "immediate"},
                "email": {"enabled": True, "digest": "daily"}
            }
        )
        self.session.add(complete_user)
        self.session.commit()
        
        retrieved_complete = self.session.query(User).filter_by(user_id="complete_user").first()
        self.assertEqual(retrieved_complete.phone, "+1987654321")
        self.assertTrue(retrieved_complete.preferences["sms"]["enabled"])

    def test_user_email_uniqueness_constraint(self):
        """Test that email uniqueness is enforced"""
        user1 = User(user_id="user1", email="duplicate@example.com")
        user2 = User(user_id="user2", email="duplicate@example.com")
        
        self.session.add(user1)
        self.session.commit()
        
        self.session.add(user2)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_flight_model_validation(self):
        """Test Flight model field validation and constraints"""
        # Test valid flight creation
        flight = Flight(
            flight_id="test_flight_123",
            airline="AA",
            flight_number="1234",
            departure_airport="JFK",
            arrival_airport="LAX",
            scheduled_departure=datetime(2025, 8, 15, 8, 30),
            scheduled_arrival=datetime(2025, 8, 15, 11, 45),
            aircraft_type="Boeing 737",
            gate="A12",
            terminal="1"
        )
        self.session.add(flight)
        self.session.commit()
        
        retrieved = self.session.query(Flight).filter_by(flight_id="test_flight_123").first()
        self.assertEqual(retrieved.airline, "AA")
        self.assertEqual(retrieved.flight_status, "SCHEDULED")
        self.assertEqual(retrieved.delay_minutes, 0)
        self.assertIsNotNone(retrieved.created_at)

    def test_flight_status_values(self):
        """Test valid flight status values"""
        valid_statuses = ["SCHEDULED", "DELAYED", "CANCELLED", "DIVERTED", "COMPLETED"]
        
        for i, status in enumerate(valid_statuses):
            flight = Flight(
                flight_id=f"status_flight_{i}",
                airline="AA",
                flight_number=f"123{i}",
                departure_airport="JFK",
                arrival_airport="LAX",
                scheduled_departure=datetime(2025, 8, 15, 8, 30),
                scheduled_arrival=datetime(2025, 8, 15, 11, 45),
                flight_status=status
            )
            self.session.add(flight)
        
        self.session.commit()
        flights = self.session.query(Flight).filter(Flight.flight_id.like("status_flight_%")).all()
        self.assertEqual(len(flights), len(valid_statuses))

    def test_traveler_model_with_json_fields(self):
        """Test Traveler model with complex JSON data"""
        traveler_data = {
            "frequent_flyer_numbers": {"AA": "12345678", "DL": "87654321"},
            "dietary_restrictions": ["vegetarian", "nut-free", "gluten-free"],
            "emergency_contact": {
                "name": "Jane Doe",
                "phone": "+1987654321",
                "relationship": "Spouse"
            },
            "preferences": {
                "seat": "aisle",
                "meal": "vegetarian"
            }
        }
        
        traveler = Traveler(
            traveler_id="json_traveler",
            user_id=self.test_user.user_id,
            first_name="John",
            last_name="Doe",
            frequent_flyer_numbers=traveler_data["frequent_flyer_numbers"],
            dietary_restrictions=traveler_data["dietary_restrictions"],
            emergency_contact=traveler_data["emergency_contact"],
            preferences=traveler_data["preferences"]
        )
        self.session.add(traveler)
        self.session.commit()
        
        retrieved = self.session.query(Traveler).filter_by(traveler_id="json_traveler").first()
        self.assertEqual(retrieved.frequent_flyer_numbers, traveler_data["frequent_flyer_numbers"])
        self.assertEqual(retrieved.dietary_restrictions, traveler_data["dietary_restrictions"])
        self.assertEqual(retrieved.emergency_contact["name"], "Jane Doe")

    def test_booking_model_relationships(self):
        """Test Booking model with proper relationships"""
        # Create dependencies
        flight = Flight(
            flight_id="booking_flight",
            airline="AA",
            flight_number="1234",
            departure_airport="JFK",
            arrival_airport="LAX",
            scheduled_departure=datetime(2025, 8, 15, 8, 30),
            scheduled_arrival=datetime(2025, 8, 15, 11, 45)
        )
        self.session.add(flight)
        
        traveler = Traveler(
            traveler_id="booking_traveler",
            user_id=self.test_user.user_id,
            first_name="John",
            last_name="Doe"
        )
        self.session.add(traveler)
        self.session.commit()
        
        # Create booking
        booking = Booking(
            booking_id="test_booking",
            user_id=self.test_user.user_id,
            flight_id=flight.flight_id,
            traveler_id=traveler.traveler_id,
            pnr="ABC123",
            airline="AA",
            flight_number="1234",
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin="JFK",
            destination="LAX",
            booking_class="Economy",
            fare_amount=350.00
        )
        self.session.add(booking)
        self.session.commit()
        
        # Test relationships
        retrieved = self.session.query(Booking).filter_by(booking_id="test_booking").first()
        self.assertEqual(retrieved.user.email, self.test_user.email)
        self.assertEqual(retrieved.flight.airline, "AA")
        self.assertEqual(retrieved.traveler.first_name, "John")
        self.assertEqual(retrieved.status, "CONFIRMED")

    def test_trip_monitor_defaults(self):
        """Test TripMonitor model default values"""
        # Create dependencies
        booking = Booking(
            booking_id="monitor_booking",
            user_id=self.test_user.user_id,
            pnr="MON123",
            airline="AA",
            flight_number="1234",
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin="JFK",
            destination="LAX"
        )
        self.session.add(booking)
        
        flight = Flight(
            flight_id="monitor_flight",
            airline="AA",
            flight_number="1234",
            departure_airport="JFK",
            arrival_airport="LAX",
            scheduled_departure=datetime(2025, 8, 15, 8, 30),
            scheduled_arrival=datetime(2025, 8, 15, 11, 45)
        )
        self.session.add(flight)
        self.session.commit()
        
        # Create monitor with minimal data
        monitor = TripMonitor(
            monitor_id="minimal_monitor",
            user_id=self.test_user.user_id,
            booking_id=booking.booking_id,
            flight_id=flight.flight_id
        )
        self.session.add(monitor)
        self.session.commit()
        
        retrieved = self.session.query(TripMonitor).filter_by(monitor_id="minimal_monitor").first()
        self.assertEqual(retrieved.monitor_type, "FULL")
        self.assertTrue(retrieved.is_active)
        self.assertEqual(retrieved.check_frequency_minutes, 30)
        self.assertFalse(retrieved.auto_rebooking_enabled)


class TestAdvancedModels(unittest.TestCase):
    """Test advanced models for disruption handling and alternatives"""
    
    @classmethod
    def setUpClass(cls):
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        self.session = self.TestSession()
        self.unique_id = str(int(datetime.now().timestamp() * 1000000))
        
        # Create test user and booking
        self.test_user = User(
            user_id=f"adv_user_{self.unique_id}",
            email=f"adv_{self.unique_id}@example.com"
        )
        self.session.add(self.test_user)
        
        self.test_booking = Booking(
            booking_id=f"adv_booking_{self.unique_id}",
            user_id=self.test_user.user_id,
            pnr="ADV123",
            airline="AA",
            flight_number="1234",
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin="JFK",
            destination="LAX"
        )
        self.session.add(self.test_booking)
        self.session.commit()
    
    def tearDown(self):
        self.session.rollback()
        self.session.close()

    def test_disruption_event_model(self):
        """Test DisruptionEvent model with compensation tracking"""
        disruption = DisruptionEvent(
            event_id="test_disruption",
            booking_id=self.test_booking.booking_id,
            disruption_type="CANCELLED",
            original_departure=datetime(2025, 8, 15, 8, 30),
            reason="Mechanical issue",
            priority="HIGH",
            compensation_eligible=True,
            compensation_amount=400.00,
            compensation_status="PENDING"
        )
        self.session.add(disruption)
        self.session.commit()
        
        retrieved = self.session.query(DisruptionEvent).filter_by(event_id="test_disruption").first()
        self.assertEqual(retrieved.disruption_type, "CANCELLED")
        self.assertTrue(retrieved.compensation_eligible)
        self.assertEqual(retrieved.compensation_amount, 400.00)
        self.assertFalse(retrieved.user_notified)

    def test_disruption_alert_with_severity(self):
        """Test DisruptionAlert model with risk severity levels"""
        # Create disruption first
        disruption = DisruptionEvent(
            event_id="alert_disruption",
            booking_id=self.test_booking.booking_id,
            disruption_type="DELAYED",
            delay_minutes=90
        )
        self.session.add(disruption)
        self.session.commit()
        
        alert = DisruptionAlert(
            alert_id="severity_alert",
            event_id=disruption.event_id,
            user_id=self.test_user.user_id,
            alert_type="SMS",
            risk_severity="CRITICAL",
            alert_message="Critical delay: Your flight is delayed by 90 minutes",
            urgency_score=90,
            expires_at=datetime.now() + timedelta(hours=6)
        )
        self.session.add(alert)
        self.session.commit()
        
        retrieved = self.session.query(DisruptionAlert).filter_by(alert_id="severity_alert").first()
        self.assertEqual(retrieved.risk_severity, "CRITICAL")
        self.assertEqual(retrieved.urgency_score, 90)
        self.assertEqual(retrieved.delivery_status, "PENDING")

    def test_alternative_flight_with_policy_compliance(self):
        """Test AlternativeFlight model with policy compliance flags"""
        # Create disruption
        disruption = DisruptionEvent(
            event_id="alt_disruption",
            booking_id=self.test_booking.booking_id,
            disruption_type="CANCELLED"
        )
        self.session.add(disruption)
        self.session.commit()
        
        alternative = AlternativeFlight(
            alternative_id="policy_alt",
            event_id=disruption.event_id,
            flight_number="AA5678",
            airline="AA",
            departure_time=datetime(2025, 8, 15, 10, 30),
            arrival_time=datetime(2025, 8, 15, 13, 45),
            origin="JFK",
            destination="LAX",
            booking_class="Economy",
            available_seats=5,
            price=50.00,
            policy_compliant=True,
            class_downgrade_approved=False,
            airline_restriction_compliant=True,
            recommended_rank=1,
            user_preference_score=85
        )
        self.session.add(alternative)
        self.session.commit()
        
        retrieved = self.session.query(AlternativeFlight).filter_by(alternative_id="policy_alt").first()
        self.assertTrue(retrieved.policy_compliant)
        self.assertEqual(retrieved.recommended_rank, 1)
        self.assertEqual(retrieved.user_preference_score, 85)

    def test_flight_hold_management(self):
        """Test FlightHold model with expiration and extension"""
        hold_expires_at = datetime.now() + timedelta(minutes=30)
        
        hold = FlightHold(
            hold_id="test_hold",
            booking_id=self.test_booking.booking_id,
            user_id=self.test_user.user_id,
            flight_number="AA5678",
            airline="AA",
            departure_time=datetime(2025, 8, 15, 10, 30),
            arrival_time=datetime(2025, 8, 15, 13, 45),
            origin="JFK",
            destination="LAX",
            booking_class="Economy",
            hold_duration_minutes=30,
            hold_expires_at=hold_expires_at,
            price_locked=375.00,
            seats_held=2,
            max_extensions_allowed=3
        )
        self.session.add(hold)
        self.session.commit()
        
        retrieved = self.session.query(FlightHold).filter_by(hold_id="test_hold").first()
        self.assertEqual(retrieved.hold_status, "ACTIVE")
        self.assertEqual(retrieved.seats_held, 2)
        self.assertEqual(retrieved.extension_count, 0)


class TestPolicyAndApprovalModels(unittest.TestCase):
    """Test policy compliance and approval workflow models"""
    
    @classmethod
    def setUpClass(cls):
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        self.session = self.TestSession()
        self.unique_id = str(int(datetime.now().timestamp() * 1000000))
        
        self.test_user = User(
            user_id=f"policy_user_{self.unique_id}",
            email=f"policy_{self.unique_id}@example.com"
        )
        self.session.add(self.test_user)
        self.session.commit()
    
    def tearDown(self):
        self.session.rollback()
        self.session.close()

    def test_travel_policy_with_complex_rules(self):
        """Test TravelPolicy model with comprehensive rule structure"""
        rules = {
            'booking_limits': {
                'max_fare_amount': 1000,
                'allowed_booking_classes': ['Economy', 'Premium Economy'],
                'advance_booking_days': 7,
                'preferred_airlines': ['AA', 'DL', 'UA']
            },
            'expense_limits': {
                'max_hotel_rate': 200,
                'max_meal_allowance': 50
            },
            'approval_thresholds': {
                'auto_approve_below': 500,
                'manager_approval_below': 2000
            }
        }
        
        policy = TravelPolicy(
            policy_id="comprehensive_policy",
            policy_name="Comprehensive Travel Policy",
            description="Full corporate travel policy",
            policy_type="BOOKING",
            rules=rules,
            effective_date=datetime(2025, 1, 1),
            enforcement_level="STRICT",
            created_by="policy_admin"
        )
        self.session.add(policy)
        self.session.commit()
        
        retrieved = self.session.query(TravelPolicy).filter_by(policy_id="comprehensive_policy").first()
        self.assertEqual(retrieved.enforcement_level, "STRICT")
        self.assertTrue(retrieved.auto_compliance_check)
        self.assertEqual(retrieved.rules['booking_limits']['max_fare_amount'], 1000)

    def test_approval_request_with_escalation_chain(self):
        """Test ApprovalRequest model with escalation management"""
        escalation_chain = [
            {"level": 0, "approver_role": "manager", "approver_id": "mgr_123", "timeout_hours": 24},
            {"level": 1, "approver_role": "director", "approver_id": "dir_456", "timeout_hours": 48}
        ]
        
        request_data = {
            'booking_details': {'fare_amount': 1500, 'class': 'Business'},
            'policy_violations': ['fare_limit_exceeded'],
            'business_justification': 'Critical client meeting'
        }
        
        approval_request = ApprovalRequest(
            request_id="escalation_request",
            user_id=self.test_user.user_id,
            request_type="BOOKING_APPROVAL",
            title="Business Class Approval Request",
            description="Request approval for business class booking",
            request_data=request_data,
            escalation_chain=escalation_chain,
            current_approver_id="mgr_123",
            current_approver_role="manager",
            approval_history=[{
                "timestamp": datetime.now().isoformat(),
                "action": "CREATED",
                "user_id": self.test_user.user_id
            }]
        )
        self.session.add(approval_request)
        self.session.commit()
        
        retrieved = self.session.query(ApprovalRequest).filter_by(request_id="escalation_request").first()
        self.assertEqual(retrieved.status, "PENDING")
        self.assertEqual(retrieved.escalation_level, 0)
        self.assertEqual(retrieved.current_approver_id, "mgr_123")

    def test_policy_exception_violation_tracking(self):
        """Test PolicyException model for tracking violations"""
        # Create policy first
        policy = TravelPolicy(
            policy_id="exception_policy",
            policy_name="Test Policy",
            description="Test policy for exceptions",
            policy_type="BOOKING",
            rules={'booking_limits': {'max_fare_amount': 1000}},
            effective_date=datetime(2025, 1, 1),
            created_by="admin"
        )
        self.session.add(policy)
        
        booking = Booking(
            booking_id="exception_booking",
            user_id=self.test_user.user_id,
            pnr="EXC123",
            airline="AA",
            flight_number="1234",
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin="JFK",
            destination="LAX",
            fare_amount=1500.00
        )
        self.session.add(booking)
        self.session.commit()
        
        violation_details = {
            'rule_path': 'booking_limits.max_fare_amount',
            'policy_value': 1000,
            'actual_value': 1500,
            'violation_percentage': 50
        }
        
        exception = PolicyException(
            exception_id="fare_violation",
            booking_id=booking.booking_id,
            policy_id=policy.policy_id,
            exception_type="RULE_VIOLATION",
            violation_category="BOOKING_LIMIT",
            severity="HIGH",
            violated_rule="booking_limits.max_fare_amount",
            expected_value="1000",
            actual_value="1500",
            violation_amount=500.0,
            title="Fare Limit Exceeded",
            description="Booking fare exceeds maximum allowed",
            violation_details=violation_details,
            cost_impact=500.0
        )
        self.session.add(exception)
        self.session.commit()
        
        retrieved = self.session.query(PolicyException).filter_by(exception_id="fare_violation").first()
        self.assertEqual(retrieved.violation_category, "BOOKING_LIMIT")
        self.assertEqual(retrieved.severity, "HIGH")
        self.assertEqual(retrieved.violation_amount, 500.0)


class TestHelperFunctions(unittest.TestCase):
    """Test model helper functions and business logic"""
    
    @classmethod
    def setUpClass(cls):
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        # Patch SessionLocal to use test session
        self.session_patcher = patch('flight_agent.models.SessionLocal', self.TestSession)
        self.session_patcher.start()
        
        self.unique_id = str(int(datetime.now().timestamp() * 1000000))
    
    def tearDown(self):
        self.session_patcher.stop()

    def test_create_user_helper_function(self):
        """Test create_user helper function"""
        email = f'helper_{self.unique_id}@example.com'
        phone = '+1234567890'
        
        user = create_user(email=email, phone=phone)
        
        self.assertIsNotNone(user)
        self.assertEqual(user.email, email)
        self.assertEqual(user.phone, phone)
        self.assertTrue(user.user_id.startswith('user_'))

    def test_create_flight_helper_function(self):
        """Test create_flight helper function"""
        flight_data = {
            'airline': 'AA',
            'flight_number': '1234',
            'departure_airport': 'JFK',
            'arrival_airport': 'LAX',
            'scheduled_departure': datetime(2025, 8, 15, 8, 30),
            'scheduled_arrival': datetime(2025, 8, 15, 11, 45),
            'aircraft_type': 'Boeing 737',
            'gate': 'A12'
        }
        
        flight = create_flight(flight_data)
        
        self.assertIsNotNone(flight)
        self.assertEqual(flight.airline, 'AA')
        self.assertEqual(flight.flight_number, '1234')
        self.assertEqual(flight.aircraft_type, 'Boeing 737')

    def test_compensation_rule_validation(self):
        """Test compensation rule validation helper"""
        # Valid rule
        valid_rule = {
            'rule_name': 'Test Rule',
            'description': 'Test compensation rule',
            'disruption_type': 'CANCELLED',
            'amount': 400.0,
            'priority': 10
        }
        
        validation = validate_compensation_rule(valid_rule)
        self.assertTrue(validation['valid'])
        self.assertEqual(len(validation['errors']), 0)
        
        # Invalid rule (missing required fields)
        invalid_rule = {
            'rule_name': 'Incomplete Rule'
            # Missing description, disruption_type, amount
        }
        
        invalid_validation = validate_compensation_rule(invalid_rule)
        self.assertFalse(invalid_validation['valid'])
        self.assertGreater(len(invalid_validation['errors']), 0)

    def test_policy_compliance_checking(self):
        """Test policy compliance checking function"""
        # Create a policy
        policy_data = {
            'policy_name': 'Test Policy',
            'description': 'Test policy for compliance',
            'policy_type': 'BOOKING',
            'rules': {
                'booking_limits': {
                    'max_fare_amount': 1000,
                    'allowed_booking_classes': ['Economy'],
                    'advance_booking_days': 7
                }
            },
            'effective_date': datetime(2025, 1, 1)
        }
        
        policy = create_travel_policy(policy_data, 'test_admin')
        
        # Test violating booking data
        violating_booking = {
            'fare_amount': 1500,  # Exceeds limit
            'booking_class': 'Business',  # Not allowed
            'departure_date': datetime.now() + timedelta(days=2)  # Too short advance
        }
        
        violations = check_policy_compliance(violating_booking, [policy])
        
        self.assertGreater(len(violations), 0)
        violation_types = [v['violation_type'] for v in violations]
        self.assertIn('FARE_LIMIT_EXCEEDED', violation_types)


class TestDatabaseOperations(unittest.TestCase):
    """Test CRUD operations and database integrity"""
    
    @classmethod
    def setUpClass(cls):
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        self.session = self.TestSession()
        self.unique_id = str(int(datetime.now().timestamp() * 1000000))
    
    def tearDown(self):
        self.session.rollback()
        self.session.close()

    def test_crud_operations(self):
        """Test basic CRUD operations"""
        # CREATE
        user = User(
            user_id=f'crud_{self.unique_id}',
            email=f'crud_{self.unique_id}@example.com',
            phone='+1234567890'
        )
        self.session.add(user)
        self.session.commit()
        
        # READ
        retrieved = self.session.query(User).filter_by(user_id=f'crud_{self.unique_id}').first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.email, f'crud_{self.unique_id}@example.com')
        
        # UPDATE
        retrieved.phone = '+9876543210'
        self.session.commit()
        
        updated = self.session.query(User).filter_by(user_id=f'crud_{self.unique_id}').first()
        self.assertEqual(updated.phone, '+9876543210')
        
        # DELETE
        self.session.delete(updated)
        self.session.commit()
        
        deleted = self.session.query(User).filter_by(user_id=f'crud_{self.unique_id}').first()
        self.assertIsNone(deleted)

    def test_relationship_queries(self):
        """Test complex relationship queries"""
        # Create related entities
        user = User(
            user_id=f'rel_{self.unique_id}',
            email=f'rel_{self.unique_id}@example.com'
        )
        self.session.add(user)
        
        flight = Flight(
            flight_id=f'rel_flight_{self.unique_id}',
            airline='AA',
            flight_number='1234',
            departure_airport='JFK',
            arrival_airport='LAX',
            scheduled_departure=datetime(2025, 8, 15, 8, 30),
            scheduled_arrival=datetime(2025, 8, 15, 11, 45),
            flight_status='DELAYED'
        )
        self.session.add(flight)
        
        booking = Booking(
            booking_id=f'rel_booking_{self.unique_id}',
            user_id=user.user_id,
            flight_id=flight.flight_id,
            pnr='REL123',
            airline='AA',
            flight_number='1234',
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin='JFK',
            destination='LAX'
        )
        self.session.add(booking)
        self.session.commit()
        
        # Test JOIN query
        result = self.session.query(Booking, Flight, User).join(Flight).join(User).filter(
            Flight.flight_status == 'DELAYED'
        ).first()
        
        self.assertIsNotNone(result)
        booking_result, flight_result, user_result = result
        self.assertEqual(booking_result.pnr, 'REL123')
        self.assertEqual(flight_result.flight_status, 'DELAYED')


if __name__ == '__main__':
    # Create test suite with all test classes
    test_classes = [
        TestCoreModels,
        TestAdvancedModels, 
        TestPolicyAndApprovalModels,
        TestHelperFunctions,
        TestDatabaseOperations
    ]
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"UNIT TESTS FOR DATA MODELS - TASK 1.4 SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.testsRun > 0:
        success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100)
        print(f"Success rate: {success_rate:.1f}%")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}")
    
    print(f"\n✅ Task 1.4: Unit tests for data models and validation completed!")
    
    # Exit with appropriate code
    exit_code = 0 if len(result.failures) == 0 and len(result.errors) == 0 else 1
    exit(exit_code)
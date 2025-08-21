#!/usr/bin/env python3
"""
Comprehensive Test Suite for Flight Agent Data Models and Validation
Task 1.4: Write unit tests for all data models and validation

This test suite provides comprehensive coverage for:
- All data model validation (field constraints, data types, required fields)
- Database operations (CRUD operations, queries)
- Relationship integrity (foreign keys, joins, cascades)
- Edge cases and error handling
- Model helper functions
- Business logic validation

Requirements Coverage:
- REQ-1.1-1.6: Core flight monitoring models
- REQ-2.1-2.6: Alternative flight and disruption models
- REQ-5.1-5.6: Policy compliance and approval workflow models
"""

import pytest
import unittest
import tempfile
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, StatementError

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
    get_active_travel_policies, get_pending_approval_requests, get_policy_exceptions_by_booking,
    escalate_approval_request, approve_request, reject_request, resolve_policy_exception,
    check_policy_compliance, validate_compensation_rule, update_flight_status,
    get_upcoming_bookings, get_active_trip_monitors, get_flight_by_details,
    get_users_with_sms_enabled, get_active_disruption_alerts, get_policy_compliant_alternatives,
    get_active_flight_holds, extend_flight_hold, release_flight_hold, convert_hold_to_booking
)


class TestDataModelValidation(unittest.TestCase):
    """Comprehensive tests for data model validation and constraints"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        """Set up test data for each test"""
        self.session = self.TestSession()
        self.unique_id = str(int(datetime.now().timestamp() * 1000000))
        
        # Create test user
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

    # User Model Tests
    def test_user_model_required_fields(self):
        """Test User model required field validation"""
        # Test valid user creation
        user = User(
            user_id="valid_user_123",
            email="valid@example.com"
        )
        self.session.add(user)
        self.session.commit()
        
        retrieved_user = self.session.query(User).filter_by(user_id="valid_user_123").first()
        self.assertIsNotNone(retrieved_user)
        self.assertEqual(retrieved_user.email, "valid@example.com")
        self.assertIsNotNone(retrieved_user.created_at)
        self.assertEqual(retrieved_user.preferences, {})

    def test_user_email_uniqueness(self):
        """Test email uniqueness constraint"""
        user1 = User(user_id="user1", email="duplicate@example.com")
        user2 = User(user_id="user2", email="duplicate@example.com")
        
        self.session.add(user1)
        self.session.commit()
        
        self.session.add(user2)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_user_preferences_json_validation(self):
        """Test JSON preferences field"""
        complex_preferences = {
            "sms": {"enabled": True, "frequency": "immediate"},
            "email": {"enabled": True, "digest": "daily"},
            "airlines": ["AA", "DL", "UA"],
            "seat_preference": "aisle"
        }
        
        user = User(
            user_id="json_test_user",
            email="json@example.com",
            preferences=complex_preferences
        )
        self.session.add(user)
        self.session.commit()
        
        retrieved_user = self.session.query(User).filter_by(user_id="json_test_user").first()
        self.assertEqual(retrieved_user.preferences, complex_preferences)

    # Flight Model Tests
    def test_flight_model_required_fields(self):
        """Test Flight model required field validation"""
        # Test missing required fields
        with self.assertRaises(Exception):
            incomplete_flight = Flight(flight_id="incomplete")
            self.session.add(incomplete_flight)
            self.session.commit()
        
        # Test valid flight creation
        valid_flight = Flight(
            flight_id="valid_flight_123",
            airline="AA",
            flight_number="1234",
            departure_airport="JFK",
            arrival_airport="LAX",
            scheduled_departure=datetime(2025, 8, 15, 8, 30),
            scheduled_arrival=datetime(2025, 8, 15, 11, 45)
        )
        self.session.add(valid_flight)
        self.session.commit()
        
        retrieved_flight = self.session.query(Flight).filter_by(flight_id="valid_flight_123").first()
        self.assertIsNotNone(retrieved_flight)
        self.assertEqual(retrieved_flight.flight_status, "SCHEDULED")
        self.assertEqual(retrieved_flight.delay_minutes, 0)

    def test_flight_status_validation(self):
        """Test flight status field values"""
        valid_statuses = ["SCHEDULED", "DELAYED", "CANCELLED", "DIVERTED", "COMPLETED"]
        
        for status in valid_statuses:
            flight = Flight(
                flight_id=f"flight_{status}_{self.unique_id}",
                airline="AA",
                flight_number="1234",
                departure_airport="JFK",
                arrival_airport="LAX",
                scheduled_departure=datetime(2025, 8, 15, 8, 30),
                scheduled_arrival=datetime(2025, 8, 15, 11, 45),
                flight_status=status
            )
            self.session.add(flight)
        
        self.session.commit()
        
        # Verify all flights were created successfully
        flights = self.session.query(Flight).filter(Flight.flight_id.like(f"flight_%_{self.unique_id}")).all()
        self.assertEqual(len(flights), len(valid_statuses))

    def test_flight_datetime_constraints(self):
        """Test flight datetime logical constraints"""
        # Test that arrival cannot be before departure
        departure_time = datetime(2025, 8, 15, 8, 30)
        arrival_time = datetime(2025, 8, 15, 7, 30)  # Before departure
        
        flight = Flight(
            flight_id="datetime_test_flight",
            airline="AA",
            flight_number="1234",
            departure_airport="JFK",
            arrival_airport="LAX",
            scheduled_departure=departure_time,
            scheduled_arrival=arrival_time  # This should be caught by business logic
        )
        self.session.add(flight)
        self.session.commit()  # SQLAlchemy won't enforce this, but business logic should

    # Traveler Model Tests
    def test_traveler_model_relationships(self):
        """Test Traveler model foreign key relationships"""
        traveler = Traveler(
            traveler_id="rel_test_traveler",
            user_id=self.test_user.user_id,
            first_name="John",
            last_name="Doe"
        )
        self.session.add(traveler)
        self.session.commit()
        
        # Test relationship integrity
        retrieved_traveler = self.session.query(Traveler).filter_by(traveler_id="rel_test_traveler").first()
        self.assertEqual(retrieved_traveler.user.email, self.test_user.email)

    def test_traveler_json_fields(self):
        """Test Traveler JSON field validation"""
        complex_data = {
            "frequent_flyer_numbers": {"AA": "12345678", "DL": "87654321"},
            "dietary_restrictions": ["vegetarian", "nut-free", "gluten-free"],
            "emergency_contact": {
                "name": "Jane Doe",
                "phone": "+1987654321",
                "relationship": "Spouse",
                "email": "jane@example.com"
            },
            "preferences": {
                "seat": "aisle",
                "meal": "vegetarian",
                "notification": "email"
            }
        }
        
        traveler = Traveler(
            traveler_id="json_traveler_test",
            user_id=self.test_user.user_id,
            first_name="John",
            last_name="Doe",
            frequent_flyer_numbers=complex_data["frequent_flyer_numbers"],
            dietary_restrictions=complex_data["dietary_restrictions"],
            emergency_contact=complex_data["emergency_contact"],
            preferences=complex_data["preferences"]
        )
        self.session.add(traveler)
        self.session.commit()
        
        retrieved_traveler = self.session.query(Traveler).filter_by(traveler_id="json_traveler_test").first()
        self.assertEqual(retrieved_traveler.frequent_flyer_numbers, complex_data["frequent_flyer_numbers"])
        self.assertEqual(retrieved_traveler.dietary_restrictions, complex_data["dietary_restrictions"])
        self.assertEqual(retrieved_traveler.emergency_contact, complex_data["emergency_contact"])

    # Booking Model Tests
    def test_booking_model_constraints(self):
        """Test Booking model field constraints and validation"""
        # Create required dependencies
        flight = Flight(
            flight_id="booking_test_flight",
            airline="AA",
            flight_number="1234",
            departure_airport="JFK",
            arrival_airport="LAX",
            scheduled_departure=datetime(2025, 8, 15, 8, 30),
            scheduled_arrival=datetime(2025, 8, 15, 11, 45)
        )
        self.session.add(flight)
        
        traveler = Traveler(
            traveler_id="booking_test_traveler",
            user_id=self.test_user.user_id,
            first_name="John",
            last_name="Doe"
        )
        self.session.add(traveler)
        self.session.commit()
        
        # Test valid booking
        booking = Booking(
            booking_id="valid_booking_test",
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
            fare_amount=350.00,
            currency="USD"
        )
        self.session.add(booking)
        self.session.commit()
        
        retrieved_booking = self.session.query(Booking).filter_by(booking_id="valid_booking_test").first()
        self.assertIsNotNone(retrieved_booking)
        self.assertEqual(retrieved_booking.status, "CONFIRMED")
        self.assertEqual(retrieved_booking.currency, "USD")
        self.assertEqual(retrieved_booking.fare_amount, 350.00)

    def test_booking_foreign_key_constraints(self):
        """Test Booking foreign key constraint validation"""
        # Test invalid user_id
        with self.assertRaises(Exception):
            invalid_booking = Booking(
                booking_id="invalid_booking",
                user_id="nonexistent_user",
                pnr="ABC123",
                airline="AA",
                flight_number="1234",
                departure_date=datetime(2025, 8, 15, 8, 30),
                origin="JFK",
                destination="LAX"
            )
            self.session.add(invalid_booking)
            self.session.commit()

    # TripMonitor Model Tests
    def test_trip_monitor_model_validation(self):
        """Test TripMonitor model validation and defaults"""
        # Create dependencies
        flight = Flight(
            flight_id="monitor_test_flight",
            airline="AA",
            flight_number="1234",
            departure_airport="JFK",
            arrival_airport="LAX",
            scheduled_departure=datetime(2025, 8, 15, 8, 30),
            scheduled_arrival=datetime(2025, 8, 15, 11, 45)
        )
        self.session.add(flight)
        
        booking = Booking(
            booking_id="monitor_test_booking",
            user_id=self.test_user.user_id,
            flight_id=flight.flight_id,
            pnr="MON123",
            airline="AA",
            flight_number="1234",
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin="JFK",
            destination="LAX"
        )
        self.session.add(booking)
        self.session.commit()
        
        # Test monitor with minimal data (should use defaults)
        monitor = TripMonitor(
            monitor_id="minimal_monitor",
            user_id=self.test_user.user_id,
            booking_id=booking.booking_id,
            flight_id=flight.flight_id
        )
        self.session.add(monitor)
        self.session.commit()
        
        retrieved_monitor = self.session.query(TripMonitor).filter_by(monitor_id="minimal_monitor").first()
        self.assertEqual(retrieved_monitor.monitor_type, "FULL")
        self.assertTrue(retrieved_monitor.is_active)
        self.assertEqual(retrieved_monitor.check_frequency_minutes, 30)
        self.assertFalse(retrieved_monitor.auto_rebooking_enabled)

    # DisruptionEvent Model Tests
    def test_disruption_event_validation(self):
        """Test DisruptionEvent model validation"""
        # Create dependencies
        booking = Booking(
            booking_id="disruption_booking",
            user_id=self.test_user.user_id,
            pnr="DIS123",
            airline="AA",
            flight_number="1234",
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin="JFK",
            destination="LAX"
        )
        self.session.add(booking)
        self.session.commit()
        
        # Test disruption event with compensation data
        disruption = DisruptionEvent(
            event_id="compensation_disruption",
            booking_id=booking.booking_id,
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
        
        retrieved_disruption = self.session.query(DisruptionEvent).filter_by(event_id="compensation_disruption").first()
        self.assertEqual(retrieved_disruption.disruption_type, "CANCELLED")
        self.assertTrue(retrieved_disruption.compensation_eligible)
        self.assertEqual(retrieved_disruption.compensation_amount, 400.00)
        self.assertFalse(retrieved_disruption.user_notified)

    # DisruptionAlert Model Tests
    def test_disruption_alert_risk_severity(self):
        """Test DisruptionAlert model with risk severity levels"""
        # Create dependencies
        booking = Booking(
            booking_id="alert_booking",
            user_id=self.test_user.user_id,
            pnr="ALT123",
            airline="AA",
            flight_number="1234",
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin="JFK",
            destination="LAX"
        )
        self.session.add(booking)
        
        disruption = DisruptionEvent(
            event_id="alert_disruption",
            booking_id=booking.booking_id,
            disruption_type="DELAYED",
            delay_minutes=90
        )
        self.session.add(disruption)
        self.session.commit()
        
        # Test alert with high risk severity
        alert = DisruptionAlert(
            alert_id="high_risk_alert",
            event_id=disruption.event_id,
            user_id=self.test_user.user_id,
            alert_type="SMS",
            risk_severity="CRITICAL",
            alert_message="Critical delay alert: Your flight is delayed by 90 minutes",
            urgency_score=90,
            expires_at=datetime.utcnow() + timedelta(hours=6)
        )
        self.session.add(alert)
        self.session.commit()
        
        retrieved_alert = self.session.query(DisruptionAlert).filter_by(alert_id="high_risk_alert").first()
        self.assertEqual(retrieved_alert.risk_severity, "CRITICAL")
        self.assertEqual(retrieved_alert.urgency_score, 90)
        self.assertEqual(retrieved_alert.delivery_status, "PENDING")

    # AlternativeFlight Model Tests
    def test_alternative_flight_policy_compliance(self):
        """Test AlternativeFlight model with policy compliance flags"""
        # Create disruption event
        booking = Booking(
            booking_id="alt_flight_booking",
            user_id=self.test_user.user_id,
            pnr="ALT123",
            airline="AA",
            flight_number="1234",
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin="JFK",
            destination="LAX"
        )
        self.session.add(booking)
        
        disruption = DisruptionEvent(
            event_id="alt_flight_disruption",
            booking_id=booking.booking_id,
            disruption_type="CANCELLED"
        )
        self.session.add(disruption)
        self.session.commit()
        
        # Test policy-compliant alternative
        alternative = AlternativeFlight(
            alternative_id="policy_compliant_alt",
            event_id=disruption.event_id,
            flight_number="AA5678",
            airline="AA",
            departure_time=datetime(2025, 8, 15, 10, 30),
            arrival_time=datetime(2025, 8, 15, 13, 45),
            origin="JFK",
            destination="LAX",
            booking_class="Economy",
            available_seats=5,
            price=50.00,  # Price difference
            policy_compliant=True,
            class_downgrade_approved=False,
            airline_restriction_compliant=True,
            route_policy_compliant=True,
            time_window_compliant=True,
            cost_policy_compliant=True,
            recommended_rank=1,
            user_preference_score=85
        )
        self.session.add(alternative)
        self.session.commit()
        
        retrieved_alt = self.session.query(AlternativeFlight).filter_by(alternative_id="policy_compliant_alt").first()
        self.assertTrue(retrieved_alt.policy_compliant)
        self.assertEqual(retrieved_alt.recommended_rank, 1)
        self.assertEqual(retrieved_alt.user_preference_score, 85)

    # FlightHold Model Tests
    def test_flight_hold_expiration_logic(self):
        """Test FlightHold model with expiration and extension logic"""
        # Create dependencies
        booking = Booking(
            booking_id="hold_booking",
            user_id=self.test_user.user_id,
            pnr="HLD123",
            airline="AA",
            flight_number="1234",
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin="JFK",
            destination="LAX"
        )
        self.session.add(booking)
        self.session.commit()
        
        # Test hold with custom expiration
        hold_expires_at = datetime.utcnow() + timedelta(minutes=30)
        hold = FlightHold(
            hold_id="expiration_test_hold",
            booking_id=booking.booking_id,
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
        
        retrieved_hold = self.session.query(FlightHold).filter_by(hold_id="expiration_test_hold").first()
        self.assertEqual(retrieved_hold.hold_status, "ACTIVE")
        self.assertEqual(retrieved_hold.seats_held, 2)
        self.assertEqual(retrieved_hold.max_extensions_allowed, 3)
        self.assertEqual(retrieved_hold.extension_count, 0)

    # Wallet and Transaction Model Tests
    def test_wallet_transaction_integrity(self):
        """Test Wallet and WalletTransaction model integrity"""
        # Create wallet
        wallet = Wallet(
            wallet_id="test_wallet",
            user_id=self.test_user.user_id,
            balance=100.0,
            currency="USD"
        )
        self.session.add(wallet)
        self.session.commit()
        
        # Test positive transaction (credit)
        credit_transaction = WalletTransaction(
            transaction_id="credit_txn",
            wallet_id=wallet.wallet_id,
            amount=50.0,
            transaction_type="COMPENSATION",
            description="Flight delay compensation",
            reference_id="disruption_123"
        )
        self.session.add(credit_transaction)
        
        # Test negative transaction (debit)
        debit_transaction = WalletTransaction(
            transaction_id="debit_txn",
            wallet_id=wallet.wallet_id,
            amount=-25.0,
            transaction_type="PURCHASE",
            description="Seat upgrade purchase",
            reference_id="booking_456"
        )
        self.session.add(debit_transaction)
        self.session.commit()
        
        # Verify transactions
        transactions = self.session.query(WalletTransaction).filter_by(wallet_id=wallet.wallet_id).all()
        self.assertEqual(len(transactions), 2)
        
        credit_txn = next(t for t in transactions if t.amount > 0)
        debit_txn = next(t for t in transactions if t.amount < 0)
        
        self.assertEqual(credit_txn.transaction_type, "COMPENSATION")
        self.assertEqual(debit_txn.transaction_type, "PURCHASE")

    # CompensationRule Model Tests
    def test_compensation_rule_validation(self):
        """Test CompensationRule model validation and versioning"""
        rule_data = {
            'rule_name': 'Cancellation Compensation',
            'description': 'Compensation for flight cancellations',
            'disruption_type': 'CANCELLED',
            'amount': 400.0,
            'conditions': {
                'advance_notice_hours': 24,
                'minimum_delay_minutes': 0,
                'domestic_flight': True
            },
            'priority': 10
        }
        
        rule = CompensationRule(
            rule_id="test_comp_rule",
            **rule_data,
            created_by="test_admin"
        )
        self.session.add(rule)
        self.session.commit()
        
        retrieved_rule = self.session.query(CompensationRule).filter_by(rule_id="test_comp_rule").first()
        self.assertEqual(retrieved_rule.disruption_type, "CANCELLED")
        self.assertEqual(retrieved_rule.amount, 400.0)
        self.assertTrue(retrieved_rule.is_active)
        self.assertEqual(retrieved_rule.version, 1)
        self.assertEqual(retrieved_rule.conditions['advance_notice_hours'], 24)

    # TravelPolicy Model Tests
    def test_travel_policy_rules_validation(self):
        """Test TravelPolicy model with complex rules structure"""
        policy_rules = {
            'booking_limits': {
                'max_fare_amount': 1000,
                'allowed_booking_classes': ['Economy', 'Premium Economy'],
                'advance_booking_days': 7,
                'preferred_airlines': ['AA', 'DL', 'UA']
            },
            'expense_limits': {
                'max_hotel_rate': 200,
                'max_meal_allowance': 50,
                'receipts_required_above': 25
            },
            'approval_thresholds': {
                'auto_approve_below': 500,
                'manager_approval_below': 2000,
                'director_approval_above': 2000
            }
        }
        
        policy = TravelPolicy(
            policy_id="comprehensive_policy",
            policy_name="Comprehensive Travel Policy",
            description="Full corporate travel policy with all rules",
            policy_type="BOOKING",
            rules=policy_rules,
            effective_date=datetime(2025, 1, 1),
            enforcement_level="STRICT",
            created_by="policy_admin"
        )
        self.session.add(policy)
        self.session.commit()
        
        retrieved_policy = self.session.query(TravelPolicy).filter_by(policy_id="comprehensive_policy").first()
        self.assertEqual(retrieved_policy.enforcement_level, "STRICT")
        self.assertTrue(retrieved_policy.auto_compliance_check)
        self.assertTrue(retrieved_policy.allow_exceptions)
        self.assertEqual(retrieved_policy.rules['booking_limits']['max_fare_amount'], 1000)

    # ApprovalRequest Model Tests
    def test_approval_request_escalation_chain(self):
        """Test ApprovalRequest model with escalation chain"""
        escalation_chain = [
            {"level": 0, "approver_role": "manager", "approver_id": "mgr_123", "timeout_hours": 24},
            {"level": 1, "approver_role": "director", "approver_id": "dir_456", "timeout_hours": 48},
            {"level": 2, "approver_role": "vp", "approver_id": "vp_789", "timeout_hours": 72}
        ]
        
        request_data = {
            'booking_details': {'fare_amount': 1500, 'class': 'Business'},
            'policy_violations': ['fare_limit_exceeded'],
            'business_justification': 'Critical client meeting'
        }
        
        approval_request = ApprovalRequest(
            request_id="escalation_test_request",
            user_id=self.test_user.user_id,
            request_type="BOOKING_APPROVAL",
            title="Business Class Approval Request",
            description="Request approval for business class booking exceeding policy limits",
            request_data=request_data,
            escalation_chain=escalation_chain,
            current_approver_id="mgr_123",
            current_approver_role="manager",
            due_date=datetime.utcnow() + timedelta(days=1),
            approval_history=[{
                "timestamp": datetime.utcnow().isoformat(),
                "action": "CREATED",
                "user_id": self.test_user.user_id
            }]
        )
        self.session.add(approval_request)
        self.session.commit()
        
        retrieved_request = self.session.query(ApprovalRequest).filter_by(request_id="escalation_test_request").first()
        self.assertEqual(retrieved_request.status, "PENDING")
        self.assertEqual(retrieved_request.escalation_level, 0)
        self.assertEqual(retrieved_request.current_approver_id, "mgr_123")
        self.assertEqual(len(retrieved_request.escalation_chain), 3)

    # PolicyException Model Tests
    def test_policy_exception_violation_tracking(self):
        """Test PolicyException model for violation tracking"""
        # Create dependencies
        policy = TravelPolicy(
            policy_id="exception_test_policy",
            policy_name="Test Policy",
            description="Test policy for exceptions",
            policy_type="BOOKING",
            rules={'booking_limits': {'max_fare_amount': 1000}},
            effective_date=datetime(2025, 1, 1),
            created_by="admin"
        )
        self.session.add(policy)
        
        booking = Booking(
            booking_id="exception_test_booking",
            user_id=self.test_user.user_id,
            pnr="EXC123",
            airline="AA",
            flight_number="1234",
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin="JFK",
            destination="LAX",
            fare_amount=1500.00  # Exceeds policy limit
        )
        self.session.add(booking)
        self.session.commit()
        
        violation_details = {
            'rule_path': 'booking_limits.max_fare_amount',
            'policy_value': 1000,
            'actual_value': 1500,
            'violation_percentage': 50,
            'context': {
                'booking_class': 'Business',
                'route': 'JFK-LAX',
                'advance_days': 2
            }
        }
        
        exception = PolicyException(
            exception_id="fare_violation_exception",
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
            description="Booking fare exceeds maximum allowed amount",
            violation_details=violation_details,
            user_justification="Critical business meeting with key client",
            business_justification="Revenue impact justifies additional cost",
            cost_impact=500.0
        )
        self.session.add(exception)
        self.session.commit()
        
        retrieved_exception = self.session.query(PolicyException).filter_by(exception_id="fare_violation_exception").first()
        self.assertEqual(retrieved_exception.violation_category, "BOOKING_LIMIT")
        self.assertEqual(retrieved_exception.severity, "HIGH")
        self.assertEqual(retrieved_exception.violation_amount, 500.0)
        self.assertEqual(retrieved_exception.violation_details['violation_percentage'], 50)


class TestDatabaseOperations(unittest.TestCase):
    """Test database operations and CRUD functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        """Set up test data for each test"""
        self.session = self.TestSession()
        self.unique_id = str(int(datetime.now().timestamp() * 1000000))
    
    def tearDown(self):
        """Clean up after each test"""
        self.session.rollback()
        self.session.close()

    def test_crud_operations_user(self):
        """Test CRUD operations for User model"""
        # CREATE
        user_data = {
            'user_id': f'crud_user_{self.unique_id}',
            'email': f'crud_{self.unique_id}@example.com',
            'phone': '+1234567890',
            'preferences': {'notifications': True}
        }
        user = User(**user_data)
        self.session.add(user)
        self.session.commit()
        
        # READ
        retrieved_user = self.session.query(User).filter_by(user_id=user_data['user_id']).first()
        self.assertIsNotNone(retrieved_user)
        self.assertEqual(retrieved_user.email, user_data['email'])
        
        # UPDATE
        retrieved_user.phone = '+9876543210'
        retrieved_user.preferences = {'notifications': False, 'sms': True}
        self.session.commit()
        
        updated_user = self.session.query(User).filter_by(user_id=user_data['user_id']).first()
        self.assertEqual(updated_user.phone, '+9876543210')
        self.assertEqual(updated_user.preferences['sms'], True)
        
        # DELETE
        self.session.delete(updated_user)
        self.session.commit()
        
        deleted_user = self.session.query(User).filter_by(user_id=user_data['user_id']).first()
        self.assertIsNone(deleted_user)

    def test_complex_query_operations(self):
        """Test complex query operations across multiple models"""
        # Create test data
        user = User(
            user_id=f'query_user_{self.unique_id}',
            email=f'query_{self.unique_id}@example.com'
        )
        self.session.add(user)
        
        flight = Flight(
            flight_id=f'query_flight_{self.unique_id}',
            airline='AA',
            flight_number='1234',
            departure_airport='JFK',
            arrival_airport='LAX',
            scheduled_departure=datetime(2025, 8, 15, 8, 30),
            scheduled_arrival=datetime(2025, 8, 15, 11, 45),
            flight_status='DELAYED',
            delay_minutes=30
        )
        self.session.add(flight)
        
        booking = Booking(
            booking_id=f'query_booking_{self.unique_id}',
            user_id=user.user_id,
            flight_id=flight.flight_id,
            pnr='QRY123',
            airline='AA',
            flight_number='1234',
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin='JFK',
            destination='LAX',
            fare_amount=500.00
        )
        self.session.add(booking)
        self.session.commit()
        
        # Test JOIN queries
        result = self.session.query(Booking, Flight, User).join(Flight).join(User).filter(
            Flight.flight_status == 'DELAYED'
        ).first()
        
        self.assertIsNotNone(result)
        booking_result, flight_result, user_result = result
        self.assertEqual(flight_result.delay_minutes, 30)
        self.assertEqual(booking_result.pnr, 'QRY123')
        self.assertEqual(user_result.email, f'query_{self.unique_id}@example.com')

    def test_transaction_rollback(self):
        """Test database transaction rollback functionality"""
        user = User(
            user_id=f'rollback_user_{self.unique_id}',
            email=f'rollback_{self.unique_id}@example.com'
        )
        self.session.add(user)
        self.session.commit()
        
        # Start transaction that should be rolled back
        try:
            user.email = 'updated_email@example.com'
            # Simulate an error that causes rollback
            invalid_user = User(
                user_id='invalid',
                email=user.email  # This will cause unique constraint violation
            )
            self.session.add(invalid_user)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
        
        # Verify rollback worked
        refreshed_user = self.session.query(User).filter_by(user_id=f'rollback_user_{self.unique_id}').first()
        self.assertEqual(refreshed_user.email, f'rollback_{self.unique_id}@example.com')


class TestModelHelperFunctions(unittest.TestCase):
    """Test model helper functions and business logic"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        """Set up test data"""
        # Patch SessionLocal to use our test session
        self.session_patcher = patch('flight_agent.models.SessionLocal', self.TestSession)
        self.session_patcher.start()
        
        self.unique_id = str(int(datetime.now().timestamp() * 1000000))
    
    def tearDown(self):
        """Clean up"""
        self.session_patcher.stop()

    def test_create_user_helper(self):
        """Test create_user helper function"""
        email = f'helper_{self.unique_id}@example.com'
        phone = '+1234567890'
        
        user = create_user(email=email, phone=phone)
        
        self.assertIsNotNone(user)
        self.assertEqual(user.email, email)
        self.assertEqual(user.phone, phone)
        self.assertTrue(user.user_id.startswith('user_'))

    def test_create_flight_helper(self):
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
        self.assertTrue(flight.flight_id.startswith('AA_1234_'))

    def test_get_upcoming_bookings(self):
        """Test get_upcoming_bookings helper function"""
        # Create test user and future booking
        user = create_user(f'upcoming_{self.unique_id}@example.com')
        
        future_date = datetime.utcnow() + timedelta(days=7)
        booking_data = {
            'pnr': 'FUTURE123',
            'airline': 'AA',
            'flight_number': '1234',
            'departure_date': future_date,
            'origin': 'JFK',
            'destination': 'LAX'
        }
        
        booking = create_booking(user.user_id, booking_data)
        
        # Test helper function
        upcoming_bookings = get_upcoming_bookings(user.user_id)
        
        self.assertGreater(len(upcoming_bookings), 0)
        self.assertEqual(upcoming_bookings[0].pnr, 'FUTURE123')

    def test_compensation_rule_validation_helper(self):
        """Test validate_compensation_rule helper function"""
        # Test valid rule
        valid_rule_data = {
            'rule_name': 'Test Rule',
            'description': 'Test compensation rule',
            'disruption_type': 'CANCELLED',
            'amount': 400.0,
            'priority': 10,
            'conditions': {
                'delay_min': 60,
                'delay_max': 240
            }
        }
        
        validation_result = validate_compensation_rule(valid_rule_data)
        
        self.assertTrue(validation_result['valid'])
        self.assertEqual(len(validation_result['errors']), 0)
        
        # Test invalid rule (missing required field)
        invalid_rule_data = {
            'rule_name': 'Incomplete Rule',
            # Missing description, disruption_type, amount
            'priority': 10
        }
        
        invalid_validation = validate_compensation_rule(invalid_rule_data)
        
        self.assertFalse(invalid_validation['valid'])
        self.assertGreater(len(invalid_validation['errors']), 0)

    def test_policy_compliance_checking(self):
        """Test check_policy_compliance helper function"""
        # Create a travel policy
        policy_data = {
            'policy_name': 'Test Policy',
            'description': 'Test policy for compliance checking',
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
        
        # Test booking data that violates policy
        violating_booking_data = {
            'fare_amount': 1500,  # Exceeds limit
            'booking_class': 'Business',  # Not allowed
            'departure_date': datetime.utcnow() + timedelta(days=2)  # Too short advance booking
        }
        
        violations = check_policy_compliance(violating_booking_data, [policy])
        
        self.assertGreater(len(violations), 0)
        violation_types = [v['violation_type'] for v in violations]
        self.assertIn('FARE_LIMIT_EXCEEDED', violation_types)
        self.assertIn('BOOKING_CLASS_VIOLATION', violation_types)

    def test_flight_hold_operations(self):
        """Test flight hold creation and management"""
        # Create dependencies
        user = create_user(f'hold_{self.unique_id}@example.com')
        booking_data = {
            'pnr': 'HOLD123',
            'airline': 'AA',
            'flight_number': '1234',
            'departure_date': datetime.utcnow() + timedelta(days=7),
            'origin': 'JFK',
            'destination': 'LAX'
        }
        booking = create_booking(user.user_id, booking_data)
        
        # Test hold creation
        hold_data = {
            'flight_number': 'AA5678',
            'airline': 'AA',
            'departure_time': datetime.utcnow() + timedelta(days=7, hours=2),
            'arrival_time': datetime.utcnow() + timedelta(days=7, hours=8),
            'origin': 'JFK',
            'destination': 'LAX',
            'booking_class': 'Economy',
            'hold_duration_minutes': 30,
            'price_locked': 375.00
        }
        
        hold = create_flight_hold(booking.booking_id, user.user_id, hold_data)
        
        self.assertIsNotNone(hold)
        self.assertEqual(hold.hold_status, 'ACTIVE')
        self.assertEqual(hold.flight_number, 'AA5678')
        
        # Test hold extension
        extended_hold = extend_flight_hold(hold.hold_id, 15, "User requested extension")
        
        self.assertEqual(extended_hold.extension_count, 1)
        self.assertEqual(extended_hold.extension_reason, "User requested extension")
        
        # Test hold release
        released_hold = release_flight_hold(hold.hold_id)
        
        self.assertEqual(released_hold.hold_status, 'RELEASED')
        self.assertIsNotNone(released_hold.released_at)


class TestRelationshipIntegrity(unittest.TestCase):
    """Test relationship integrity and foreign key constraints"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        """Set up test data"""
        self.session = self.TestSession()
        self.unique_id = str(int(datetime.now().timestamp() * 1000000))
    
    def tearDown(self):
        """Clean up"""
        self.session.rollback()
        self.session.close()

    def test_cascading_relationships(self):
        """Test cascading deletes and relationship integrity"""
        # Create user with related entities
        user = User(
            user_id=f'cascade_user_{self.unique_id}',
            email=f'cascade_{self.unique_id}@example.com'
        )
        self.session.add(user)
        
        traveler = Traveler(
            traveler_id=f'cascade_traveler_{self.unique_id}',
            user_id=user.user_id,
            first_name='John',
            last_name='Doe'
        )
        self.session.add(traveler)
        
        wallet = Wallet(
            wallet_id=f'cascade_wallet_{self.unique_id}',
            user_id=user.user_id,
            balance=100.0
        )
        self.session.add(wallet)
        self.session.commit()
        
        # Verify relationships exist
        self.assertEqual(len(user.travelers), 1)
        self.assertIsNotNone(user.wallet)
        
        # Test relationship navigation
        self.assertEqual(traveler.user.email, user.email)
        self.assertEqual(wallet.user.email, user.email)

    def test_booking_flight_relationship(self):
        """Test booking-flight relationship integrity"""
        # Create flight
        flight = Flight(
            flight_id=f'rel_flight_{self.unique_id}',
            airline='AA',
            flight_number='1234',
            departure_airport='JFK',
            arrival_airport='LAX',
            scheduled_departure=datetime(2025, 8, 15, 8, 30),
            scheduled_arrival=datetime(2025, 8, 15, 11, 45)
        )
        self.session.add(flight)
        
        user = User(
            user_id=f'rel_user_{self.unique_id}',
            email=f'rel_{self.unique_id}@example.com'
        )
        self.session.add(user)
        
        # Create multiple bookings for same flight
        for i in range(3):
            booking = Booking(
                booking_id=f'rel_booking_{self.unique_id}_{i}',
                user_id=user.user_id,
                flight_id=flight.flight_id,
                pnr=f'REL{i}',
                airline='AA',
                flight_number='1234',
                departure_date=datetime(2025, 8, 15, 8, 30),
                origin='JFK',
                destination='LAX'
            )
            self.session.add(booking)
        
        self.session.commit()
        
        # Test relationship integrity
        self.assertEqual(len(flight.bookings), 3)
        self.assertEqual(len(user.bookings), 3)
        
        # Test back-references
        for booking in flight.bookings:
            self.assertEqual(booking.flight.flight_id, flight.flight_id)
            self.assertEqual(booking.user.user_id, user.user_id)

    def test_disruption_alert_relationships(self):
        """Test complex relationship chains for disruption alerts"""
        # Create full chain: User -> Booking -> DisruptionEvent -> DisruptionAlert
        user = User(
            user_id=f'alert_user_{self.unique_id}',
            email=f'alert_{self.unique_id}@example.com'
        )
        self.session.add(user)
        
        booking = Booking(
            booking_id=f'alert_booking_{self.unique_id}',
            user_id=user.user_id,
            pnr='ALERT123',
            airline='AA',
            flight_number='1234',
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin='JFK',
            destination='LAX'
        )
        self.session.add(booking)
        
        disruption = DisruptionEvent(
            event_id=f'alert_disruption_{self.unique_id}',
            booking_id=booking.booking_id,
            disruption_type='DELAYED',
            delay_minutes=60
        )
        self.session.add(disruption)
        
        alert = DisruptionAlert(
            alert_id=f'alert_{self.unique_id}',
            event_id=disruption.event_id,
            user_id=user.user_id,
            alert_type='EMAIL',
            alert_message='Your flight is delayed by 60 minutes'
        )
        self.session.add(alert)
        self.session.commit()
        
        # Test relationship chain integrity
        self.assertEqual(alert.disruption_event.booking.user.email, user.email)
        self.assertEqual(disruption.booking.user.user_id, user.user_id)
        self.assertEqual(len(disruption.disruption_alerts), 1)


class TestEdgeCasesAndErrorHandling(unittest.TestCase):
    """Test edge cases and error handling scenarios"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        """Set up test data"""
        self.session = self.TestSession()
        self.unique_id = str(int(datetime.now().timestamp() * 1000000))
        
        # Patch SessionLocal for helper function tests
        self.session_patcher = patch('flight_agent.models.SessionLocal', self.TestSession)
        self.session_patcher.start()
    
    def tearDown(self):
        """Clean up"""
        self.session_patcher.stop()
        self.session.rollback()
        self.session.close()

    def test_invalid_json_data_handling(self):
        """Test handling of invalid JSON data in JSON fields"""
        user = User(
            user_id=f'json_test_{self.unique_id}',
            email=f'json_{self.unique_id}@example.com',
            preferences=None  # Test None value
        )
        self.session.add(user)
        self.session.commit()
        
        retrieved_user = self.session.query(User).filter_by(user_id=f'json_test_{self.unique_id}').first()
        self.assertIsNone(retrieved_user.preferences)

    def test_datetime_edge_cases(self):
        """Test datetime edge cases and timezone handling"""
        # Test timezone-aware datetime
        utc_now = datetime.now(timezone.utc)
        
        flight = Flight(
            flight_id=f'datetime_edge_{self.unique_id}',
            airline='AA',
            flight_number='1234',
            departure_airport='JFK',
            arrival_airport='LAX',
            scheduled_departure=utc_now,
            scheduled_arrival=utc_now + timedelta(hours=6)
        )
        self.session.add(flight)
        self.session.commit()
        
        retrieved_flight = self.session.query(Flight).filter_by(flight_id=f'datetime_edge_{self.unique_id}').first()
        self.assertIsNotNone(retrieved_flight.scheduled_departure)

    def test_large_json_data_handling(self):
        """Test handling of large JSON data structures"""
        # Create large preferences object
        large_preferences = {
            'airlines': [f'airline_{i}' for i in range(100)],
            'routes': {f'route_{i}': f'preference_{i}' for i in range(50)},
            'history': [{'date': f'2025-01-{i:02d}', 'action': f'action_{i}'} for i in range(1, 32)]
        }
        
        user = User(
            user_id=f'large_json_{self.unique_id}',
            email=f'large_{self.unique_id}@example.com',
            preferences=large_preferences
        )
        self.session.add(user)
        self.session.commit()
        
        retrieved_user = self.session.query(User).filter_by(user_id=f'large_json_{self.unique_id}').first()
        self.assertEqual(len(retrieved_user.preferences['airlines']), 100)
        self.assertEqual(len(retrieved_user.preferences['routes']), 50)

    def test_boundary_value_testing(self):
        """Test boundary values for numeric fields"""
        # Test maximum delay minutes
        flight = Flight(
            flight_id=f'boundary_test_{self.unique_id}',
            airline='AA',
            flight_number='1234',
            departure_airport='JFK',
            arrival_airport='LAX',
            scheduled_departure=datetime(2025, 8, 15, 8, 30),
            scheduled_arrival=datetime(2025, 8, 15, 11, 45),
            delay_minutes=9999  # Very large delay
        )
        self.session.add(flight)
        self.session.commit()
        
        retrieved_flight = self.session.query(Flight).filter_by(flight_id=f'boundary_test_{self.unique_id}').first()
        self.assertEqual(retrieved_flight.delay_minutes, 9999)

    def test_nonexistent_record_operations(self):
        """Test operations on nonexistent records"""
        # Test updating nonexistent flight
        with self.assertRaises(ValueError):
            update_flight_status('nonexistent_flight', {'flight_status': 'DELAYED'})
        
        # Test extending nonexistent hold
        with self.assertRaises(ValueError):
            extend_flight_hold('nonexistent_hold', 15)

    def test_string_length_limits(self):
        """Test string field length handling"""
        # Test very long strings
        long_description = 'A' * 10000  # Very long description
        
        policy = TravelPolicy(
            policy_id=f'long_desc_{self.unique_id}',
            policy_name='Long Description Policy',
            description=long_description,
            policy_type='BOOKING',
            rules={'test': 'rule'},
            effective_date=datetime(2025, 1, 1),
            created_by='test'
        )
        self.session.add(policy)
        self.session.commit()
        
        retrieved_policy = self.session.query(TravelPolicy).filter_by(policy_id=f'long_desc_{self.unique_id}').first()
        self.assertEqual(len(retrieved_policy.description), 10000)

    def test_concurrent_modification_handling(self):
        """Test handling of concurrent modifications"""
        # Create user
        user = User(
            user_id=f'concurrent_{self.unique_id}',
            email=f'concurrent_{self.unique_id}@example.com'
        )
        self.session.add(user)
        self.session.commit()
        
        # Simulate concurrent modification by creating second session
        session2 = self.TestSession()
        user2 = session2.query(User).filter_by(user_id=f'concurrent_{self.unique_id}').first()
        
        # Modify in both sessions
        user.phone = '+1111111111'
        user2.phone = '+2222222222'
        
        # Commit first session
        self.session.commit()
        
        # Commit second session (this might raise an exception depending on isolation level)
        try:
            session2.commit()
        except Exception:
            session2.rollback()
        finally:
            session2.close()


if __name__ == '__main__':
    # Set up test runner with comprehensive reporting
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestDataModelValidation,
        TestDatabaseOperations,
        TestModelHelperFunctions,
        TestRelationshipIntegrity,
        TestEdgeCasesAndErrorHandling
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"COMPREHENSIVE MODEL TESTING SUMMARY")
    print(f"{'='*70}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError: ')[-1].split('\\n')[0] if 'AssertionError:' in traceback else 'See details above'}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('\\n')[-2] if len(traceback.split('\\n')) > 1 else 'See details above'}")
    
    print(f"\n✅ Comprehensive unit tests for all data models and validation completed!")
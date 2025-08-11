# flight_agent/models.py
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Boolean, ForeignKey, Float, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./travel_disruption.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    user_id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    preferences = Column(JSON, default={})  # seat preference, airline preference, sms preferences, etc.
    
    # Relationships
    bookings = relationship("Booking", back_populates="user")
    email_connections = relationship("EmailConnection", back_populates="user")
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    travelers = relationship("Traveler", back_populates="user")
    approval_requests = relationship("ApprovalRequest", back_populates="user")


class EmailConnection(Base):
    __tablename__ = "email_connections"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"))
    email_provider = Column(String)  # gmail, outlook, etc.
    email_address = Column(String)
    access_token = Column(String)  # OAuth token or app password
    last_sync = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="email_connections")


class Flight(Base):
    __tablename__ = "flights"
    
    flight_id = Column(String, primary_key=True)
    airline = Column(String, nullable=False)
    flight_number = Column(String, nullable=False)
    departure_airport = Column(String, nullable=False)  # IATA airport code
    arrival_airport = Column(String, nullable=False)  # IATA airport code
    scheduled_departure = Column(DateTime, nullable=False)
    scheduled_arrival = Column(DateTime, nullable=False)
    actual_departure = Column(DateTime)
    actual_arrival = Column(DateTime)
    aircraft_type = Column(String)
    flight_status = Column(String, default="SCHEDULED")  # SCHEDULED, DELAYED, CANCELLED, DIVERTED, COMPLETED
    delay_minutes = Column(Integer, default=0)
    gate = Column(String)
    terminal = Column(String)
    raw_flight_data = Column(JSON)  # Store complete flight data from external APIs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = relationship("Booking", back_populates="flight")
    trip_monitors = relationship("TripMonitor", back_populates="flight")


class Traveler(Base):
    __tablename__ = "travelers"
    
    traveler_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    middle_name = Column(String)
    date_of_birth = Column(DateTime)
    passport_number = Column(String)
    passport_country = Column(String)  # ISO country code
    passport_expiry = Column(DateTime)
    known_traveler_number = Column(String)  # TSA PreCheck, Global Entry, etc.
    frequent_flyer_numbers = Column(JSON, default={})  # {"airline": "number", ...}
    dietary_restrictions = Column(JSON, default=[])
    mobility_assistance = Column(Boolean, default=False)
    emergency_contact = Column(JSON, default={})  # {"name": "", "phone": "", "relationship": ""}
    preferences = Column(JSON, default={})  # seat preferences, meal preferences, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="travelers")
    bookings = relationship("Booking", back_populates="traveler")


class Booking(Base):
    __tablename__ = "bookings"
    
    booking_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"))
    flight_id = Column(String, ForeignKey("flights.flight_id"))
    traveler_id = Column(String, ForeignKey("travelers.traveler_id"))
    pnr = Column(String, nullable=False)  # Passenger Name Record / Confirmation Number
    airline = Column(String, nullable=False)
    flight_number = Column(String, nullable=False)
    departure_date = Column(DateTime, nullable=False)
    origin = Column(String, nullable=False)  # Airport code
    destination = Column(String, nullable=False)  # Airport code
    booking_class = Column(String, default="Economy")  # Economy, Business, First
    seat = Column(String)
    ticket_number = Column(String)
    booking_reference = Column(String)  # Alternative booking reference
    fare_basis = Column(String)
    fare_amount = Column(Float)
    currency = Column(String, default="USD")
    status = Column(String, default="CONFIRMED")  # CONFIRMED, CANCELLED, COMPLETED, REFUNDED
    raw_data = Column(JSON)  # Store complete booking data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_checked = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="bookings")
    flight = relationship("Flight", back_populates="bookings")
    traveler = relationship("Traveler", back_populates="bookings")
    disruption_events = relationship("DisruptionEvent", back_populates="booking")
    flight_holds = relationship("FlightHold", back_populates="booking")
    trip_monitors = relationship("TripMonitor", back_populates="booking")
    approval_requests = relationship("ApprovalRequest", back_populates="booking")
    policy_exceptions = relationship("PolicyException", back_populates="booking")


class TripMonitor(Base):
    __tablename__ = "trip_monitors"
    
    monitor_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    booking_id = Column(String, ForeignKey("bookings.booking_id"), nullable=False)
    flight_id = Column(String, ForeignKey("flights.flight_id"), nullable=False)
    monitor_type = Column(String, default="FULL")  # FULL, DELAY_ONLY, CANCELLATION_ONLY
    is_active = Column(Boolean, default=True)
    check_frequency_minutes = Column(Integer, default=30)  # How often to check for updates
    notification_preferences = Column(JSON, default={})  # {"email": True, "sms": True, "push": False}
    last_check = Column(DateTime)
    last_notification_sent = Column(DateTime)
    escalation_rules = Column(JSON, default={})  # Rules for escalating notifications
    auto_rebooking_enabled = Column(Boolean, default=False)
    rebooking_preferences = Column(JSON, default={})  # Preferences for automatic rebooking
    notes = Column(Text)  # User notes or special instructions
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)  # When to stop monitoring (e.g., after flight completion + 24h)
    
    # Relationships
    user = relationship("User", back_populates=None)
    booking = relationship("Booking", back_populates="trip_monitors")
    flight = relationship("Flight", back_populates="trip_monitors")


class DisruptionEvent(Base):
    __tablename__ = "disruption_events"
    
    event_id = Column(String, primary_key=True)
    booking_id = Column(String, ForeignKey("bookings.booking_id"))
    detected_at = Column(DateTime, default=datetime.utcnow)
    disruption_type = Column(String)  # CANCELLED, DELAYED, DIVERTED
    original_departure = Column(DateTime)
    new_departure = Column(DateTime)
    delay_minutes = Column(Integer, default=0)
    reason = Column(String)  # Weather, mechanical, crew, etc.
    rebooking_status = Column(String, default="PENDING")  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    rebooking_options = Column(JSON)  # Store alternative flight options
    selected_option = Column(JSON)
    user_notified = Column(Boolean, default=False)
    notification_sent_at = Column(DateTime)
    resolved_at = Column(DateTime)
    priority = Column(String, default="MEDIUM")  # HIGH, MEDIUM, LOW - for SMS filtering
    compensation_eligible = Column(Boolean, default=False)
    compensation_amount = Column(Float)
    compensation_status = Column(String, default="PENDING")  # PENDING, APPROVED, PAID, DENIED
    
    # Relationships
    booking = relationship("Booking", back_populates="disruption_events")
    disruption_alerts = relationship("DisruptionAlert", back_populates="disruption_event")


class DisruptionAlert(Base):
    """
    REQ-1.2: DisruptionAlert model with risk severity levels
    Handles alert notifications for disruption events with configurable severity levels
    """
    __tablename__ = "disruption_alerts"
    
    alert_id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("disruption_events.event_id"), nullable=False)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    alert_type = Column(String, nullable=False)  # EMAIL, SMS, PUSH, IN_APP
    risk_severity = Column(String, default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    alert_message = Column(String, nullable=False)
    sent_at = Column(DateTime)
    delivery_status = Column(String, default="PENDING")  # PENDING, SENT, DELIVERED, FAILED
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    urgency_score = Column(Integer, default=50)  # 0-100 scale for prioritization
    alert_metadata = Column(JSON, default={})  # Additional alert context
    expires_at = Column(DateTime)  # When this alert becomes irrelevant
    acknowledged_at = Column(DateTime)  # User acknowledgment timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    disruption_event = relationship("DisruptionEvent", back_populates="disruption_alerts")
    user = relationship("User")


class AlternativeFlight(Base):
    """
    REQ-2.1: AlternativeFlight model with policy compliance flags
    Stores alternative flight options with policy and compliance validation
    """
    __tablename__ = "alternative_flights"
    
    alternative_id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("disruption_events.event_id"), nullable=False)
    flight_number = Column(String, nullable=False)
    airline = Column(String, nullable=False)
    departure_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    origin = Column(String, nullable=False)  # Airport code
    destination = Column(String, nullable=False)  # Airport code
    booking_class = Column(String, nullable=False)
    available_seats = Column(Integer, default=0)
    price = Column(Float)  # Price difference from original booking
    currency = Column(String, default="USD")
    
    # Policy compliance flags (REQ-2.1)
    policy_compliant = Column(Boolean, default=False)  # Overall policy compliance
    class_downgrade_approved = Column(Boolean, default=False)  # If lower class is acceptable
    airline_restriction_compliant = Column(Boolean, default=True)  # Airline policy compliance
    route_policy_compliant = Column(Boolean, default=True)  # Route restrictions compliance
    time_window_compliant = Column(Boolean, default=True)  # Departure time policy compliance
    cost_policy_compliant = Column(Boolean, default=True)  # Cost increase policy compliance
    
    # Additional metadata
    stops = Column(Integer, default=0)  # Number of stops/connections
    layover_duration = Column(Integer)  # Total layover time in minutes
    flight_duration = Column(Integer)  # Total flight time in minutes
    aircraft_type = Column(String)
    meal_service = Column(Boolean, default=False)
    wifi_available = Column(Boolean, default=False)
    
    # Booking and status
    recommended_rank = Column(Integer)  # 1-N ranking of alternatives
    user_preference_score = Column(Integer)  # User preference matching score (0-100)
    availability_status = Column(String, default="AVAILABLE")  # AVAILABLE, WAITLIST, SOLD_OUT
    booking_deadline = Column(DateTime)  # When this option expires
    selected_by_user = Column(Boolean, default=False)
    booked_at = Column(DateTime)
    booking_reference = Column(String)  # New booking reference if selected
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    disruption_event = relationship("DisruptionEvent")


class FlightHold(Base):
    """
    REQ-2.5: FlightHold model for temporary reservations
    Manages temporary reservations of alternative flights during rebooking process
    """
    __tablename__ = "flight_holds"
    
    hold_id = Column(String, primary_key=True)
    booking_id = Column(String, ForeignKey("bookings.booking_id"), nullable=False)
    alternative_id = Column(String, ForeignKey("alternative_flights.alternative_id"))
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    
    # Flight details
    flight_number = Column(String, nullable=False)
    airline = Column(String, nullable=False)
    departure_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    booking_class = Column(String, nullable=False)
    
    # Hold management
    hold_status = Column(String, default="ACTIVE")  # ACTIVE, EXPIRED, RELEASED, CONVERTED
    hold_type = Column(String, default="AUTOMATIC")  # AUTOMATIC, MANUAL, AGENT_REQUESTED
    hold_duration_minutes = Column(Integer, default=15)  # How long to hold
    hold_expires_at = Column(DateTime, nullable=False)
    auto_release = Column(Boolean, default=True)  # Auto-release when expired
    
    # Reservation details
    seats_held = Column(Integer, default=1)
    hold_reference = Column(String)  # Airline's hold reference
    hold_confirmation_code = Column(String)  # Airline confirmation for hold
    price_locked = Column(Float)  # Price guaranteed during hold
    currency = Column(String, default="USD")
    
    # Business rules
    payment_required_by = Column(DateTime)  # When payment must be made
    cancellation_deadline = Column(DateTime)  # When hold can no longer be cancelled
    modification_allowed = Column(Boolean, default=True)  # Can hold be modified
    transfer_allowed = Column(Boolean, default=False)  # Can hold be transferred to another user
    
    # Status tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = Column(DateTime)  # When user confirmed the hold
    released_at = Column(DateTime)  # When hold was released
    converted_to_booking_at = Column(DateTime)  # When hold became a real booking
    
    # Extension tracking
    extension_count = Column(Integer, default=0)  # How many times hold was extended
    max_extensions_allowed = Column(Integer, default=2)
    extended_until = Column(DateTime)  # If hold was extended
    extension_reason = Column(String)  # Why hold was extended
    
    # Relationships
    booking = relationship("Booking", back_populates="flight_holds")
    alternative_flight = relationship("AlternativeFlight")
    user = relationship("User")


class Wallet(Base):
    __tablename__ = "wallets"
    
    wallet_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"), unique=True)
    balance = Column(Float, default=0.0)  # Current wallet balance in USD
    currency = Column(String, default="USD")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="wallet")
    transactions = relationship("WalletTransaction", back_populates="wallet")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    
    transaction_id = Column(String, primary_key=True)
    wallet_id = Column(String, ForeignKey("wallets.wallet_id"))
    amount = Column(Float, nullable=False)  # Positive for credits, negative for debits
    transaction_type = Column(String, nullable=False)  # COMPENSATION, PURCHASE, REFUND, etc.
    description = Column(String)
    reference_id = Column(String)  # Reference to booking, disruption event, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    transaction_metadata = Column(JSON, default={})  # Additional transaction details (renamed from metadata)
    
    # Relationships
    wallet = relationship("Wallet", back_populates="transactions")


class CompensationRule(Base):
    __tablename__ = "compensation_rules"
    
    rule_id = Column(String, primary_key=True)
    rule_name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    disruption_type = Column(String, nullable=False)  # CANCELLED, DELAYED, DIVERTED, OVERBOOKED
    amount = Column(Float, nullable=False)  # Base compensation amount in USD
    conditions = Column(JSON, default={})  # Rule conditions (flight_distance, delay_hours, booking_class, etc.)
    priority = Column(Integer, default=0)  # Higher priority rules take precedence
    is_active = Column(Boolean, default=True)  # Rule activation/deactivation
    version = Column(Integer, default=1)  # Rule versioning for audit trail
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String, default="system")  # User who created/modified the rule
    
    # Relationships
    rule_history = relationship("CompensationRuleHistory", back_populates="rule")


class CompensationRuleHistory(Base):
    __tablename__ = "compensation_rule_history"
    
    history_id = Column(String, primary_key=True)
    rule_id = Column(String, ForeignKey("compensation_rules.rule_id"))
    rule_name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    disruption_type = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    conditions = Column(JSON, default={})
    priority = Column(Integer, default=0)
    is_active = Column(Boolean)
    version = Column(Integer, nullable=False)
    action = Column(String, nullable=False)  # CREATED, UPDATED, DEACTIVATED, DELETED
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=False)
    
    # Relationships
    rule = relationship("CompensationRule", back_populates="rule_history")


# New Policy Compliance and Approval Workflow Models


class TravelPolicy(Base):
    """
    Travel policy model with rule definitions for compliance checking.
    Supports REQ-5.1: Policy rule definitions and compliance checking.
    """
    __tablename__ = "travel_policies"
    
    policy_id = Column(String, primary_key=True)
    policy_name = Column(String, nullable=False)
    policy_version = Column(String, default="1.0")
    description = Column(Text, nullable=False)
    policy_type = Column(String, nullable=False)  # BOOKING, EXPENSE, APPROVAL, SECURITY
    scope = Column(String, default="GLOBAL")  # GLOBAL, DEPARTMENT, ROLE, USER
    target_audience = Column(JSON, default={})  # {"departments": [], "roles": [], "users": []}
    
    # Rule definitions
    rules = Column(JSON, nullable=False)  # Comprehensive rule definitions
    # Example rules structure:
    # {
    #   "booking_limits": {
    #     "max_fare_amount": 1000,
    #     "allowed_booking_classes": ["Economy", "Premium Economy"],
    #     "advance_booking_days": 7,
    #     "preferred_airlines": ["AA", "DL", "UA"]
    #   },
    #   "expense_limits": {
    #     "max_hotel_rate": 200,
    #     "max_meal_allowance": 50,
    #     "receipts_required_above": 25
    #   },
    #   "approval_thresholds": {
    #     "auto_approve_below": 500,
    #     "manager_approval_below": 2000,
    #     "director_approval_above": 2000
    #   }
    # }
    
    # Compliance settings
    enforcement_level = Column(String, default="STRICT")  # STRICT, MODERATE, ADVISORY
    auto_compliance_check = Column(Boolean, default=True)
    allow_exceptions = Column(Boolean, default=True)
    exception_requires_approval = Column(Boolean, default=True)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    effective_date = Column(DateTime, nullable=False)
    expiration_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String, nullable=False)
    updated_by = Column(String)
    
    # Relationships
    approval_requests = relationship("ApprovalRequest", back_populates="travel_policy")
    policy_exceptions = relationship("PolicyException", back_populates="travel_policy")


class ApprovalRequest(Base):
    """
    Approval request model with escalation chains for workflow management.
    Supports REQ-5.2: Approval workflows with escalation chains.
    """
    __tablename__ = "approval_requests"
    
    request_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    booking_id = Column(String, ForeignKey("bookings.booking_id"))  # Optional, for booking-related approvals
    policy_id = Column(String, ForeignKey("travel_policies.policy_id"))
    
    # Request details
    request_type = Column(String, nullable=False)  # BOOKING_APPROVAL, POLICY_EXCEPTION, EXPENSE_APPROVAL
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    justification = Column(Text)  # User-provided justification
    request_data = Column(JSON, nullable=False)  # Detailed request information
    # Example request_data structure:
    # {
    #   "booking_details": {...},
    #   "policy_violations": [...],
    #   "requested_amount": 1500,
    #   "business_justification": "Critical client meeting",
    #   "alternative_options_considered": [...]
    # }
    
    # Approval workflow
    status = Column(String, default="PENDING")  # PENDING, IN_REVIEW, APPROVED, REJECTED, ESCALATED, EXPIRED
    priority = Column(String, default="MEDIUM")  # HIGH, MEDIUM, LOW
    escalation_level = Column(Integer, default=0)  # Current escalation level (0 = initial, 1+ = escalated)
    
    # Escalation chain definition
    escalation_chain = Column(JSON, nullable=False)  # Defines approval hierarchy
    # Example escalation_chain structure:
    # [
    #   {"level": 0, "approver_role": "manager", "approver_id": "mgr_123", "timeout_hours": 24},
    #   {"level": 1, "approver_role": "director", "approver_id": "dir_456", "timeout_hours": 48},
    #   {"level": 2, "approver_role": "vp", "approver_id": "vp_789", "timeout_hours": 72}
    # ]
    
    current_approver_id = Column(String)  # Current person who needs to approve
    current_approver_role = Column(String)  # Current approver's role
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = Column(DateTime)  # When approval is needed by
    escalation_due = Column(DateTime)  # When to escalate if no response
    resolved_at = Column(DateTime)
    
    # Resolution details
    approved_by = Column(String)  # Final approver user ID
    approved_at = Column(DateTime)
    approval_notes = Column(Text)  # Approver's comments
    rejection_reason = Column(Text)  # If rejected, reason provided
    
    # Audit trail
    approval_history = Column(JSON, default=[])  # History of all approval actions
    # Example approval_history structure:
    # [
    #   {"timestamp": "2024-01-01T10:00:00", "action": "CREATED", "user_id": "user_123"},
    #   {"timestamp": "2024-01-01T11:00:00", "action": "REVIEWED", "user_id": "mgr_123", "notes": "Looks good"},
    #   {"timestamp": "2024-01-01T12:00:00", "action": "APPROVED", "user_id": "mgr_123", "notes": "Approved"}
    # ]
    
    # Relationships
    user = relationship("User", back_populates="approval_requests")
    booking = relationship("Booking", back_populates="approval_requests")
    travel_policy = relationship("TravelPolicy", back_populates="approval_requests")


class PolicyException(Base):
    """
    Policy exception model for tracking rule violations and their handling.
    Supports REQ-5.4: Exception tracking and violation management.
    """
    __tablename__ = "policy_exceptions"
    
    exception_id = Column(String, primary_key=True)
    booking_id = Column(String, ForeignKey("bookings.booking_id"), nullable=False)
    policy_id = Column(String, ForeignKey("travel_policies.policy_id"), nullable=False)
    
    # Exception details
    exception_type = Column(String, nullable=False)  # RULE_VIOLATION, THRESHOLD_EXCEEDED, APPROVAL_BYPASS
    violation_category = Column(String, nullable=False)  # BOOKING_LIMIT, EXPENSE_LIMIT, ADVANCE_BOOKING, CLASS_RESTRICTION
    severity = Column(String, default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    
    # Violation details
    violated_rule = Column(String, nullable=False)  # Specific rule that was violated
    expected_value = Column(String)  # What the policy expected
    actual_value = Column(String)  # What was actually done
    violation_amount = Column(Float)  # Monetary amount of violation (if applicable)
    
    # Exception description
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    violation_details = Column(JSON, nullable=False)  # Detailed violation information
    # Example violation_details structure:
    # {
    #   "rule_path": "booking_limits.max_fare_amount",
    #   "policy_value": 1000,
    #   "actual_value": 1500,
    #   "violation_percentage": 50,
    #   "context": {
    #     "booking_class": "Business",
    #     "route": "JFK-LAX",
    #     "advance_days": 2
    #   }
    # }
    
    # Status and resolution
    status = Column(String, default="OPEN")  # OPEN, UNDER_REVIEW, APPROVED_EXCEPTION, REJECTED, RESOLVED
    requires_approval = Column(Boolean, default=True)
    approval_request_id = Column(String)  # Reference to related approval request
    
    # Justification and resolution
    user_justification = Column(Text)  # User's explanation for the violation
    business_justification = Column(Text)  # Business reason for the exception
    resolution_notes = Column(Text)  # How the exception was resolved
    resolution_action = Column(String)  # APPROVED, REJECTED, POLICY_UPDATED, BOOKING_MODIFIED
    
    # Financial impact
    cost_impact = Column(Float)  # Additional cost due to violation
    savings_foregone = Column(Float)  # Potential savings lost due to violation
    
    # Timing
    detected_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime)
    
    # Resolution details
    resolved_by = Column(String)  # User ID who resolved the exception
    resolution_date = Column(DateTime)
    
    # Audit and compliance
    is_recurring = Column(Boolean, default=False)  # If this is a repeated violation
    previous_exceptions = Column(JSON, default=[])  # References to previous similar exceptions
    compliance_notes = Column(Text)  # Notes for compliance/audit purposes
    
    # Relationships
    booking = relationship("Booking", back_populates="policy_exceptions")
    travel_policy = relationship("TravelPolicy", back_populates="policy_exceptions")


# Create all tables
Base.metadata.create_all(bind=engine)


# Database helper functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_user(email: str, phone: str = None) -> User:
    """Create a new user"""
    db = SessionLocal()
    try:
        user = User(
            user_id=f"user_{email.split('@')[0]}_{datetime.now().timestamp()}",
            email=email,
            phone=phone
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def get_user_by_email(email: str) -> User:
    """Get user by email"""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


def create_flight(flight_data: dict) -> Flight:
    """Create a new flight record"""
    db = SessionLocal()
    try:
        # Generate unique flight ID
        flight_id = f"{flight_data['airline']}_{flight_data['flight_number']}_{flight_data['scheduled_departure'].strftime('%Y%m%d')}"
        
        flight = Flight(
            flight_id=flight_id,
            airline=flight_data['airline'],
            flight_number=flight_data['flight_number'],
            departure_airport=flight_data['departure_airport'],
            arrival_airport=flight_data['arrival_airport'],
            scheduled_departure=flight_data['scheduled_departure'],
            scheduled_arrival=flight_data['scheduled_arrival'],
            actual_departure=flight_data.get('actual_departure'),
            actual_arrival=flight_data.get('actual_arrival'),
            aircraft_type=flight_data.get('aircraft_type'),
            flight_status=flight_data.get('flight_status', 'SCHEDULED'),
            delay_minutes=flight_data.get('delay_minutes', 0),
            gate=flight_data.get('gate'),
            terminal=flight_data.get('terminal'),
            raw_flight_data=flight_data.get('raw_flight_data', {})
        )
        db.add(flight)
        db.commit()
        db.refresh(flight)
        return flight
    finally:
        db.close()


def create_traveler(user_id: str, traveler_data: dict) -> Traveler:
    """Create a new traveler profile"""
    db = SessionLocal()
    try:
        traveler = Traveler(
            traveler_id=f"traveler_{user_id}_{datetime.now().timestamp()}",
            user_id=user_id,
            first_name=traveler_data['first_name'],
            last_name=traveler_data['last_name'],
            middle_name=traveler_data.get('middle_name'),
            date_of_birth=traveler_data.get('date_of_birth'),
            passport_number=traveler_data.get('passport_number'),
            passport_country=traveler_data.get('passport_country'),
            passport_expiry=traveler_data.get('passport_expiry'),
            known_traveler_number=traveler_data.get('known_traveler_number'),
            frequent_flyer_numbers=traveler_data.get('frequent_flyer_numbers', {}),
            dietary_restrictions=traveler_data.get('dietary_restrictions', []),
            mobility_assistance=traveler_data.get('mobility_assistance', False),
            emergency_contact=traveler_data.get('emergency_contact', {}),
            preferences=traveler_data.get('preferences', {})
        )
        db.add(traveler)
        db.commit()
        db.refresh(traveler)
        return traveler
    finally:
        db.close()


def create_trip_monitor(user_id: str, booking_id: str, flight_id: str, monitor_data: dict = None) -> TripMonitor:
    """Create a new trip monitor"""
    db = SessionLocal()
    try:
        if monitor_data is None:
            monitor_data = {}
            
        monitor = TripMonitor(
            monitor_id=f"monitor_{booking_id}_{datetime.now().timestamp()}",
            user_id=user_id,
            booking_id=booking_id,
            flight_id=flight_id,
            monitor_type=monitor_data.get('monitor_type', 'FULL'),
            is_active=monitor_data.get('is_active', True),
            check_frequency_minutes=monitor_data.get('check_frequency_minutes', 30),
            notification_preferences=monitor_data.get('notification_preferences', {"email": True, "sms": False}),
            escalation_rules=monitor_data.get('escalation_rules', {}),
            auto_rebooking_enabled=monitor_data.get('auto_rebooking_enabled', False),
            rebooking_preferences=monitor_data.get('rebooking_preferences', {}),
            notes=monitor_data.get('notes'),
            expires_at=monitor_data.get('expires_at')
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)
        return monitor
    finally:
        db.close()


def create_booking(user_id: str, booking_data: dict) -> Booking:
    """Create a new booking"""
    db = SessionLocal()
    try:
        # Create a copy of booking_data to avoid modifying the original
        safe_raw_data = booking_data.copy()
        
        # Convert datetime objects to strings in the raw_data
        for key, value in safe_raw_data.items():
            if isinstance(value, datetime):
                safe_raw_data[key] = value.isoformat()  # Convert to string like "2025-01-05T10:30:00"
        
        booking = Booking(
            booking_id=f"{booking_data['pnr']}_{booking_data['flight_number']}_{datetime.now().timestamp()}",
            user_id=user_id,
            flight_id=booking_data.get('flight_id'),
            traveler_id=booking_data.get('traveler_id'),
            pnr=booking_data['pnr'],
            airline=booking_data['airline'],
            flight_number=booking_data['flight_number'],
            departure_date=booking_data['departure_date'],  # This stays as datetime for the column
            origin=booking_data['origin'],
            destination=booking_data['destination'],
            booking_class=booking_data.get('class', 'Economy'),
            seat=booking_data.get('seat'),
            ticket_number=booking_data.get('ticket_number'),
            booking_reference=booking_data.get('booking_reference'),
            fare_basis=booking_data.get('fare_basis'),
            fare_amount=booking_data.get('fare_amount'),
            currency=booking_data.get('currency', 'USD'),
            raw_data=safe_raw_data  # Use the safe version with strings instead of datetime
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return booking
    finally:
        db.close()


def get_upcoming_bookings(user_id: str = None):
    """Get all upcoming bookings, optionally filtered by user"""
    db = SessionLocal()
    try:
        query = db.query(Booking).filter(
            Booking.departure_date > datetime.utcnow(),
            Booking.status != "CANCELLED"
        )
        if user_id:
            query = query.filter(Booking.user_id == user_id)
        return query.all()
    finally:
        db.close()


def get_active_trip_monitors(user_id: str = None):
    """Get all active trip monitors, optionally filtered by user"""
    db = SessionLocal()
    try:
        query = db.query(TripMonitor).filter(
            TripMonitor.is_active == True,
            TripMonitor.expires_at > datetime.utcnow() if TripMonitor.expires_at.isnot(None) else True
        )
        if user_id:
            query = query.filter(TripMonitor.user_id == user_id)
        return query.all()
    finally:
        db.close()


def get_flight_by_details(airline: str, flight_number: str, departure_date: datetime) -> Flight:
    """Get flight by airline, flight number, and departure date"""
    db = SessionLocal()
    try:
        return db.query(Flight).filter(
            Flight.airline == airline,
            Flight.flight_number == flight_number,
            Flight.scheduled_departure.between(
                departure_date.replace(hour=0, minute=0, second=0),
                departure_date.replace(hour=23, minute=59, second=59)
            )
        ).first()
    finally:
        db.close()


def update_flight_status(flight_id: str, status_data: dict) -> Flight:
    """Update flight status and timing information"""
    db = SessionLocal()
    try:
        flight = db.query(Flight).filter(Flight.flight_id == flight_id).first()
        if not flight:
            raise ValueError(f"Flight {flight_id} not found")
        
        # Update flight status fields
        if 'flight_status' in status_data:
            flight.flight_status = status_data['flight_status']
        if 'actual_departure' in status_data:
            flight.actual_departure = status_data['actual_departure']
        if 'actual_arrival' in status_data:
            flight.actual_arrival = status_data['actual_arrival']
        if 'delay_minutes' in status_data:
            flight.delay_minutes = status_data['delay_minutes']
        if 'gate' in status_data:
            flight.gate = status_data['gate']
        if 'terminal' in status_data:
            flight.terminal = status_data['terminal']
        if 'raw_flight_data' in status_data:
            flight.raw_flight_data = status_data['raw_flight_data']
        
        flight.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(flight)
        return flight
    finally:
        db.close()


def create_disruption_event(booking_id: str, disruption_data: dict) -> DisruptionEvent:
    """Create a new disruption event"""
    db = SessionLocal()
    try:
        disruption = DisruptionEvent(
            event_id=f"disruption_{booking_id}_{datetime.now().timestamp()}",
            booking_id=booking_id,
            disruption_type=disruption_data['type'],
            original_departure=disruption_data.get('original_departure'),
            new_departure=disruption_data.get('new_departure'),
            delay_minutes=disruption_data.get('delay_minutes', 0),
            reason=disruption_data.get('reason'),
            priority=disruption_data.get('priority', 'MEDIUM'),
            compensation_eligible=disruption_data.get('compensation_eligible', False),
            compensation_amount=disruption_data.get('compensation_amount')
        )
        db.add(disruption)
        db.commit()
        db.refresh(disruption)
        return disruption
    finally:
        db.close()


# New helper functions for the newly implemented models

def create_disruption_alert(event_id: str, user_id: str, alert_data: dict) -> DisruptionAlert:
    """Create a new disruption alert"""
    db = SessionLocal()
    try:
        alert = DisruptionAlert(
            alert_id=f"alert_{event_id}_{alert_data['alert_type']}_{datetime.now().timestamp()}",
            event_id=event_id,
            user_id=user_id,
            alert_type=alert_data['alert_type'],
            risk_severity=alert_data.get('risk_severity', 'MEDIUM'),
            alert_message=alert_data['alert_message'],
            urgency_score=alert_data.get('urgency_score', 50),
            expires_at=alert_data.get('expires_at'),
            alert_metadata=alert_data.get('alert_metadata', {})
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert
    finally:
        db.close()


def create_alternative_flight(event_id: str, flight_data: dict) -> AlternativeFlight:
    """Create a new alternative flight option"""
    db = SessionLocal()
    try:
        alternative = AlternativeFlight(
            alternative_id=f"alt_{event_id}_{flight_data['flight_number']}_{datetime.now().timestamp()}",
            event_id=event_id,
            flight_number=flight_data['flight_number'],
            airline=flight_data['airline'],
            departure_time=flight_data['departure_time'],
            arrival_time=flight_data['arrival_time'],
            origin=flight_data['origin'],
            destination=flight_data['destination'],
            booking_class=flight_data['booking_class'],
            available_seats=flight_data.get('available_seats', 0),
            price=flight_data.get('price'),
            currency=flight_data.get('currency', 'USD'),
            policy_compliant=flight_data.get('policy_compliant', False),
            class_downgrade_approved=flight_data.get('class_downgrade_approved', False),
            airline_restriction_compliant=flight_data.get('airline_restriction_compliant', True),
            route_policy_compliant=flight_data.get('route_policy_compliant', True),
            time_window_compliant=flight_data.get('time_window_compliant', True),
            cost_policy_compliant=flight_data.get('cost_policy_compliant', True),
            stops=flight_data.get('stops', 0),
            layover_duration=flight_data.get('layover_duration'),
            flight_duration=flight_data.get('flight_duration'),
            recommended_rank=flight_data.get('recommended_rank'),
            user_preference_score=flight_data.get('user_preference_score', 50),
            booking_deadline=flight_data.get('booking_deadline')
        )
        db.add(alternative)
        db.commit()
        db.refresh(alternative)
        return alternative
    finally:
        db.close()


def create_flight_hold(booking_id: str, user_id: str, hold_data: dict) -> FlightHold:
    """Create a new flight hold"""
    db = SessionLocal()
    try:
        # Calculate hold expiration time
        from datetime import timedelta
        hold_duration = hold_data.get('hold_duration_minutes', 15)
        hold_expires_at = datetime.utcnow() + timedelta(minutes=hold_duration)
        
        hold = FlightHold(
            hold_id=f"hold_{booking_id}_{hold_data['flight_number']}_{datetime.now().timestamp()}",
            booking_id=booking_id,
            alternative_id=hold_data.get('alternative_id'),
            user_id=user_id,
            flight_number=hold_data['flight_number'],
            airline=hold_data['airline'],
            departure_time=hold_data['departure_time'],
            arrival_time=hold_data['arrival_time'],
            origin=hold_data['origin'],
            destination=hold_data['destination'],
            booking_class=hold_data['booking_class'],
            hold_type=hold_data.get('hold_type', 'AUTOMATIC'),
            hold_duration_minutes=hold_duration,
            hold_expires_at=hold_expires_at,
            seats_held=hold_data.get('seats_held', 1),
            hold_reference=hold_data.get('hold_reference'),
            price_locked=hold_data.get('price_locked'),
            payment_required_by=hold_data.get('payment_required_by'),
            cancellation_deadline=hold_data.get('cancellation_deadline')
        )
        db.add(hold)
        db.commit()
        db.refresh(hold)
        return hold
    finally:
        db.close()


def get_active_disruption_alerts(user_id: str = None, risk_severity: str = None):
    """Get active disruption alerts, optionally filtered by user and severity"""
    db = SessionLocal()
    try:
        query = db.query(DisruptionAlert).filter(
            DisruptionAlert.delivery_status != "DELIVERED",
            DisruptionAlert.expires_at > datetime.utcnow()
        )
        if user_id:
            query = query.filter(DisruptionAlert.user_id == user_id)
        if risk_severity:
            query = query.filter(DisruptionAlert.risk_severity == risk_severity)
        return query.order_by(DisruptionAlert.urgency_score.desc()).all()
    finally:
        db.close()


def get_policy_compliant_alternatives(event_id: str):
    """Get all policy-compliant alternative flights for a disruption event"""
    db = SessionLocal()
    try:
        return db.query(AlternativeFlight).filter(
            AlternativeFlight.event_id == event_id,
            AlternativeFlight.policy_compliant == True,
            AlternativeFlight.availability_status == "AVAILABLE"
        ).order_by(AlternativeFlight.recommended_rank).all()
    finally:
        db.close()


def get_active_flight_holds(user_id: str = None):
    """Get all active flight holds, optionally filtered by user"""
    db = SessionLocal()
    try:
        query = db.query(FlightHold).filter(
            FlightHold.hold_status == "ACTIVE",
            FlightHold.hold_expires_at > datetime.utcnow()
        )
        if user_id:
            query = query.filter(FlightHold.user_id == user_id)
        return query.order_by(FlightHold.hold_expires_at).all()
    finally:
        db.close()


def extend_flight_hold(hold_id: str, additional_minutes: int = 15, reason: str = None) -> FlightHold:
    """Extend a flight hold by additional minutes"""
    db = SessionLocal()
    try:
        hold = db.query(FlightHold).filter(FlightHold.hold_id == hold_id).first()
        if not hold:
            raise ValueError(f"Flight hold {hold_id} not found")
        
        if hold.extension_count >= hold.max_extensions_allowed:
            raise ValueError(f"Maximum extensions ({hold.max_extensions_allowed}) already reached")
        
        from datetime import timedelta
        new_expiry = hold.hold_expires_at + timedelta(minutes=additional_minutes)
        hold.hold_expires_at = new_expiry
        hold.extended_until = new_expiry
        hold.extension_count += 1
        hold.extension_reason = reason or "User requested extension"
        hold.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(hold)
        return hold
    finally:
        db.close()


def release_flight_hold(hold_id: str) -> FlightHold:
    """Release a flight hold"""
    db = SessionLocal()
    try:
        hold = db.query(FlightHold).filter(FlightHold.hold_id == hold_id).first()
        if not hold:
            raise ValueError(f"Flight hold {hold_id} not found")
        
        hold.hold_status = "RELEASED"
        hold.released_at = datetime.utcnow()
        hold.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(hold)
        return hold
    finally:
        db.close()


def convert_hold_to_booking(hold_id: str) -> FlightHold:
    """Convert a flight hold to a confirmed booking"""
    db = SessionLocal()
    try:
        hold = db.query(FlightHold).filter(FlightHold.hold_id == hold_id).first()
        if not hold:
            raise ValueError(f"Flight hold {hold_id} not found")
        
        hold.hold_status = "CONVERTED"
        hold.converted_to_booking_at = datetime.utcnow()
        hold.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(hold)
        return hold
    finally:
        db.close()



def get_or_create_wallet(user_id: str) -> Wallet:
    """Get or create a wallet for a user"""
    db = SessionLocal()
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if not wallet:
            wallet = Wallet(
                wallet_id=f"wallet_{user_id}_{datetime.now().timestamp()}",
                user_id=user_id,
                balance=0.0
            )
            db.add(wallet)
            db.commit()
            db.refresh(wallet)
        return wallet
    finally:
        db.close()


def create_compensation_rule(rule_data: dict, created_by: str = "system") -> CompensationRule:
    """Create a new compensation rule"""
    db = SessionLocal()
    try:
        # Generate unique rule ID
        rule_id = f"rule_{rule_data['disruption_type'].lower()}_{datetime.now().timestamp()}"
        
        rule = CompensationRule(
            rule_id=rule_id,
            rule_name=rule_data['rule_name'],
            description=rule_data['description'],
            disruption_type=rule_data['disruption_type'],
            amount=rule_data['amount'],
            conditions=rule_data.get('conditions', {}),
            priority=rule_data.get('priority', 0),
            created_by=created_by
        )
        
        db.add(rule)
        
        # Create history record
        history = CompensationRuleHistory(
            history_id=f"history_{rule_id}_{datetime.now().timestamp()}",
            rule_id=rule_id,
            rule_name=rule.rule_name,
            description=rule.description,
            disruption_type=rule.disruption_type,
            amount=rule.amount,
            conditions=rule.conditions,
            priority=rule.priority,
            is_active=rule.is_active,
            version=rule.version,
            action="CREATED",
            created_by=created_by
        )
        
        db.add(history)
        db.commit()
        db.refresh(rule)
        return rule
    finally:
        db.close()


def get_users_with_sms_enabled():
    """Get all users who have SMS notifications enabled"""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.phone.isnot(None)).all()
        sms_enabled_users = []
        
        for user in users:
            preferences = user.preferences or {}
            sms_prefs = preferences.get('sms', {})
            if sms_prefs.get('enabled', False):
                sms_enabled_users.append(user)
        
        return sms_enabled_users
    finally:
        db.close()


def update_compensation_rule(rule_id: str, updated_data: dict, updated_by: str = "system") -> CompensationRule:
    """Update an existing compensation rule and create audit trail"""
    db = SessionLocal()
    try:
        rule = db.query(CompensationRule).filter(CompensationRule.rule_id == rule_id).first()
        if not rule:
            raise ValueError(f"Compensation rule {rule_id} not found")
        
        # Create history record before updating
        history = CompensationRuleHistory(
            history_id=f"history_{rule_id}_{datetime.now().timestamp()}",
            rule_id=rule_id,
            rule_name=rule.rule_name,
            description=rule.description,
            disruption_type=rule.disruption_type,
            amount=rule.amount,
            conditions=rule.conditions,
            priority=rule.priority,
            is_active=rule.is_active,
            version=rule.version,
            action="UPDATED",
            created_by=updated_by
        )
        
        # Update rule fields
        if 'rule_name' in updated_data:
            rule.rule_name = updated_data['rule_name']
        if 'description' in updated_data:
            rule.description = updated_data['description']
        if 'disruption_type' in updated_data:
            rule.disruption_type = updated_data['disruption_type']
        if 'amount' in updated_data:
            rule.amount = updated_data['amount']
        if 'conditions' in updated_data:
            rule.conditions = updated_data['conditions']
        if 'priority' in updated_data:
            rule.priority = updated_data['priority']
        if 'is_active' in updated_data:
            rule.is_active = updated_data['is_active']
        
        # Increment version
        rule.version += 1
        rule.updated_at = datetime.utcnow()
        rule.created_by = updated_by
        
        db.add(history)
        db.commit()
        db.refresh(rule)
        return rule
    finally:
        db.close()


def update_user_phone(email: str, phone: str) -> bool:
    """Update user phone number"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.phone = phone
            db.commit()
            return True
        return False
    finally:
        db.close()


def get_active_compensation_rules(disruption_type: str = None) -> list:
    """Get all active compensation rules, optionally filtered by disruption type"""
    db = SessionLocal()
    try:
        query = db.query(CompensationRule).filter(CompensationRule.is_active == True)
        if disruption_type:
            query = query.filter(CompensationRule.disruption_type == disruption_type)
        return query.order_by(CompensationRule.priority.desc()).all()
    finally:
        db.close()


def get_high_priority_disruptions():
    """Get unnotified high-priority disruptions for SMS alerts"""
    db = SessionLocal()
    try:
        return db.query(DisruptionEvent).filter(
            DisruptionEvent.user_notified == False,
            DisruptionEvent.priority == "HIGH"
        ).all()
    finally:
        db.close()


def get_all_compensation_rules() -> list:
    """Get all compensation rules (active and inactive)"""
    db = SessionLocal()
    try:
        return db.query(CompensationRule).order_by(
            CompensationRule.is_active.desc(),
            CompensationRule.priority.desc()
        ).all()
    finally:
        db.close()


def get_compensation_rule_by_id(rule_id: str) -> CompensationRule:
    """Get a specific compensation rule by ID"""
    db = SessionLocal()
    try:
        return db.query(CompensationRule).filter(CompensationRule.rule_id == rule_id).first()
    finally:
        db.close()


def deactivate_compensation_rule(rule_id: str, deactivated_by: str = "system") -> CompensationRule:
    """Deactivate a compensation rule"""
    db = SessionLocal()
    try:
        rule = db.query(CompensationRule).filter(CompensationRule.rule_id == rule_id).first()
        if not rule:
            raise ValueError(f"Compensation rule {rule_id} not found")
        
        # Create history record
        history = CompensationRuleHistory(
            history_id=f"history_{rule_id}_{datetime.now().timestamp()}",
            rule_id=rule_id,
            rule_name=rule.rule_name,
            description=rule.description,
            disruption_type=rule.disruption_type,
            amount=rule.amount,
            conditions=rule.conditions,
            priority=rule.priority,
            is_active=rule.is_active,
            version=rule.version,
            action="DEACTIVATED",
            created_by=deactivated_by
        )
        
        rule.is_active = False
        rule.version += 1
        rule.updated_at = datetime.utcnow()
        rule.created_by = deactivated_by
        
        db.add(history)
        db.commit()
        db.refresh(rule)
        return rule
    finally:
        db.close()


def get_compensation_rule_history(rule_id: str) -> list:
    """Get audit trail for a specific compensation rule"""
    db = SessionLocal()
    try:
        return db.query(CompensationRuleHistory).filter(
            CompensationRuleHistory.rule_id == rule_id
        ).order_by(CompensationRuleHistory.created_at.desc()).all()
    finally:
        db.close()


def validate_compensation_rule(rule_data: dict) -> dict:
    """Validate compensation rule data and check for conflicts"""
    errors = []
    warnings = []
    
    # Required field validation
    required_fields = ['rule_name', 'description', 'disruption_type', 'amount']
    for field in required_fields:
        if field not in rule_data or not rule_data[field]:
            errors.append(f"Field '{field}' is required")
    
    # Disruption type validation
    valid_disruption_types = ['CANCELLED', 'DELAYED', 'DIVERTED', 'OVERBOOKED']
    if 'disruption_type' in rule_data and rule_data['disruption_type'] not in valid_disruption_types:
        errors.append(f"Invalid disruption_type. Must be one of: {', '.join(valid_disruption_types)}")
    
    # Amount validation
    if 'amount' in rule_data:
        try:
            amount = float(rule_data['amount'])
            if amount < 0:
                errors.append("Amount must be non-negative")
            if amount > 10000:
                warnings.append("Amount is very high (>$10,000). Please verify.")
        except (TypeError, ValueError):
            errors.append("Amount must be a valid number")
    
    # Priority validation
    if 'priority' in rule_data:
        try:
            priority = int(rule_data['priority'])
            if priority < 0 or priority > 100:
                warnings.append("Priority should be between 0-100 for best results")
        except (TypeError, ValueError):
            errors.append("Priority must be a valid integer")
    
    # Conditions validation
    if 'conditions' in rule_data and isinstance(rule_data['conditions'], dict):
        for condition_key, condition_value in rule_data['conditions'].items():
            if condition_key.endswith('_min') or condition_key.endswith('_max'):
                try:
                    float(condition_value)
                except (TypeError, ValueError):
                    errors.append(f"Condition '{condition_key}' must be a valid number")
    
    # Check for potential conflicts with existing rules
    db = SessionLocal()
    try:
        if 'disruption_type' in rule_data:
            existing_rules = db.query(CompensationRule).filter(
                CompensationRule.disruption_type == rule_data['disruption_type'],
                CompensationRule.is_active == True
            ).all()
            
            if existing_rules:
                # Check for similar conditions that might cause conflicts
                for existing_rule in existing_rules:
                    if ('priority' in rule_data and 
                        existing_rule.priority == rule_data.get('priority', 0)):
                        warnings.append(
                            f"Rule with same priority ({rule_data.get('priority', 0)}) "
                            f"already exists for {rule_data['disruption_type']}: "
                            f"{existing_rule.rule_name}"
                        )
    finally:
        db.close()
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


# New helper functions for Policy Compliance and Approval Workflow models


def create_travel_policy(policy_data: dict, created_by: str) -> TravelPolicy:
    """Create a new travel policy"""
    db = SessionLocal()
    try:
        # Generate unique policy ID
        policy_id = f"policy_{policy_data['policy_type'].lower()}_{datetime.now().timestamp()}"
        
        policy = TravelPolicy(
            policy_id=policy_id,
            policy_name=policy_data['policy_name'],
            policy_version=policy_data.get('policy_version', '1.0'),
            description=policy_data['description'],
            policy_type=policy_data['policy_type'],
            scope=policy_data.get('scope', 'GLOBAL'),
            target_audience=policy_data.get('target_audience', {}),
            rules=policy_data['rules'],
            enforcement_level=policy_data.get('enforcement_level', 'STRICT'),
            auto_compliance_check=policy_data.get('auto_compliance_check', True),
            allow_exceptions=policy_data.get('allow_exceptions', True),
            exception_requires_approval=policy_data.get('exception_requires_approval', True),
            effective_date=policy_data['effective_date'],
            expiration_date=policy_data.get('expiration_date'),
            created_by=created_by
        )
        
        db.add(policy)
        db.commit()
        db.refresh(policy)
        return policy
    finally:
        db.close()


def create_approval_request(request_data: dict, user_id: str) -> ApprovalRequest:
    """Create a new approval request with escalation chain"""
    db = SessionLocal()
    try:
        # Generate unique request ID
        request_id = f"approval_{request_data['request_type'].lower()}_{datetime.now().timestamp()}"
        
        # Set escalation due date based on first level in chain
        escalation_due = None
        if request_data['escalation_chain']:
            first_level = request_data['escalation_chain'][0]
            timeout_hours = first_level.get('timeout_hours', 24)
            escalation_due = datetime.utcnow() + timedelta(hours=timeout_hours)
        
        # Set current approver from first level
        current_approver_id = None
        current_approver_role = None
        if request_data['escalation_chain']:
            first_level = request_data['escalation_chain'][0]
            current_approver_id = first_level.get('approver_id')
            current_approver_role = first_level.get('approver_role')
        
        approval_request = ApprovalRequest(
            request_id=request_id,
            user_id=user_id,
            booking_id=request_data.get('booking_id'),
            policy_id=request_data.get('policy_id'),
            request_type=request_data['request_type'],
            title=request_data['title'],
            description=request_data['description'],
            justification=request_data.get('justification'),
            request_data=request_data['request_data'],
            priority=request_data.get('priority', 'MEDIUM'),
            escalation_chain=request_data['escalation_chain'],
            current_approver_id=current_approver_id,
            current_approver_role=current_approver_role,
            due_date=request_data.get('due_date'),
            escalation_due=escalation_due,
            approval_history=[{
                "timestamp": datetime.utcnow().isoformat(),
                "action": "CREATED",
                "user_id": user_id,
                "notes": f"Request created: {request_data['title']}"
            }]
        )
        
        db.add(approval_request)
        db.commit()
        db.refresh(approval_request)
        return approval_request
    finally:
        db.close()


def create_policy_exception(exception_data: dict, booking_id: str, policy_id: str) -> PolicyException:
    """Create a new policy exception"""
    db = SessionLocal()
    try:
        # Generate unique exception ID
        exception_id = f"exception_{exception_data['exception_type'].lower()}_{datetime.now().timestamp()}"
        
        exception = PolicyException(
            exception_id=exception_id,
            booking_id=booking_id,
            policy_id=policy_id,
            exception_type=exception_data['exception_type'],
            violation_category=exception_data['violation_category'],
            severity=exception_data.get('severity', 'MEDIUM'),
            violated_rule=exception_data['violated_rule'],
            expected_value=exception_data.get('expected_value'),
            actual_value=exception_data.get('actual_value'),
            violation_amount=exception_data.get('violation_amount'),
            title=exception_data['title'],
            description=exception_data['description'],
            violation_details=exception_data['violation_details'],
            requires_approval=exception_data.get('requires_approval', True),
            approval_request_id=exception_data.get('approval_request_id'),
            user_justification=exception_data.get('user_justification'),
            business_justification=exception_data.get('business_justification'),
            cost_impact=exception_data.get('cost_impact'),
            savings_foregone=exception_data.get('savings_foregone'),
            is_recurring=exception_data.get('is_recurring', False),
            previous_exceptions=exception_data.get('previous_exceptions', [])
        )
        
        db.add(exception)
        db.commit()
        db.refresh(exception)
        return exception
    finally:
        db.close()


def get_active_travel_policies(scope: str = None, policy_type: str = None) -> list:
    """Get active travel policies, optionally filtered by scope and type"""
    db = SessionLocal()
    try:
        query = db.query(TravelPolicy).filter(TravelPolicy.is_active == True)
        if scope:
            query = query.filter(TravelPolicy.scope == scope)
        if policy_type:
            query = query.filter(TravelPolicy.policy_type == policy_type)
        return query.order_by(TravelPolicy.created_at.desc()).all()
    finally:
        db.close()


def get_pending_approval_requests(approver_id: str = None) -> list:
    """Get pending approval requests, optionally filtered by approver"""
    db = SessionLocal()
    try:
        query = db.query(ApprovalRequest).filter(ApprovalRequest.status == "PENDING")
        if approver_id:
            query = query.filter(ApprovalRequest.current_approver_id == approver_id)
        return query.order_by(ApprovalRequest.priority.desc(), ApprovalRequest.created_at.asc()).all()
    finally:
        db.close()


def get_policy_exceptions_by_booking(booking_id: str) -> list:
    """Get all policy exceptions for a specific booking"""
    db = SessionLocal()
    try:
        return db.query(PolicyException).filter(PolicyException.booking_id == booking_id).all()
    finally:
        db.close()


def escalate_approval_request(request_id: str) -> ApprovalRequest:
    """Escalate an approval request to the next level"""
    db = SessionLocal()
    try:
        request = db.query(ApprovalRequest).filter(ApprovalRequest.request_id == request_id).first()
        if not request:
            raise ValueError(f"Approval request {request_id} not found")
        
        # Find next escalation level
        next_level = request.escalation_level + 1
        if next_level >= len(request.escalation_chain):
            raise ValueError("Cannot escalate further - already at highest level")
        
        # Update to next level
        next_level_info = request.escalation_chain[next_level]
        request.escalation_level = next_level
        request.current_approver_id = next_level_info.get('approver_id')
        request.current_approver_role = next_level_info.get('approver_role')
        request.status = "ESCALATED"
        
        # Update escalation due date
        timeout_hours = next_level_info.get('timeout_hours', 48)
        request.escalation_due = datetime.utcnow() + timedelta(hours=timeout_hours)
        
        # Add to approval history
        history = list(request.approval_history) if request.approval_history else []
        history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "ESCALATED",
            "from_level": next_level - 1,
            "to_level": next_level,
            "new_approver": request.current_approver_id,
            "reason": "Timeout or explicit escalation"
        })
        request.approval_history = history
        
        request.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(request)
        return request
    finally:
        db.close()


def approve_request(request_id: str, approver_id: str, notes: str = None) -> ApprovalRequest:
    """Approve an approval request"""
    db = SessionLocal()
    try:
        request = db.query(ApprovalRequest).filter(ApprovalRequest.request_id == request_id).first()
        if not request:
            raise ValueError(f"Approval request {request_id} not found")
        
        # Update request status
        request.status = "APPROVED"
        request.approved_by = approver_id
        request.approved_at = datetime.utcnow()
        request.resolved_at = datetime.utcnow()
        request.approval_notes = notes
        
        # Add to approval history
        history = list(request.approval_history) if request.approval_history else []
        history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "APPROVED",
            "user_id": approver_id,
            "level": request.escalation_level,
            "notes": notes or "Request approved"
        })
        request.approval_history = history
        
        request.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(request)
        return request
    finally:
        db.close()


def reject_request(request_id: str, approver_id: str, reason: str) -> ApprovalRequest:
    """Reject an approval request"""
    db = SessionLocal()
    try:
        request = db.query(ApprovalRequest).filter(ApprovalRequest.request_id == request_id).first()
        if not request:
            raise ValueError(f"Approval request {request_id} not found")
        
        # Update request status
        request.status = "REJECTED"
        request.approved_by = approver_id
        request.resolved_at = datetime.utcnow()
        request.rejection_reason = reason
        
        # Add to approval history
        history = list(request.approval_history) if request.approval_history else []
        history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "REJECTED",
            "user_id": approver_id,
            "level": request.escalation_level,
            "reason": reason
        })
        request.approval_history = history
        
        request.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(request)
        return request
    finally:
        db.close()


def resolve_policy_exception(exception_id: str, resolved_by: str, resolution_action: str, notes: str = None) -> PolicyException:
    """Resolve a policy exception"""
    db = SessionLocal()
    try:
        exception = db.query(PolicyException).filter(PolicyException.exception_id == exception_id).first()
        if not exception:
            raise ValueError(f"Policy exception {exception_id} not found")
        
        # Update exception status
        exception.status = "RESOLVED"
        exception.resolved_by = resolved_by
        exception.resolved_at = datetime.utcnow()
        exception.resolution_date = datetime.utcnow()
        exception.resolution_action = resolution_action
        exception.resolution_notes = notes
        exception.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(exception)
        return exception
    finally:
        db.close()


def check_policy_compliance(booking_data: dict, policies: list = None) -> list:
    """
    Check booking data against travel policies and return violations.
    This is a simplified implementation - in practice, this would contain
    sophisticated rule evaluation logic.
    """
    violations = []
    
    if policies is None:
        # Get all active policies
        policies = get_active_travel_policies()
    
    for policy in policies:
        rules = policy.rules
        
        # Check booking limits
        if 'booking_limits' in rules:
            booking_limits = rules['booking_limits']
            
            # Check fare amount
            if 'max_fare_amount' in booking_limits:
                max_fare = booking_limits['max_fare_amount']
                if booking_data.get('fare_amount', 0) > max_fare:
                    violations.append({
                        'policy_id': policy.policy_id,
                        'violation_type': 'FARE_LIMIT_EXCEEDED',
                        'rule_path': 'booking_limits.max_fare_amount',
                        'expected_value': max_fare,
                        'actual_value': booking_data.get('fare_amount'),
                        'message': f"Fare amount ${booking_data.get('fare_amount')} exceeds policy limit of ${max_fare}"
                    })
            
            # Check booking class
            if 'allowed_booking_classes' in booking_limits:
                allowed_classes = booking_limits['allowed_booking_classes']
                actual_class = booking_data.get('booking_class', 'Economy')
                if actual_class not in allowed_classes:
                    violations.append({
                        'policy_id': policy.policy_id,
                        'violation_type': 'BOOKING_CLASS_VIOLATION',
                        'rule_path': 'booking_limits.allowed_booking_classes',
                        'expected_value': ', '.join(allowed_classes),
                        'actual_value': actual_class,
                        'message': f"Booking class '{actual_class}' not allowed. Permitted classes: {', '.join(allowed_classes)}"
                    })
            
            # Check advance booking requirement
            if 'advance_booking_days' in booking_limits:
                required_days = booking_limits['advance_booking_days']
                departure_date = booking_data.get('departure_date')
                if departure_date:
                    if isinstance(departure_date, str):
                        departure_date = datetime.fromisoformat(departure_date)
                    days_in_advance = (departure_date - datetime.utcnow()).days
                    if days_in_advance < required_days:
                        violations.append({
                            'policy_id': policy.policy_id,
                            'violation_type': 'ADVANCE_BOOKING_VIOLATION',
                            'rule_path': 'booking_limits.advance_booking_days',
                            'expected_value': f"{required_days} days",
                            'actual_value': f"{days_in_advance} days",
                            'message': f"Booking must be made at least {required_days} days in advance. Current advance: {days_in_advance} days"
                        })
    
    return violations
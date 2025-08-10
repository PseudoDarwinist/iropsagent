# flight_agent/models.py
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Boolean, ForeignKey, Float, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
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
    trip_monitors = relationship("TripMonitor", back_populates="booking")


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
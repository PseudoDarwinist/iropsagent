# flight_agent/models.py
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Boolean, ForeignKey, Float, Integer
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


class Booking(Base):
    __tablename__ = "bookings"
    
    booking_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"))
    pnr = Column(String)  # Passenger Name Record / Confirmation Number
    airline = Column(String)
    flight_number = Column(String)
    departure_date = Column(DateTime)
    origin = Column(String)  # Airport code
    destination = Column(String)  # Airport code
    booking_class = Column(String)  # Economy, Business, First
    seat = Column(String)
    status = Column(String, default="CONFIRMED")  # CONFIRMED, CANCELLED, COMPLETED
    raw_data = Column(JSON)  # Store complete booking data
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="bookings")
    disruption_events = relationship("DisruptionEvent", back_populates="booking")


class DisruptionEvent(Base):
    __tablename__ = "disruption_events"
    
    event_id = Column(String, primary_key=True)
    booking_id = Column(String, ForeignKey("bookings.booking_id"))
    detected_at = Column(DateTime, default=datetime.utcnow)
    disruption_type = Column(String)  # CANCELLED, DELAYED, DIVERTED
    original_departure = Column(DateTime)
    new_departure = Column(DateTime)
    rebooking_status = Column(String, default="PENDING")  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    rebooking_options = Column(JSON)  # Store alternative flight options
    selected_option = Column(JSON)
    user_notified = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    priority = Column(String, default="MEDIUM")  # HIGH, MEDIUM, LOW - for SMS filtering
    
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
            pnr=booking_data['pnr'],
            airline=booking_data['airline'],
            flight_number=booking_data['flight_number'],
            departure_date=booking_data['departure_date'],  # This stays as datetime for the column
            origin=booking_data['origin'],
            destination=booking_data['destination'],
            booking_class=booking_data.get('class', 'Economy'),
            seat=booking_data.get('seat'),
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
            priority=disruption_data.get('priority', 'MEDIUM')
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
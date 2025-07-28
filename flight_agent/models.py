# flight_agent/models.py
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Boolean, ForeignKey, Float
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
    preferences = Column(JSON, default={})  # seat preference, airline preference, SMS preferences, etc.
    
    # Relationships
    bookings = relationship("Booking", back_populates="user")
    email_connections = relationship("EmailConnection", back_populates="user")


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
    
    # Relationships
    booking = relationship("Booking", back_populates="disruption_events")


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


def update_user_phone(user_id: str, phone: str) -> bool:
    """Update user's phone number"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return False
        
        user.phone = phone
        db.commit()
        return True
    except Exception as e:
        print(f"Error updating phone number: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def enable_sms_notifications(user_id: str, severity_levels: list = None) -> bool:
    """Enable SMS notifications for a user"""
    if severity_levels is None:
        severity_levels = ["major"]  # Default to major disruptions only
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return False
        
        if not user.preferences:
            user.preferences = {}
        
        user.preferences["sms_notifications"] = {
            "enabled": True,
            "severity_levels": severity_levels,
            "quiet_hours": {"enabled": False, "start": "22:00", "end": "08:00"}
        }
        
        db.commit()
        return True
    except Exception as e:
        print(f"Error enabling SMS notifications: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def disable_sms_notifications(user_id: str) -> bool:
    """Disable SMS notifications for a user"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return False
        
        if not user.preferences:
            user.preferences = {}
        
        user.preferences["sms_notifications"] = {
            "enabled": False,
            "severity_levels": [],
            "quiet_hours": {"enabled": False, "start": "22:00", "end": "08:00"}
        }
        
        db.commit()
        return True
    except Exception as e:
        print(f"Error disabling SMS notifications: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def get_user_sms_preferences(user_id: str) -> dict:
    """Get user's SMS notification preferences"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {"error": "User not found"}
        
        return user.preferences.get("sms_notifications", {
            "enabled": False,
            "severity_levels": ["major"],
            "quiet_hours": {"enabled": False, "start": "22:00", "end": "08:00"}
        })
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    finally:
        db.close()
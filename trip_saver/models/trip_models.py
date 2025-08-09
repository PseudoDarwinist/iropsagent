# trip_saver/models/trip_models.py
from sqlalchemy import Column, String, DateTime, JSON, Boolean, ForeignKey, Float, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from flight_agent.models import Base

class TripPlan(Base):
    """
    Represents a planned trip that needs proactive monitoring
    """
    __tablename__ = "trip_plans"
    
    trip_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"))
    trip_name = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    origin = Column(String, nullable=False)  # Primary departure airport
    destination = Column(String, nullable=False)  # Primary destination airport
    trip_type = Column(String, default="ROUND_TRIP")  # ROUND_TRIP, ONE_WAY, MULTI_CITY
    status = Column(String, default="PLANNED")  # PLANNED, ACTIVE, COMPLETED, CANCELLED
    priority = Column(String, default="MEDIUM")  # HIGH, MEDIUM, LOW
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    preferences = Column(JSON, default={})  # Trip-specific preferences
    
    # Relationships
    trip_alerts = relationship("TripAlert", back_populates="trip_plan")
    proactive_suggestions = relationship("ProactiveSuggestion", back_populates="trip_plan")


class TripAlert(Base):
    """
    Represents proactive alerts for potential trip disruptions
    """
    __tablename__ = "trip_alerts"
    
    alert_id = Column(String, primary_key=True)
    trip_id = Column(String, ForeignKey("trip_plans.trip_id"))
    alert_type = Column(String, nullable=False)  # WEATHER, STRIKE, AIRPORT_DELAY, PRICE_DROP
    severity = Column(String, default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # When the alert becomes irrelevant
    is_active = Column(Boolean, default=True)
    user_notified = Column(Boolean, default=False)
    actions_taken = Column(JSON, default=[])  # List of actions taken based on this alert
    alert_metadata = Column(JSON, default={})  # Additional alert-specific data (renamed from metadata)
    
    # Relationships
    trip_plan = relationship("TripPlan", back_populates="trip_alerts")


class ProactiveSuggestion(Base):
    """
    Represents AI-generated suggestions for trip optimization
    """
    __tablename__ = "proactive_suggestions"
    
    suggestion_id = Column(String, primary_key=True)
    trip_id = Column(String, ForeignKey("trip_plans.trip_id"))
    suggestion_type = Column(String, nullable=False)  # REBOOKING, HOTEL_UPGRADE, ALTERNATIVE_ROUTE
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    confidence_score = Column(Float, default=0.0)  # AI confidence in suggestion (0.0-1.0)
    potential_savings = Column(Float, default=0.0)  # Estimated cost savings
    time_savings_minutes = Column(Integer, default=0)  # Estimated time savings
    expires_at = Column(DateTime)  # When the suggestion becomes invalid
    status = Column(String, default="PENDING")  # PENDING, ACCEPTED, REJECTED, EXPIRED
    created_at = Column(DateTime, default=datetime.utcnow)
    user_response_at = Column(DateTime)
    suggestion_data = Column(JSON, default={})  # Detailed suggestion information
    
    # Relationships
    trip_plan = relationship("TripPlan", back_populates="proactive_suggestions")


class TripOptimization(Base):
    """
    Tracks optimization metrics and performance for trips
    """
    __tablename__ = "trip_optimizations"
    
    optimization_id = Column(String, primary_key=True)
    trip_id = Column(String, ForeignKey("trip_plans.trip_id"))
    optimization_type = Column(String, nullable=False)  # COST, TIME, COMFORT, RELIABILITY
    original_value = Column(Float)  # Original metric value
    optimized_value = Column(Float)  # Improved metric value
    improvement_percentage = Column(Float)  # Percentage improvement
    optimization_method = Column(String)  # How the optimization was achieved
    applied_at = Column(DateTime, default=datetime.utcnow)
    metrics = Column(JSON, default={})  # Additional optimization metrics
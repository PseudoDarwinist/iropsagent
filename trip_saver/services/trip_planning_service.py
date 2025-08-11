# trip_saver/services/trip_planning_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from flight_agent.models import SessionLocal
from trip_saver.models.trip_models import TripPlan, TripAlert, ProactiveSuggestion
import uuid


class TripPlanningService:
    """
    Service for managing proactive trip planning operations
    """
    
    def __init__(self):
        self.db = SessionLocal

    def create_trip_plan(self, user_id: str, trip_data: Dict[str, Any]) -> TripPlan:
        """
        Create a new trip plan for proactive monitoring
        """
        db = self.db()
        try:
            trip = TripPlan(
                trip_id=f"trip_{user_id}_{datetime.now().timestamp()}",
                user_id=user_id,
                trip_name=trip_data['trip_name'],
                start_date=trip_data['start_date'],
                end_date=trip_data['end_date'],
                origin=trip_data['origin'],
                destination=trip_data['destination'],
                trip_type=trip_data.get('trip_type', 'ROUND_TRIP'),
                priority=trip_data.get('priority', 'MEDIUM'),
                preferences=trip_data.get('preferences', {})
            )
            
            db.add(trip)
            db.commit()
            db.refresh(trip)
            return trip
        finally:
            db.close()

    def get_active_trips(self, user_id: Optional[str] = None) -> List[TripPlan]:
        """
        Get all active trips, optionally filtered by user
        """
        db = self.db()
        try:
            query = db.query(TripPlan).filter(
                TripPlan.status.in_(["PLANNED", "ACTIVE"]),
                TripPlan.start_date > datetime.utcnow()
            )
            if user_id:
                query = query.filter(TripPlan.user_id == user_id)
            return query.all()
        finally:
            db.close()

    def update_trip_status(self, trip_id: str, status: str) -> Optional[TripPlan]:
        """
        Update trip status
        """
        db = self.db()
        try:
            trip = db.query(TripPlan).filter(TripPlan.trip_id == trip_id).first()
            if trip:
                trip.status = status
                trip.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(trip)
            return trip
        finally:
            db.close()

    def get_trips_requiring_monitoring(self, days_ahead: int = 7) -> List[TripPlan]:
        """
        Get trips that need proactive monitoring within specified days
        """
        db = self.db()
        try:
            cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
            return db.query(TripPlan).filter(
                TripPlan.status.in_(["PLANNED", "ACTIVE"]),
                TripPlan.start_date <= cutoff_date,
                TripPlan.start_date > datetime.utcnow()
            ).all()
        finally:
            db.close()

    def analyze_trip_risks(self, trip_id: str) -> Dict[str, Any]:
        """
        Analyze potential risks for a trip
        """
        # This would integrate with external APIs for weather, strikes, etc.
        # For now, return a placeholder structure
        return {
            'weather_risk': 'LOW',
            'strike_risk': 'LOW',
            'airport_congestion_risk': 'MEDIUM',
            'price_volatility_risk': 'HIGH',
            'overall_risk_score': 0.3
        }
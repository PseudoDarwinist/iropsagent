# trip_saver/services/alert_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from flight_agent.models import SessionLocal
from trip_saver.models.trip_models import TripPlan, TripAlert, ProactiveSuggestion
import uuid


class AlertService:
    """
    Service for managing proactive trip alerts and notifications
    """
    
    def __init__(self):
        self.db = SessionLocal

    def create_alert(self, trip_id: str, alert_data: Dict[str, Any]) -> TripAlert:
        """
        Create a new trip alert
        """
        db = self.db()
        try:
            alert = TripAlert(
                alert_id=f"alert_{trip_id}_{datetime.now().timestamp()}",
                trip_id=trip_id,
                alert_type=alert_data['alert_type'],
                severity=alert_data.get('severity', 'MEDIUM'),
                title=alert_data['title'],
                description=alert_data['description'],
                expires_at=alert_data.get('expires_at'),
                alert_metadata=alert_data.get('alert_metadata', {})
            )
            
            db.add(alert)
            db.commit()
            db.refresh(alert)
            return alert
        finally:
            db.close()

    def get_active_alerts(self, trip_id: Optional[str] = None, 
                         severity: Optional[str] = None) -> List[TripAlert]:
        """
        Get active alerts, optionally filtered by trip or severity
        """
        db = self.db()
        try:
            query = db.query(TripAlert).filter(
                TripAlert.is_active == True,
                TripAlert.expires_at > datetime.utcnow()
            )
            if trip_id:
                query = query.filter(TripAlert.trip_id == trip_id)
            if severity:
                query = query.filter(TripAlert.severity == severity)
            return query.order_by(TripAlert.detected_at.desc()).all()
        finally:
            db.close()

    def mark_alert_notified(self, alert_id: str) -> Optional[TripAlert]:
        """
        Mark an alert as notified to the user
        """
        db = self.db()
        try:
            alert = db.query(TripAlert).filter(TripAlert.alert_id == alert_id).first()
            if alert:
                alert.user_notified = True
                db.commit()
                db.refresh(alert)
            return alert
        finally:
            db.close()

    def deactivate_alert(self, alert_id: str) -> Optional[TripAlert]:
        """
        Deactivate an alert
        """
        db = self.db()
        try:
            alert = db.query(TripAlert).filter(TripAlert.alert_id == alert_id).first()
            if alert:
                alert.is_active = False
                db.commit()
                db.refresh(alert)
            return alert
        finally:
            db.close()

    def generate_weather_alerts(self, trip: TripPlan) -> List[TripAlert]:
        """
        Generate weather-based alerts for a trip
        """
        # This would integrate with weather APIs
        # For now, return placeholder alerts
        alerts = []
        
        # Check if trip is within weather alert timeframe
        days_ahead = (trip.start_date - datetime.utcnow()).days
        if days_ahead <= 7:  # Generate alerts for trips within a week
            # Placeholder weather alert generation
            pass
            
        return alerts

    def get_critical_alerts_for_notification(self) -> List[TripAlert]:
        """
        Get critical alerts that need immediate user notification
        """
        db = self.db()
        try:
            return db.query(TripAlert).filter(
                TripAlert.is_active == True,
                TripAlert.severity.in_(['CRITICAL', 'HIGH']),
                TripAlert.user_notified == False,
                TripAlert.expires_at > datetime.utcnow()
            ).all()
        finally:
            db.close()
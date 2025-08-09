# trip_saver/services/suggestion_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from flight_agent.models import SessionLocal
from trip_saver.models.trip_models import TripPlan, ProactiveSuggestion, TripOptimization
import uuid


class SuggestionService:
    """
    Service for generating and managing AI-powered proactive trip suggestions
    """
    
    def __init__(self):
        self.db = SessionLocal

    def create_suggestion(self, trip_id: str, suggestion_data: Dict[str, Any]) -> ProactiveSuggestion:
        """
        Create a new proactive suggestion
        """
        db = self.db()
        try:
            suggestion = ProactiveSuggestion(
                suggestion_id=f"suggestion_{trip_id}_{datetime.now().timestamp()}",
                trip_id=trip_id,
                suggestion_type=suggestion_data['suggestion_type'],
                title=suggestion_data['title'],
                description=suggestion_data['description'],
                confidence_score=suggestion_data.get('confidence_score', 0.0),
                potential_savings=suggestion_data.get('potential_savings', 0.0),
                time_savings_minutes=suggestion_data.get('time_savings_minutes', 0),
                expires_at=suggestion_data.get('expires_at'),
                suggestion_data=suggestion_data.get('suggestion_data', {})
            )
            
            db.add(suggestion)
            db.commit()
            db.refresh(suggestion)
            return suggestion
        finally:
            db.close()

    def get_active_suggestions(self, trip_id: Optional[str] = None, 
                             min_confidence: float = 0.5) -> List[ProactiveSuggestion]:
        """
        Get active suggestions above confidence threshold
        """
        db = self.db()
        try:
            query = db.query(ProactiveSuggestion).filter(
                ProactiveSuggestion.status == "PENDING",
                ProactiveSuggestion.confidence_score >= min_confidence,
                ProactiveSuggestion.expires_at > datetime.utcnow()
            )
            if trip_id:
                query = query.filter(ProactiveSuggestion.trip_id == trip_id)
            return query.order_by(
                ProactiveSuggestion.confidence_score.desc(),
                ProactiveSuggestion.potential_savings.desc()
            ).all()
        finally:
            db.close()

    def respond_to_suggestion(self, suggestion_id: str, status: str) -> Optional[ProactiveSuggestion]:
        """
        Record user response to a suggestion
        """
        db = self.db()
        try:
            suggestion = db.query(ProactiveSuggestion).filter(
                ProactiveSuggestion.suggestion_id == suggestion_id
            ).first()
            if suggestion:
                suggestion.status = status
                suggestion.user_response_at = datetime.utcnow()
                db.commit()
                db.refresh(suggestion)
            return suggestion
        finally:
            db.close()

    def generate_rebooking_suggestions(self, trip: TripPlan) -> List[Dict[str, Any]]:
        """
        Generate AI-powered rebooking suggestions for a trip
        """
        # This would integrate with flight search APIs and ML models
        # For now, return placeholder suggestions
        suggestions = []
        
        # Analyze current market conditions, prices, schedules
        # Generate optimized alternatives
        placeholder_suggestion = {
            'suggestion_type': 'REBOOKING',
            'title': 'Better Flight Option Available',
            'description': 'Found a direct flight that saves 2 hours and $150',
            'confidence_score': 0.85,
            'potential_savings': 150.0,
            'time_savings_minutes': 120,
            'expires_at': datetime.utcnow() + timedelta(hours=24),
            'suggestion_data': {
                'new_flight_details': {
                    'airline': 'Delta',
                    'flight_number': 'DL1234',
                    'departure_time': '14:30',
                    'arrival_time': '18:45',
                    'price': 450
                },
                'current_flight_details': {
                    'price': 600,
                    'total_time': '6h 15m'
                }
            }
        }
        suggestions.append(placeholder_suggestion)
        
        return suggestions

    def generate_optimization_suggestions(self, trip: TripPlan) -> List[Dict[str, Any]]:
        """
        Generate suggestions for trip optimization (cost, time, comfort)
        """
        suggestions = []
        
        # Analyze trip for optimization opportunities
        # Check for price drops, schedule improvements, etc.
        
        return suggestions

    def track_optimization_result(self, trip_id: str, optimization_data: Dict[str, Any]) -> TripOptimization:
        """
        Track the result of an applied optimization
        """
        db = self.db()
        try:
            optimization = TripOptimization(
                optimization_id=f"opt_{trip_id}_{datetime.now().timestamp()}",
                trip_id=trip_id,
                optimization_type=optimization_data['optimization_type'],
                original_value=optimization_data.get('original_value'),
                optimized_value=optimization_data.get('optimized_value'),
                improvement_percentage=optimization_data.get('improvement_percentage'),
                optimization_method=optimization_data.get('optimization_method'),
                metrics=optimization_data.get('metrics', {})
            )
            
            db.add(optimization)
            db.commit()
            db.refresh(optimization)
            return optimization
        finally:
            db.close()

    def get_high_value_suggestions(self, min_savings: float = 50.0) -> List[ProactiveSuggestion]:
        """
        Get suggestions with high potential value
        """
        db = self.db()
        try:
            return db.query(ProactiveSuggestion).filter(
                ProactiveSuggestion.status == "PENDING",
                ProactiveSuggestion.potential_savings >= min_savings,
                ProactiveSuggestion.expires_at > datetime.utcnow()
            ).order_by(ProactiveSuggestion.potential_savings.desc()).all()
        finally:
            db.close()
"""
Prediction Tools for Flight Disruption Analysis
Integration tools for the PredictionEngine service

This module provides:
- Integration tools for prediction engine
- Booking delay prediction functions
- Model performance monitoring
- Threshold management utilities
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from ..services.prediction_engine import (
    PredictionEngine, 
    DelayPrediction, 
    PredictionModel,
    predict_booking_delay
)
from ..models import SessionLocal, Booking, get_upcoming_bookings

logger = logging.getLogger(__name__)


class PredictionTools:
    """Tools for integrating prediction engine with flight monitoring"""
    
    def __init__(self):
        self.engine = PredictionEngine()
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize prediction engine"""
        if not self._initialized:
            self._initialized = await self.engine.initialize()
        return self._initialized
    
    async def predict_booking_delays(self, booking_ids: List[str]) -> Dict[str, DelayPrediction]:
        """Predict delays for multiple bookings"""
        if not await self.initialize():
            logger.error("Failed to initialize prediction engine")
            return {}
        
        try:
            requests = []
            db = SessionLocal()
            
            try:
                for booking_id in booking_ids:
                    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
                    if booking:
                        input_data = {
                            'booking_id': booking_id,
                            'origin': booking.origin,
                            'destination': booking.destination,
                            'airline': booking.airline,
                            'departure_time': booking.departure_date,
                            'booking_class': booking.booking_class,
                            'fare_amount': booking.fare_amount
                        }
                        requests.append((booking_id, input_data))
                    else:
                        logger.warning(f"Booking {booking_id} not found")
                
                return await self.engine.predict_multiple(requests)
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error predicting booking delays: {e}")
            return {}
    
    async def analyze_high_risk_bookings(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Analyze bookings with high delay risk"""
        if not await self.initialize():
            return []
        
        try:
            # Get upcoming bookings
            upcoming_bookings = get_upcoming_bookings(user_id)
            if not upcoming_bookings:
                return []
            
            booking_ids = [b.booking_id for b in upcoming_bookings]
            predictions = await self.predict_booking_delays(booking_ids)
            
            # Filter high-risk bookings
            high_risk_analysis = []
            
            for booking_id, prediction in predictions.items():
                if prediction.threshold_exceeded or prediction.delay_probability > 0.4:
                    booking = next(b for b in upcoming_bookings if b.booking_id == booking_id)
                    
                    analysis = {
                        'booking_id': booking_id,
                        'route': f"{booking.origin} → {booking.destination}",
                        'airline': booking.airline,
                        'departure_date': booking.departure_date.isoformat(),
                        'delay_probability': prediction.delay_probability,
                        'expected_delay_minutes': prediction.expected_delay_minutes,
                        'confidence_level': prediction.confidence_level.value,
                        'risk_score': prediction.risk_score,
                        'contributing_factors': prediction.contributing_factors,
                        'recommendations': self._generate_recommendations(prediction)
                    }
                    high_risk_analysis.append(analysis)
            
            # Sort by risk score
            high_risk_analysis.sort(key=lambda x: x['risk_score'], reverse=True)
            
            return high_risk_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing high-risk bookings: {e}")
            return []
    
    async def generate_prediction_report(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate comprehensive prediction report"""
        if not await self.initialize():
            return {'error': 'Failed to initialize prediction engine'}
        
        try:
            # Get upcoming bookings
            upcoming_bookings = get_upcoming_bookings(user_id)
            
            if not upcoming_bookings:
                return {
                    'summary': 'No upcoming bookings found',
                    'total_bookings': 0,
                    'predictions': []
                }
            
            booking_ids = [b.booking_id for b in upcoming_bookings]
            predictions = await self.predict_booking_delays(booking_ids)
            
            # Calculate summary statistics
            total_bookings = len(upcoming_bookings)
            predicted_bookings = len(predictions)
            high_risk_count = sum(1 for p in predictions.values() if p.threshold_exceeded)
            avg_delay_probability = sum(p.delay_probability for p in predictions.values()) / predicted_bookings if predicted_bookings > 0 else 0
            
            # Categorize by risk level
            risk_categories = {
                'high': [],
                'medium': [],
                'low': []
            }
            
            for booking_id, prediction in predictions.items():
                booking = next(b for b in upcoming_bookings if b.booking_id == booking_id)
                
                booking_info = {
                    'booking_id': booking_id,
                    'route': f"{booking.origin} → {booking.destination}",
                    'airline': booking.airline,
                    'departure_date': booking.departure_date.isoformat(),
                    'delay_probability': prediction.delay_probability,
                    'expected_delay_minutes': prediction.expected_delay_minutes,
                    'confidence_level': prediction.confidence_level.value
                }
                
                if prediction.risk_score >= 0.6:
                    risk_categories['high'].append(booking_info)
                elif prediction.risk_score >= 0.3:
                    risk_categories['medium'].append(booking_info)
                else:
                    risk_categories['low'].append(booking_info)
            
            # Generate recommendations
            recommendations = []
            if high_risk_count > 0:
                recommendations.append(f"🚨 {high_risk_count} booking(s) have high delay risk - consider backup plans")
            if avg_delay_probability > 0.3:
                recommendations.append("📱 Enable real-time notifications for flight status updates")
            if len(risk_categories['high']) > 0:
                recommendations.append("🔄 Consider rebooking high-risk flights if flexibility allows")
            
            return {
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'summary': {
                    'total_bookings': total_bookings,
                    'predicted_bookings': predicted_bookings,
                    'high_risk_bookings': high_risk_count,
                    'average_delay_probability': round(avg_delay_probability, 3)
                },
                'risk_categories': risk_categories,
                'recommendations': recommendations,
                'model_performance': self.engine.get_model_performance()
            }
            
        except Exception as e:
            logger.error(f"Error generating prediction report: {e}")
            return {'error': str(e)}
    
    async def update_prediction_thresholds(self, confidence_threshold: Optional[float] = None,
                                         delay_probability_threshold: Optional[float] = None) -> Dict[str, bool]:
        """Update prediction engine thresholds"""
        if not await self.initialize():
            return {'error': 'Failed to initialize prediction engine'}
        
        results = {}
        
        if confidence_threshold is not None:
            results['confidence_threshold'] = await self.engine.update_threshold('confidence', confidence_threshold)
        
        if delay_probability_threshold is not None:
            results['delay_probability_threshold'] = await self.engine.update_threshold('delay_probability', delay_probability_threshold)
        
        return results
    
    async def retrain_prediction_models(self, model_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Retrain prediction models with latest data"""
        if not await self.initialize():
            return {'error': 'Failed to initialize prediction engine'}
        
        try:
            # Convert string model names to enum if provided
            model_enums = None
            if model_types:
                model_enums = []
                for model_name in model_types:
                    try:
                        model_enum = PredictionModel(model_name)
                        model_enums.append(model_enum)
                    except ValueError:
                        logger.warning(f"Invalid model type: {model_name}")
            
            results = await self.engine.retrain_models(model_enums)
            
            return {
                'retrained_at': datetime.now(timezone.utc).isoformat(),
                'results': results,
                'successful_models': [model for model, success in results.items() if success],
                'failed_models': [model for model, success in results.items() if not success]
            }
            
        except Exception as e:
            logger.error(f"Error retraining models: {e}")
            return {'error': str(e)}
    
    def _generate_recommendations(self, prediction: DelayPrediction) -> List[str]:
        """Generate actionable recommendations based on prediction"""
        recommendations = []
        
        if prediction.delay_probability > 0.6:
            recommendations.append("🔴 HIGH RISK: Consider alternative flights if possible")
        elif prediction.delay_probability > 0.4:
            recommendations.append("🟡 ELEVATED RISK: Have backup travel plans ready")
        
        if prediction.expected_delay_minutes > 60:
            recommendations.append("⏰ Significant delays expected - plan for extended travel time")
        elif prediction.expected_delay_minutes > 30:
            recommendations.append("⏱️ Minor delays possible - allow extra time")
        
        if prediction.confidence_level.value in ['low', 'very_low']:
            recommendations.append("❓ Prediction uncertainty is high - monitor closely")
        
        # Route-specific recommendations
        if prediction.route_pattern_data:
            pattern = prediction.route_pattern_data
            if 'weather_sensitive' in pattern.recurring_patterns:
                recommendations.append("🌦️ Weather-sensitive route - check weather forecasts")
            if 'morning_rush' in pattern.recurring_patterns or 'evening_rush' in pattern.recurring_patterns:
                recommendations.append("🚗 Peak traffic hours - expect congestion delays")
        
        return recommendations


# Async utility functions

async def predict_user_bookings(user_id: str) -> Dict[str, Any]:
    """Predict delays for all bookings of a specific user"""
    tools = PredictionTools()
    return await tools.generate_prediction_report(user_id)


async def analyze_route_patterns(origin: str, destination: str, days_ahead: int = 7) -> Dict[str, Any]:
    """Analyze delay patterns for a specific route"""
    tools = PredictionTools()
    
    if not await tools.initialize():
        return {'error': 'Failed to initialize prediction engine'}
    
    try:
        # Get bookings for the route in the next N days
        db = SessionLocal()
        try:
            cutoff_date = datetime.now(timezone.utc) + timedelta(days=days_ahead)
            route_bookings = db.query(Booking).filter(
                Booking.origin == origin,
                Booking.destination == destination,
                Booking.departure_date <= cutoff_date,
                Booking.departure_date > datetime.now(timezone.utc)
            ).all()
            
            if not route_bookings:
                return {
                    'route': f"{origin} → {destination}",
                    'message': 'No upcoming bookings found for this route',
                    'bookings_analyzed': 0
                }
            
            # Get predictions for all route bookings
            booking_ids = [b.booking_id for b in route_bookings]
            predictions = await tools.predict_booking_delays(booking_ids)
            
            # Analyze patterns
            delay_probabilities = [p.delay_probability for p in predictions.values()]
            expected_delays = [p.expected_delay_minutes for p in predictions.values()]
            
            avg_delay_probability = sum(delay_probabilities) / len(delay_probabilities) if delay_probabilities else 0
            avg_expected_delay = sum(expected_delays) / len(expected_delays) if expected_delays else 0
            
            high_risk_count = sum(1 for p in predictions.values() if p.threshold_exceeded)
            
            return {
                'route': f"{origin} → {destination}",
                'analysis_period': f"Next {days_ahead} days",
                'bookings_analyzed': len(route_bookings),
                'average_delay_probability': round(avg_delay_probability, 3),
                'average_expected_delay_minutes': round(avg_expected_delay, 1),
                'high_risk_bookings': high_risk_count,
                'risk_assessment': 'High' if avg_delay_probability > 0.4 else 'Medium' if avg_delay_probability > 0.2 else 'Low',
                'recommendations': [
                    f"This route shows {'high' if avg_delay_probability > 0.4 else 'moderate' if avg_delay_probability > 0.2 else 'low'} delay risk",
                    f"Expected average delay: {avg_expected_delay:.1f} minutes",
                    "Monitor flight status closely" if high_risk_count > 0 else "Route appears stable"
                ]
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error analyzing route patterns: {e}")
        return {'error': str(e)}


# CLI function for testing
async def main():
    """CLI entry point for testing prediction tools"""
    import sys
    
    print("🔮 Flight Delay Prediction Tools")
    print("=" * 40)
    
    tools = PredictionTools()
    
    if not await tools.initialize():
        print("❌ Failed to initialize prediction engine")
        return
    
    print("✅ Prediction engine initialized")
    
    # Test threshold management
    print("\n📊 Testing Threshold Management:")
    threshold_results = await tools.update_prediction_thresholds(
        confidence_threshold=0.6,
        delay_probability_threshold=0.25
    )
    for threshold_type, success in threshold_results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {threshold_type}: {'Updated' if success else 'Failed'}")
    
    # Generate sample report
    print("\n📈 Generating Prediction Report:")
    report = await tools.generate_prediction_report()
    
    if 'error' in report:
        print(f"  ❌ Error: {report['error']}")
    else:
        print(f"  📋 Report generated successfully")
        print(f"  📊 Summary: {report['summary']}")
        if 'recommendations' in report and report['recommendations']:
            print(f"  💡 Recommendations:")
            for rec in report['recommendations'][:3]:  # Show first 3
                print(f"    • {rec}")
    
    # Test high-risk analysis
    print("\n🚨 Analyzing High-Risk Bookings:")
    high_risk = await tools.analyze_high_risk_bookings()
    print(f"  Found {len(high_risk)} high-risk bookings")
    
    if len(sys.argv) > 1:
        # Test specific booking prediction
        booking_id = sys.argv[1]
        print(f"\n🎯 Predicting delay for booking {booking_id}:")
        prediction = await predict_booking_delay(booking_id)
        
        if prediction:
            print(f"  Route: {prediction.route_id}")
            print(f"  Delay Probability: {prediction.delay_probability:.1%}")
            print(f"  Expected Delay: {prediction.expected_delay_minutes:.1f} minutes")
            print(f"  Confidence: {prediction.confidence_level.value}")
            print(f"  Risk Score: {prediction.risk_score:.2f}")
        else:
            print(f"  ❌ Could not predict delay for {booking_id}")
    
    print("\n✅ Prediction tools testing completed")


if __name__ == "__main__":
    asyncio.run(main())
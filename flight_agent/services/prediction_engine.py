"""
Prediction Engine for Flight Disruption Analysis
Task 3: Create prediction engine for disruption analysis

This module implements:
- ML model interface for predictive analytics
- Pattern recognition for route-specific delays
- Confidence scoring and threshold management
- Addresses requirements REQ-6.1, REQ-6.4, REQ-6.5
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
from collections import defaultdict, deque
import statistics
from ..models import SessionLocal, Booking, DisruptionEvent, Flight
from ..providers.interfaces import FlightStatusData

logger = logging.getLogger(__name__)


class PredictionModel(Enum):
    """Available ML models for predictions"""
    HISTORICAL_PATTERNS = "historical_patterns"
    ROUTE_SPECIFIC = "route_specific" 
    WEATHER_CORRELATION = "weather_correlation"
    TIME_SERIES = "time_series"
    ENSEMBLE = "ensemble"


class PredictionConfidence(Enum):
    """Confidence levels for predictions"""
    VERY_HIGH = "very_high"  # 90%+ confidence
    HIGH = "high"           # 70-89% confidence
    MEDIUM = "medium"       # 50-69% confidence
    LOW = "low"            # 30-49% confidence
    VERY_LOW = "very_low"  # <30% confidence


@dataclass
class RoutePattern:
    """Route-specific delay pattern data"""
    route_id: str  # e.g., "JFK-LAX"
    origin: str
    destination: str
    airline: str
    
    # Pattern metrics
    average_delay_minutes: float
    delay_probability: float
    peak_delay_hours: List[int]  # Hours with highest delays (0-23)
    seasonal_factors: Dict[int, float]  # Month -> multiplier
    weather_sensitivity: float  # 0.0-1.0
    
    # Statistical measures
    delay_variance: float
    sample_size: int
    confidence_score: float
    last_updated: datetime
    
    # Pattern features
    recurring_patterns: List[str]  # ["monday_morning", "weather_delays"]
    disruption_types: Dict[str, float]  # type -> frequency


@dataclass
class DelayPrediction:
    """Individual delay prediction result"""
    booking_id: str
    route_id: str
    prediction_model: PredictionModel
    
    # Prediction results
    delay_probability: float  # 0.0-1.0
    expected_delay_minutes: float
    confidence_level: PredictionConfidence
    confidence_score: float  # 0.0-1.0
    
    # Prediction details
    contributing_factors: List[str]
    threshold_exceeded: bool
    risk_score: float  # Combined risk assessment
    
    # Model metadata
    model_version: str
    prediction_timestamp: datetime
    valid_until: datetime
    
    # Additional context
    historical_context: Dict[str, Any]
    route_pattern_data: Optional[RoutePattern]


class MLModelInterface:
    """
    REQ-6.1: Machine Learning model interface for predictive analytics
    
    Abstract interface for ML models to ensure consistent prediction capabilities
    across different model implementations.
    """
    
    def __init__(self, model_name: str, version: str = "1.0"):
        self.model_name = model_name
        self.version = version
        self.is_trained = False
        self.last_training_date: Optional[datetime] = None
        self.training_data_size = 0
        self.performance_metrics = {}
        
    async def train(self, training_data: List[Dict[str, Any]]) -> bool:
        """Train the model with historical data"""
        raise NotImplementedError("Subclasses must implement train method")
    
    async def predict(self, input_data: Dict[str, Any]) -> DelayPrediction:
        """Make a prediction based on input data"""
        raise NotImplementedError("Subclasses must implement predict method")
    
    async def update_model(self, new_data: List[Dict[str, Any]]) -> bool:
        """Update model with new training data"""
        raise NotImplementedError("Subclasses must implement update_model method")
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores"""
        return {}
    
    def get_model_metrics(self) -> Dict[str, Any]:
        """Get model performance metrics"""
        return {
            'model_name': self.model_name,
            'version': self.version,
            'is_trained': self.is_trained,
            'training_data_size': self.training_data_size,
            'last_training_date': self.last_training_date.isoformat() if self.last_training_date else None,
            'performance_metrics': self.performance_metrics
        }


class RouteSpecificModel(MLModelInterface):
    """
    REQ-6.4: Route-specific delay pattern recognition
    
    ML model specialized in analyzing and predicting delays for specific routes
    based on historical patterns, time factors, and route characteristics.
    """
    
    def __init__(self):
        super().__init__("RouteSpecificModel", "1.0")
        self.route_patterns: Dict[str, RoutePattern] = {}
        self.pattern_cache = {}
        self.min_samples_for_pattern = 10
        
    async def train(self, training_data: List[Dict[str, Any]]) -> bool:
        """Train route-specific patterns from historical data"""
        try:
            logger.info(f"Training RouteSpecificModel with {len(training_data)} samples")
            
            # Group data by routes
            route_data = defaultdict(list)
            for record in training_data:
                route_id = f"{record['origin']}-{record['destination']}-{record.get('airline', 'ALL')}"
                route_data[route_id].append(record)
            
            patterns_created = 0
            for route_id, records in route_data.items():
                if len(records) >= self.min_samples_for_pattern:
                    pattern = await self._create_route_pattern(route_id, records)
                    if pattern:
                        self.route_patterns[route_id] = pattern
                        patterns_created += 1
            
            self.is_trained = True
            self.last_training_date = datetime.now(timezone.utc)
            self.training_data_size = len(training_data)
            self.performance_metrics['patterns_created'] = patterns_created
            self.performance_metrics['routes_analyzed'] = len(route_data)
            
            logger.info(f"Created {patterns_created} route patterns from {len(route_data)} routes")
            return True
            
        except Exception as e:
            logger.error(f"Error training RouteSpecificModel: {e}")
            return False
    
    async def predict(self, input_data: Dict[str, Any]) -> DelayPrediction:
        """Predict delays for a specific route"""
        try:
            route_id = f"{input_data['origin']}-{input_data['destination']}-{input_data.get('airline', 'ALL')}"
            booking_id = input_data.get('booking_id', 'unknown')
            
            # Get route pattern
            pattern = self.route_patterns.get(route_id)
            if not pattern:
                # Fallback to general route (without airline)
                general_route_id = f"{input_data['origin']}-{input_data['destination']}-ALL"
                pattern = self.route_patterns.get(general_route_id)
            
            if not pattern:
                # No pattern available, return low-confidence baseline
                return self._create_baseline_prediction(booking_id, route_id, input_data)
            
            # Calculate prediction based on pattern
            delay_probability = await self._calculate_route_delay_probability(pattern, input_data)
            expected_delay = await self._calculate_expected_delay(pattern, input_data)
            confidence_score = await self._calculate_confidence_score(pattern, input_data)
            
            # Determine confidence level
            confidence_level = self._get_confidence_level(confidence_score)
            
            # Get contributing factors
            contributing_factors = await self._identify_contributing_factors(pattern, input_data)
            
            # Calculate risk score
            risk_score = (delay_probability * 0.6) + (expected_delay / 180.0 * 0.4)  # 3 hour max delay
            
            return DelayPrediction(
                booking_id=booking_id,
                route_id=route_id,
                prediction_model=PredictionModel.ROUTE_SPECIFIC,
                delay_probability=delay_probability,
                expected_delay_minutes=expected_delay,
                confidence_level=confidence_level,
                confidence_score=confidence_score,
                contributing_factors=contributing_factors,
                threshold_exceeded=delay_probability > 0.3,  # 30% threshold
                risk_score=min(risk_score, 1.0),
                model_version=self.version,
                prediction_timestamp=datetime.now(timezone.utc),
                valid_until=datetime.now(timezone.utc) + timedelta(hours=2),
                historical_context={
                    'pattern_sample_size': pattern.sample_size,
                    'pattern_confidence': pattern.confidence_score,
                    'average_route_delay': pattern.average_delay_minutes
                },
                route_pattern_data=pattern
            )
            
        except Exception as e:
            logger.error(f"Error predicting for route {route_id}: {e}")
            return self._create_error_prediction(booking_id, route_id, str(e))
    
    async def _create_route_pattern(self, route_id: str, records: List[Dict[str, Any]]) -> Optional[RoutePattern]:
        """Create a route pattern from historical records"""
        try:
            if not records:
                return None
            
            # Extract route components
            parts = route_id.split('-')
            origin, destination, airline = parts[0], parts[1], parts[2] if len(parts) > 2 else "ALL"
            
            # Calculate delay statistics
            delays = [r.get('delay_minutes', 0) for r in records]
            disrupted_count = sum(1 for r in records if r.get('is_disrupted', False))
            
            average_delay = statistics.mean(delays) if delays else 0.0
            delay_variance = statistics.variance(delays) if len(delays) > 1 else 0.0
            delay_probability = disrupted_count / len(records) if records else 0.0
            
            # Analyze peak delay hours
            peak_hours = defaultdict(int)
            for record in records:
                if 'departure_time' in record:
                    hour = record['departure_time'].hour if isinstance(record['departure_time'], datetime) else 12
                    if record.get('delay_minutes', 0) > 30:  # Only count significant delays
                        peak_hours[hour] += 1
            
            top_peak_hours = sorted(peak_hours.keys(), key=lambda h: peak_hours[h], reverse=True)[:3]
            
            # Calculate seasonal factors
            seasonal_factors = {}
            monthly_delays = defaultdict(list)
            for record in records:
                if 'departure_time' in record:
                    month = record['departure_time'].month if isinstance(record['departure_time'], datetime) else 1
                    monthly_delays[month].append(record.get('delay_minutes', 0))
            
            overall_avg = average_delay if average_delay > 0 else 1.0
            for month in range(1, 13):
                if month in monthly_delays:
                    month_avg = statistics.mean(monthly_delays[month])
                    seasonal_factors[month] = month_avg / overall_avg
                else:
                    seasonal_factors[month] = 1.0
            
            # Calculate weather sensitivity (simplified)
            weather_related = sum(1 for r in records if 'weather' in r.get('disruption_reason', '').lower())
            weather_sensitivity = weather_related / len(records) if records else 0.0
            
            # Calculate confidence score based on sample size and consistency
            confidence_score = min(len(records) / 100.0, 1.0) * 0.7  # Sample size factor
            if delay_variance > 0:
                consistency_factor = 1.0 / (1.0 + delay_variance / 1000.0)  # Penalize high variance
                confidence_score += consistency_factor * 0.3
            
            # Identify disruption types
            disruption_types = defaultdict(int)
            for record in records:
                dtype = record.get('disruption_type', 'unknown')
                if record.get('is_disrupted', False):
                    disruption_types[dtype] += 1
            
            total_disruptions = sum(disruption_types.values())
            disruption_frequencies = {
                dtype: count / total_disruptions 
                for dtype, count in disruption_types.items()
            } if total_disruptions > 0 else {}
            
            # Identify recurring patterns
            recurring_patterns = []
            if len(top_peak_hours) > 0:
                if any(h in [7, 8, 9] for h in top_peak_hours):
                    recurring_patterns.append("morning_rush")
                if any(h in [17, 18, 19] for h in top_peak_hours):
                    recurring_patterns.append("evening_rush")
            if weather_sensitivity > 0.3:
                recurring_patterns.append("weather_sensitive")
            if delay_probability > 0.4:
                recurring_patterns.append("high_delay_route")
            
            return RoutePattern(
                route_id=route_id,
                origin=origin,
                destination=destination,
                airline=airline,
                average_delay_minutes=average_delay,
                delay_probability=delay_probability,
                peak_delay_hours=top_peak_hours,
                seasonal_factors=seasonal_factors,
                weather_sensitivity=weather_sensitivity,
                delay_variance=delay_variance,
                sample_size=len(records),
                confidence_score=confidence_score,
                last_updated=datetime.now(timezone.utc),
                recurring_patterns=recurring_patterns,
                disruption_types=disruption_frequencies
            )
            
        except Exception as e:
            logger.error(f"Error creating route pattern for {route_id}: {e}")
            return None
    
    async def _calculate_route_delay_probability(self, pattern: RoutePattern, input_data: Dict[str, Any]) -> float:
        """Calculate delay probability based on route pattern and current conditions"""
        base_probability = pattern.delay_probability
        
        # Apply time-of-day factor
        departure_time = input_data.get('departure_time')
        if departure_time:
            hour = departure_time.hour if isinstance(departure_time, datetime) else 12
            if hour in pattern.peak_delay_hours:
                base_probability *= 1.3  # Increase probability during peak hours
        
        # Apply seasonal factor
        if departure_time:
            month = departure_time.month if isinstance(departure_time, datetime) else 1
            seasonal_multiplier = pattern.seasonal_factors.get(month, 1.0)
            base_probability *= seasonal_multiplier
        
        # Weather factor (simplified)
        weather_conditions = input_data.get('weather_conditions', {})
        if weather_conditions and pattern.weather_sensitivity > 0.2:
            weather_risk = weather_conditions.get('risk_score', 0.0)
            base_probability += weather_risk * pattern.weather_sensitivity * 0.3
        
        return min(base_probability, 1.0)
    
    async def _calculate_expected_delay(self, pattern: RoutePattern, input_data: Dict[str, Any]) -> float:
        """Calculate expected delay minutes based on pattern"""
        base_delay = pattern.average_delay_minutes
        
        # Apply seasonal adjustment
        departure_time = input_data.get('departure_time')
        if departure_time:
            month = departure_time.month if isinstance(departure_time, datetime) else 1
            seasonal_multiplier = pattern.seasonal_factors.get(month, 1.0)
            base_delay *= seasonal_multiplier
        
        return max(base_delay, 0.0)
    
    async def _calculate_confidence_score(self, pattern: RoutePattern, input_data: Dict[str, Any]) -> float:
        """Calculate prediction confidence score"""
        base_confidence = pattern.confidence_score
        
        # Adjust based on how recent the pattern data is
        days_old = (datetime.now(timezone.utc) - pattern.last_updated).days
        recency_factor = max(0.5, 1.0 - days_old / 365.0)  # Decay over a year
        
        # Adjust based on sample size
        sample_factor = min(pattern.sample_size / 50.0, 1.0)  # Full confidence at 50+ samples
        
        return base_confidence * recency_factor * sample_factor
    
    async def _identify_contributing_factors(self, pattern: RoutePattern, input_data: Dict[str, Any]) -> List[str]:
        """Identify factors contributing to the delay prediction"""
        factors = []
        
        # Route-specific factors
        if pattern.delay_probability > 0.3:
            factors.append(f"High-delay route ({pattern.delay_probability:.1%} historical delay rate)")
        
        # Time factors
        departure_time = input_data.get('departure_time')
        if departure_time:
            hour = departure_time.hour if isinstance(departure_time, datetime) else 12
            if hour in pattern.peak_delay_hours:
                factors.append(f"Peak delay hour ({hour}:00)")
            
            month = departure_time.month if isinstance(departure_time, datetime) else 1
            seasonal_factor = pattern.seasonal_factors.get(month, 1.0)
            if seasonal_factor > 1.2:
                factors.append(f"High-delay season (month {month})")
        
        # Weather factors
        if pattern.weather_sensitivity > 0.3:
            factors.append("Weather-sensitive route")
        
        # Pattern factors
        for recurring_pattern in pattern.recurring_patterns:
            factors.append(f"Pattern: {recurring_pattern}")
        
        return factors
    
    def _create_baseline_prediction(self, booking_id: str, route_id: str, input_data: Dict[str, Any]) -> DelayPrediction:
        """Create a baseline prediction when no pattern is available"""
        return DelayPrediction(
            booking_id=booking_id,
            route_id=route_id,
            prediction_model=PredictionModel.ROUTE_SPECIFIC,
            delay_probability=0.15,  # Industry average
            expected_delay_minutes=20.0,  # Conservative estimate
            confidence_level=PredictionConfidence.LOW,
            confidence_score=0.2,
            contributing_factors=["No route-specific pattern available"],
            threshold_exceeded=False,
            risk_score=0.15,
            model_version=self.version,
            prediction_timestamp=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
            historical_context={'note': 'baseline_prediction'},
            route_pattern_data=None
        )
    
    def _create_error_prediction(self, booking_id: str, route_id: str, error_msg: str) -> DelayPrediction:
        """Create an error prediction when prediction fails"""
        return DelayPrediction(
            booking_id=booking_id,
            route_id=route_id,
            prediction_model=PredictionModel.ROUTE_SPECIFIC,
            delay_probability=0.1,
            expected_delay_minutes=0.0,
            confidence_level=PredictionConfidence.VERY_LOW,
            confidence_score=0.1,
            contributing_factors=[f"Prediction error: {error_msg}"],
            threshold_exceeded=False,
            risk_score=0.1,
            model_version=self.version,
            prediction_timestamp=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(minutes=30),
            historical_context={'error': error_msg},
            route_pattern_data=None
        )
    
    def _get_confidence_level(self, confidence_score: float) -> PredictionConfidence:
        """Convert confidence score to confidence level"""
        if confidence_score >= 0.9:
            return PredictionConfidence.VERY_HIGH
        elif confidence_score >= 0.7:
            return PredictionConfidence.HIGH
        elif confidence_score >= 0.5:
            return PredictionConfidence.MEDIUM
        elif confidence_score >= 0.3:
            return PredictionConfidence.LOW
        else:
            return PredictionConfidence.VERY_LOW


class PredictionEngine:
    """
    REQ-6.5: Main Prediction Engine with confidence scoring and threshold management
    
    Orchestrates multiple ML models to provide comprehensive flight delay predictions
    with confidence scoring, threshold management, and model performance tracking.
    """
    
    def __init__(self):
        self.models: Dict[PredictionModel, MLModelInterface] = {}
        self.confidence_threshold = 0.5  # Minimum confidence for predictions
        self.delay_probability_threshold = 0.3  # 30% threshold for high-risk alerts
        self.prediction_cache = {}
        self.cache_ttl_minutes = 30
        
        # Performance tracking
        self.prediction_history = deque(maxlen=1000)
        self.model_performance = defaultdict(dict)
        
        # Initialize models
        self._initialize_models()
        
        logger.info("PredictionEngine initialized with confidence and threshold management")
    
    def _initialize_models(self):
        """Initialize available prediction models"""
        # Route-specific model (primary)
        self.models[PredictionModel.ROUTE_SPECIFIC] = RouteSpecificModel()
        
        # TODO: Add other models as they're implemented
        # self.models[PredictionModel.WEATHER_CORRELATION] = WeatherCorrelationModel()
        # self.models[PredictionModel.TIME_SERIES] = TimeSeriesModel()
        # self.models[PredictionModel.ENSEMBLE] = EnsembleModel()
    
    async def initialize(self) -> bool:
        """Initialize the prediction engine with training data"""
        try:
            logger.info("Initializing PredictionEngine with historical data...")
            
            # Load historical data for training
            training_data = await self._load_training_data()
            if not training_data:
                logger.warning("No training data available - using default models")
                return True
            
            # Train all models
            successful_models = 0
            for model_type, model in self.models.items():
                try:
                    if await model.train(training_data):
                        successful_models += 1
                        logger.info(f"Successfully trained {model_type.value} model")
                    else:
                        logger.warning(f"Failed to train {model_type.value} model")
                except Exception as e:
                    logger.error(f"Error training {model_type.value} model: {e}")
            
            logger.info(f"PredictionEngine initialized with {successful_models}/{len(self.models)} models")
            return successful_models > 0
            
        except Exception as e:
            logger.error(f"Error initializing PredictionEngine: {e}")
            return False
    
    async def predict_delay(self, booking_id: str, input_data: Dict[str, Any], 
                          model_preference: Optional[PredictionModel] = None) -> DelayPrediction:
        """
        Make a delay prediction using the specified or best available model
        
        Args:
            booking_id: Booking identifier
            input_data: Flight and context data for prediction
            model_preference: Preferred model to use (optional)
            
        Returns:
            DelayPrediction with confidence scoring and threshold analysis
        """
        try:
            # Check cache first
            cache_key = self._generate_cache_key(booking_id, input_data)
            cached_prediction = self._get_cached_prediction(cache_key)
            if cached_prediction:
                logger.debug(f"Returning cached prediction for {booking_id}")
                return cached_prediction
            
            # Select model
            model = await self._select_best_model(input_data, model_preference)
            if not model:
                logger.error("No suitable model available for prediction")
                return self._create_fallback_prediction(booking_id, input_data)
            
            # Make prediction
            prediction = await model.predict(input_data)
            
            # Apply confidence threshold filtering
            if prediction.confidence_score < self.confidence_threshold:
                logger.warning(f"Prediction confidence ({prediction.confidence_score:.2f}) below threshold ({self.confidence_threshold})")
                prediction.contributing_factors.append(f"Low confidence (< {self.confidence_threshold})")
            
            # Check delay probability threshold
            if prediction.delay_probability >= self.delay_probability_threshold:
                prediction.threshold_exceeded = True
                prediction.contributing_factors.append(f"Delay probability ({prediction.delay_probability:.1%}) exceeds threshold ({self.delay_probability_threshold:.1%})")
            
            # Cache the prediction
            self._cache_prediction(cache_key, prediction)
            
            # Track prediction for performance analysis
            self._track_prediction(prediction)
            
            logger.info(f"Generated prediction for {booking_id}: {prediction.delay_probability:.1%} probability, {prediction.confidence_level.value} confidence")
            return prediction
            
        except Exception as e:
            logger.error(f"Error predicting delay for {booking_id}: {e}")
            return self._create_error_prediction(booking_id, str(e), input_data)
    
    async def predict_multiple(self, requests: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, DelayPrediction]:
        """Make predictions for multiple bookings efficiently"""
        try:
            logger.info(f"Making predictions for {len(requests)} bookings")
            
            results = {}
            tasks = []
            
            for booking_id, input_data in requests:
                task = asyncio.create_task(self.predict_delay(booking_id, input_data))
                tasks.append((booking_id, task))
            
            # Wait for all predictions to complete
            for booking_id, task in tasks:
                try:
                    prediction = await task
                    results[booking_id] = prediction
                except Exception as e:
                    logger.error(f"Error predicting for {booking_id}: {e}")
                    results[booking_id] = self._create_error_prediction(booking_id, str(e), {})
            
            logger.info(f"Completed {len(results)} predictions")
            return results
            
        except Exception as e:
            logger.error(f"Error in batch prediction: {e}")
            return {}
    
    async def update_threshold(self, threshold_type: str, value: float) -> bool:
        """Update prediction thresholds"""
        try:
            if threshold_type == "confidence":
                if 0.0 <= value <= 1.0:
                    self.confidence_threshold = value
                    logger.info(f"Updated confidence threshold to {value}")
                    return True
                else:
                    logger.error("Confidence threshold must be between 0.0 and 1.0")
                    return False
                    
            elif threshold_type == "delay_probability":
                if 0.0 <= value <= 1.0:
                    self.delay_probability_threshold = value
                    logger.info(f"Updated delay probability threshold to {value}")
                    return True
                else:
                    logger.error("Delay probability threshold must be between 0.0 and 1.0")
                    return False
            else:
                logger.error(f"Unknown threshold type: {threshold_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating threshold {threshold_type}: {e}")
            return False
    
    def get_model_performance(self) -> Dict[str, Any]:
        """Get performance metrics for all models"""
        try:
            performance_summary = {
                'engine_config': {
                    'confidence_threshold': self.confidence_threshold,
                    'delay_probability_threshold': self.delay_probability_threshold,
                    'cache_ttl_minutes': self.cache_ttl_minutes
                },
                'models': {},
                'prediction_stats': {
                    'total_predictions': len(self.prediction_history),
                    'recent_predictions': len([p for p in self.prediction_history 
                                             if (datetime.now(timezone.utc) - p['timestamp']).total_seconds() < 3600])
                }
            }
            
            for model_type, model in self.models.items():
                performance_summary['models'][model_type.value] = model.get_model_metrics()
            
            return performance_summary
            
        except Exception as e:
            logger.error(f"Error getting model performance: {e}")
            return {'error': str(e)}
    
    async def retrain_models(self, model_types: Optional[List[PredictionModel]] = None) -> Dict[str, bool]:
        """Retrain specified models or all models"""
        try:
            models_to_retrain = model_types or list(self.models.keys())
            results = {}
            
            logger.info(f"Retraining {len(models_to_retrain)} models")
            
            # Load fresh training data
            training_data = await self._load_training_data()
            if not training_data:
                logger.warning("No training data available for retraining")
                return {model.value: False for model in models_to_retrain}
            
            for model_type in models_to_retrain:
                if model_type in self.models:
                    try:
                        success = await self.models[model_type].train(training_data)
                        results[model_type.value] = success
                        if success:
                            logger.info(f"Successfully retrained {model_type.value}")
                        else:
                            logger.warning(f"Failed to retrain {model_type.value}")
                    except Exception as e:
                        logger.error(f"Error retraining {model_type.value}: {e}")
                        results[model_type.value] = False
                else:
                    logger.error(f"Model type {model_type.value} not available")
                    results[model_type.value] = False
            
            return results
            
        except Exception as e:
            logger.error(f"Error retraining models: {e}")
            return {}
    
    # Private helper methods
    
    async def _load_training_data(self) -> List[Dict[str, Any]]:
        """Load historical data for model training"""
        try:
            db = SessionLocal()
            try:
                # Load flight and disruption data from the last year
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=365)
                
                # Get bookings with their flights and disruptions
                bookings = db.query(Booking).filter(
                    Booking.departure_date >= cutoff_date
                ).all()
                
                training_data = []
                for booking in bookings:
                    # Get disruption events for this booking
                    disruption_events = db.query(DisruptionEvent).filter(
                        DisruptionEvent.booking_id == booking.booking_id
                    ).all()
                    
                    # Create training record
                    record = {
                        'booking_id': booking.booking_id,
                        'origin': booking.origin,
                        'destination': booking.destination,
                        'airline': booking.airline,
                        'departure_time': booking.departure_date,
                        'booking_class': booking.booking_class,
                        'is_disrupted': len(disruption_events) > 0,
                        'delay_minutes': max([e.delay_minutes for e in disruption_events], default=0),
                        'disruption_type': disruption_events[0].disruption_type if disruption_events else None,
                        'disruption_reason': disruption_events[0].reason if disruption_events else None
                    }
                    training_data.append(record)
                
                logger.info(f"Loaded {len(training_data)} training records")
                return training_data
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            return []
    
    async def _select_best_model(self, input_data: Dict[str, Any], 
                               preference: Optional[PredictionModel] = None) -> Optional[MLModelInterface]:
        """Select the best model for the given input data"""
        try:
            # Use preferred model if specified and available
            if preference and preference in self.models:
                model = self.models[preference]
                if model.is_trained:
                    return model
            
            # Find best trained model
            for model_type in [PredictionModel.ROUTE_SPECIFIC, PredictionModel.ENSEMBLE]:
                if model_type in self.models and self.models[model_type].is_trained:
                    return self.models[model_type]
            
            # Fallback to any available model
            for model in self.models.values():
                if model.is_trained:
                    return model
            
            logger.warning("No trained models available")
            return None
            
        except Exception as e:
            logger.error(f"Error selecting model: {e}")
            return None
    
    def _generate_cache_key(self, booking_id: str, input_data: Dict[str, Any]) -> str:
        """Generate cache key for prediction"""
        key_data = {
            'booking_id': booking_id,
            'origin': input_data.get('origin'),
            'destination': input_data.get('destination'),
            'airline': input_data.get('airline'),
            'departure_hour': input_data.get('departure_time', datetime.now()).hour if input_data.get('departure_time') else 0
        }
        return f"prediction:{hash(json.dumps(key_data, sort_keys=True))}"
    
    def _get_cached_prediction(self, cache_key: str) -> Optional[DelayPrediction]:
        """Get cached prediction if still valid"""
        try:
            if cache_key in self.prediction_cache:
                cached = self.prediction_cache[cache_key]
                if datetime.now(timezone.utc) < cached['expires_at']:
                    return cached['prediction']
                else:
                    del self.prediction_cache[cache_key]
            return None
        except Exception as e:
            logger.error(f"Error getting cached prediction: {e}")
            return None
    
    def _cache_prediction(self, cache_key: str, prediction: DelayPrediction):
        """Cache prediction with TTL"""
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.cache_ttl_minutes)
            self.prediction_cache[cache_key] = {
                'prediction': prediction,
                'expires_at': expires_at
            }
        except Exception as e:
            logger.error(f"Error caching prediction: {e}")
    
    def _track_prediction(self, prediction: DelayPrediction):
        """Track prediction for performance analysis"""
        try:
            self.prediction_history.append({
                'timestamp': prediction.prediction_timestamp,
                'model': prediction.prediction_model.value,
                'confidence_score': prediction.confidence_score,
                'delay_probability': prediction.delay_probability,
                'threshold_exceeded': prediction.threshold_exceeded
            })
        except Exception as e:
            logger.error(f"Error tracking prediction: {e}")
    
    def _create_fallback_prediction(self, booking_id: str, input_data: Dict[str, Any]) -> DelayPrediction:
        """Create fallback prediction when no models are available"""
        route_id = f"{input_data.get('origin', 'UNK')}-{input_data.get('destination', 'UNK')}"
        
        return DelayPrediction(
            booking_id=booking_id,
            route_id=route_id,
            prediction_model=PredictionModel.HISTORICAL_PATTERNS,
            delay_probability=0.2,  # Conservative default
            expected_delay_minutes=15.0,
            confidence_level=PredictionConfidence.VERY_LOW,
            confidence_score=0.1,
            contributing_factors=["No models available - using fallback"],
            threshold_exceeded=False,
            risk_score=0.2,
            model_version="fallback",
            prediction_timestamp=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(minutes=15),
            historical_context={'fallback': True},
            route_pattern_data=None
        )
    
    def _create_error_prediction(self, booking_id: str, error_msg: str, input_data: Dict[str, Any]) -> DelayPrediction:
        """Create error prediction when prediction fails"""
        route_id = f"{input_data.get('origin', 'UNK')}-{input_data.get('destination', 'UNK')}"
        
        return DelayPrediction(
            booking_id=booking_id,
            route_id=route_id,
            prediction_model=PredictionModel.HISTORICAL_PATTERNS,
            delay_probability=0.0,
            expected_delay_minutes=0.0,
            confidence_level=PredictionConfidence.VERY_LOW,
            confidence_score=0.0,
            contributing_factors=[f"Prediction error: {error_msg}"],
            threshold_exceeded=False,
            risk_score=0.0,
            model_version="error",
            prediction_timestamp=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(minutes=5),
            historical_context={'error': error_msg},
            route_pattern_data=None
        )


# Async utility functions for easy integration

async def predict_booking_delay(booking_id: str) -> Optional[DelayPrediction]:
    """
    Main entry point for delay prediction
    
    Args:
        booking_id: ID of booking to predict
        
    Returns:
        DelayPrediction or None if booking not found
    """
    db = SessionLocal()
    try:
        booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
        if not booking:
            logger.error(f"Booking {booking_id} not found")
            return None
        
        # Prepare input data
        input_data = {
            'booking_id': booking_id,
            'origin': booking.origin,
            'destination': booking.destination,
            'airline': booking.airline,
            'departure_time': booking.departure_date,
            'booking_class': booking.booking_class,
            'fare_amount': booking.fare_amount
        }
        
        # Get global prediction engine instance
        engine = _get_global_engine()
        return await engine.predict_delay(booking_id, input_data)
        
    except Exception as e:
        logger.error(f"Error predicting delay for {booking_id}: {e}")
        return None
    finally:
        db.close()


# Global engine instance for easy access
_global_engine: Optional[PredictionEngine] = None

def _get_global_engine() -> PredictionEngine:
    """Get or create global prediction engine instance"""
    global _global_engine
    if _global_engine is None:
        _global_engine = PredictionEngine()
        # Note: initialize() should be called separately in async context
    return _global_engine


# CLI function for testing
async def main():
    """CLI entry point for testing prediction engine"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m flight_agent.services.prediction_engine <booking_id>")
        return
    
    booking_id = sys.argv[1]
    
    # Initialize engine
    engine = PredictionEngine()
    if not await engine.initialize():
        print("❌ Failed to initialize prediction engine")
        return
    
    # Make prediction
    prediction = await predict_booking_delay(booking_id)
    
    if prediction:
        print(f"\n🔮 Delay Prediction for {booking_id}")
        print(f"Route: {prediction.route_id}")
        print(f"Model: {prediction.prediction_model.value}")
        print(f"Delay Probability: {prediction.delay_probability:.1%}")
        print(f"Expected Delay: {prediction.expected_delay_minutes:.1f} minutes")
        print(f"Confidence: {prediction.confidence_level.value} ({prediction.confidence_score:.2f})")
        print(f"Risk Score: {prediction.risk_score:.2f}")
        print(f"Threshold Exceeded: {'Yes' if prediction.threshold_exceeded else 'No'}")
        
        print(f"\n📊 Contributing Factors:")
        for factor in prediction.contributing_factors:
            print(f"  • {factor}")
        
        if prediction.route_pattern_data:
            pattern = prediction.route_pattern_data
            print(f"\n📈 Route Pattern Data:")
            print(f"  Sample Size: {pattern.sample_size}")
            print(f"  Historical Delay Rate: {pattern.delay_probability:.1%}")
            print(f"  Average Delay: {pattern.average_delay_minutes:.1f} minutes")
            print(f"  Pattern Confidence: {pattern.confidence_score:.2f}")
    else:
        print(f"❌ Could not generate prediction for booking {booking_id}")


if __name__ == "__main__":
    asyncio.run(main())
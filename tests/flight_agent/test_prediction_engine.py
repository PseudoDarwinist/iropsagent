"""
Tests for Prediction Engine
Task 3: Create prediction engine for disruption analysis

Tests for:
- ML model interface functionality
- Route-specific delay pattern recognition
- Confidence scoring and threshold management
- Requirements REQ-6.1, REQ-6.4, REQ-6.5
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
import json

from flight_agent.services.prediction_engine import (
    PredictionEngine,
    DelayPrediction,
    RoutePattern,
    MLModelInterface,
    RouteSpecificModel,
    PredictionModel,
    PredictionConfidence,
    predict_booking_delay
)
from flight_agent.models import create_booking, create_user, create_disruption_event


class TestMLModelInterface:
    """Test ML model interface functionality (REQ-6.1)"""
    
    def test_ml_model_interface_abstract_methods(self):
        """Test that MLModelInterface properly defines abstract methods"""
        model = MLModelInterface("TestModel", "1.0")
        
        assert model.model_name == "TestModel"
        assert model.version == "1.0"
        assert not model.is_trained
        assert model.training_data_size == 0
        
        # Test that abstract methods raise NotImplementedError
        with pytest.raises(NotImplementedError):
            asyncio.run(model.train([]))
        
        with pytest.raises(NotImplementedError):
            asyncio.run(model.predict({}))
        
        with pytest.raises(NotImplementedError):
            asyncio.run(model.update_model([]))
    
    def test_ml_model_metrics(self):
        """Test model metrics functionality"""
        model = MLModelInterface("TestModel", "2.0")
        model.is_trained = True
        model.training_data_size = 100
        model.last_training_date = datetime.now(timezone.utc)
        model.performance_metrics = {"accuracy": 0.85}
        
        metrics = model.get_model_metrics()
        
        assert metrics['model_name'] == "TestModel"
        assert metrics['version'] == "2.0"
        assert metrics['is_trained'] is True
        assert metrics['training_data_size'] == 100
        assert metrics['performance_metrics']['accuracy'] == 0.85
        assert 'last_training_date' in metrics


class TestRouteSpecificModel:
    """Test route-specific delay pattern recognition (REQ-6.4)"""
    
    @pytest.fixture
    def model(self):
        """Create RouteSpecificModel instance"""
        return RouteSpecificModel()
    
    @pytest.fixture
    def sample_training_data(self):
        """Sample training data for model"""
        base_time = datetime.now(timezone.utc)
        return [
            {
                'origin': 'JFK', 'destination': 'LAX', 'airline': 'AA',
                'departure_time': base_time + timedelta(hours=8),
                'is_disrupted': True, 'delay_minutes': 45,
                'disruption_type': 'delay', 'disruption_reason': 'weather'
            },
            {
                'origin': 'JFK', 'destination': 'LAX', 'airline': 'AA',
                'departure_time': base_time + timedelta(hours=18),
                'is_disrupted': True, 'delay_minutes': 30,
                'disruption_type': 'delay', 'disruption_reason': 'congestion'
            },
            {
                'origin': 'JFK', 'destination': 'LAX', 'airline': 'AA',
                'departure_time': base_time + timedelta(hours=12),
                'is_disrupted': False, 'delay_minutes': 0
            },
            # Add more samples for statistical significance
            *[{
                'origin': 'JFK', 'destination': 'LAX', 'airline': 'AA',
                'departure_time': base_time + timedelta(hours=i),
                'is_disrupted': i % 3 == 0,  # Every third flight delayed
                'delay_minutes': 25 if i % 3 == 0 else 0
            } for i in range(10, 25)]
        ]
    
    @pytest.mark.asyncio
    async def test_train_route_specific_model(self, model, sample_training_data):
        """Test training route-specific patterns"""
        success = await model.train(sample_training_data)
        
        assert success is True
        assert model.is_trained is True
        assert model.training_data_size == len(sample_training_data)
        assert 'JFK-LAX-AA' in model.route_patterns
        
        pattern = model.route_patterns['JFK-LAX-AA']
        assert pattern.origin == 'JFK'
        assert pattern.destination == 'LAX'
        assert pattern.airline == 'AA'
        assert pattern.sample_size >= model.min_samples_for_pattern
        assert 0.0 <= pattern.delay_probability <= 1.0
        assert pattern.average_delay_minutes >= 0.0
    
    @pytest.mark.asyncio
    async def test_route_pattern_creation(self, model, sample_training_data):
        """Test route pattern creation with sufficient data"""
        await model.train(sample_training_data)
        
        pattern = model.route_patterns['JFK-LAX-AA']
        
        # Test pattern attributes
        assert isinstance(pattern.peak_delay_hours, list)
        assert isinstance(pattern.seasonal_factors, dict)
        assert len(pattern.seasonal_factors) == 12  # All months
        assert 0.0 <= pattern.weather_sensitivity <= 1.0
        assert pattern.confidence_score > 0.0
        assert isinstance(pattern.recurring_patterns, list)
        assert isinstance(pattern.disruption_types, dict)
    
    @pytest.mark.asyncio
    async def test_prediction_with_trained_model(self, model, sample_training_data):
        """Test making predictions with trained model"""
        await model.train(sample_training_data)
        
        input_data = {
            'booking_id': 'test_123',
            'origin': 'JFK',
            'destination': 'LAX',
            'airline': 'AA',
            'departure_time': datetime.now(timezone.utc) + timedelta(hours=8)
        }
        
        prediction = await model.predict(input_data)
        
        assert prediction.booking_id == 'test_123'
        assert prediction.route_id == 'JFK-LAX-AA'
        assert prediction.prediction_model == PredictionModel.ROUTE_SPECIFIC
        assert 0.0 <= prediction.delay_probability <= 1.0
        assert prediction.expected_delay_minutes >= 0.0
        assert isinstance(prediction.confidence_level, PredictionConfidence)
        assert 0.0 <= prediction.confidence_score <= 1.0
        assert isinstance(prediction.contributing_factors, list)
        assert prediction.route_pattern_data is not None
    
    @pytest.mark.asyncio
    async def test_prediction_without_pattern(self, model):
        """Test prediction fallback when no pattern is available"""
        # Don't train the model, so no patterns available
        input_data = {
            'booking_id': 'test_456',
            'origin': 'XYZ',
            'destination': 'ABC',
            'airline': 'XX'
        }
        
        prediction = await model.predict(input_data)
        
        assert prediction.booking_id == 'test_456'
        assert prediction.confidence_level == PredictionConfidence.LOW
        assert prediction.route_pattern_data is None
        assert "No route-specific pattern available" in prediction.contributing_factors[0]
    
    @pytest.mark.asyncio 
    async def test_confidence_scoring_factors(self, model, sample_training_data):
        """Test confidence scoring based on various factors"""
        await model.train(sample_training_data)
        
        # Test with sufficient data
        input_data = {
            'origin': 'JFK', 'destination': 'LAX', 'airline': 'AA',
            'departure_time': datetime.now(timezone.utc) + timedelta(hours=8)
        }
        
        prediction = await model.predict(input_data)
        confidence_with_data = prediction.confidence_score
        
        # Confidence should be reasonable with training data (adjusted threshold)
        assert confidence_with_data > 0.1
        assert confidence_with_data <= 1.0
        
        # Test feature importance (if implemented)
        feature_importance = model.get_feature_importance()
        assert isinstance(feature_importance, dict)


class TestPredictionEngine:
    """Test main PredictionEngine functionality (REQ-6.5)"""
    
    @pytest.fixture
    def engine(self):
        """Create PredictionEngine instance"""
        return PredictionEngine()
    
    @pytest.fixture
    def mock_booking_data(self):
        """Mock booking data for testing"""
        return {
            'booking_id': 'test_booking_123',
            'origin': 'JFK',
            'destination': 'LAX',
            'airline': 'AA',
            'departure_time': datetime.now(timezone.utc) + timedelta(hours=24),
            'booking_class': 'Economy',
            'fare_amount': 350.0
        }
    
    def test_engine_initialization(self, engine):
        """Test prediction engine initialization"""
        assert isinstance(engine.models, dict)
        assert PredictionModel.ROUTE_SPECIFIC in engine.models
        assert engine.confidence_threshold == 0.5
        assert engine.delay_probability_threshold == 0.3
        assert isinstance(engine.prediction_cache, dict)
        assert engine.cache_ttl_minutes == 30
    
    @pytest.mark.asyncio
    async def test_threshold_management(self, engine):
        """Test confidence and delay probability threshold management (REQ-6.5)"""
        # Test confidence threshold updates
        assert await engine.update_threshold("confidence", 0.7) is True
        assert engine.confidence_threshold == 0.7
        
        assert await engine.update_threshold("confidence", 1.5) is False  # Invalid value
        assert engine.confidence_threshold == 0.7  # Should remain unchanged
        
        # Test delay probability threshold updates
        assert await engine.update_threshold("delay_probability", 0.25) is True
        assert engine.delay_probability_threshold == 0.25
        
        assert await engine.update_threshold("delay_probability", -0.1) is False  # Invalid value
        assert engine.delay_probability_threshold == 0.25  # Should remain unchanged
        
        # Test invalid threshold type
        assert await engine.update_threshold("invalid_type", 0.5) is False
    
    @pytest.mark.asyncio
    async def test_delay_prediction_with_thresholds(self, engine, mock_booking_data):
        """Test delay prediction with threshold checking"""
        # Mock a trained model
        mock_model = Mock(spec=MLModelInterface)
        mock_model.is_trained = True
        mock_prediction = DelayPrediction(
            booking_id=mock_booking_data['booking_id'],
            route_id='JFK-LAX',
            prediction_model=PredictionModel.ROUTE_SPECIFIC,
            delay_probability=0.6,  # Above 30% threshold
            expected_delay_minutes=45.0,
            confidence_level=PredictionConfidence.HIGH,
            confidence_score=0.8,  # Above 50% confidence threshold
            contributing_factors=["High-delay route"],
            threshold_exceeded=False,  # Will be set by engine
            risk_score=0.6,
            model_version="1.0",
            prediction_timestamp=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(hours=2),
            historical_context={},
            route_pattern_data=None
        )
        mock_model.predict.return_value = mock_prediction
        
        engine.models[PredictionModel.ROUTE_SPECIFIC] = mock_model
        
        prediction = await engine.predict_delay(mock_booking_data['booking_id'], mock_booking_data)
        
        # Verify threshold checking
        assert prediction.threshold_exceeded is True  # 60% > 30% threshold
        assert any("exceeds threshold" in factor for factor in prediction.contributing_factors)
    
    @pytest.mark.asyncio
    async def test_prediction_caching(self, engine, mock_booking_data):
        """Test prediction caching functionality"""
        # Mock a model to return consistent results
        mock_model = Mock(spec=MLModelInterface)
        mock_model.is_trained = True
        mock_prediction = DelayPrediction(
            booking_id=mock_booking_data['booking_id'],
            route_id='JFK-LAX',
            prediction_model=PredictionModel.ROUTE_SPECIFIC,
            delay_probability=0.3,
            expected_delay_minutes=30.0,
            confidence_level=PredictionConfidence.MEDIUM,
            confidence_score=0.6,
            contributing_factors=["Test prediction"],
            threshold_exceeded=True,
            risk_score=0.3,
            model_version="1.0",
            prediction_timestamp=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(hours=2),
            historical_context={},
            route_pattern_data=None
        )
        mock_model.predict.return_value = mock_prediction
        engine.models[PredictionModel.ROUTE_SPECIFIC] = mock_model
        
        # First prediction should call the model
        prediction1 = await engine.predict_delay(mock_booking_data['booking_id'], mock_booking_data)
        assert mock_model.predict.call_count == 1
        
        # Second prediction should use cache
        prediction2 = await engine.predict_delay(mock_booking_data['booking_id'], mock_booking_data)
        assert mock_model.predict.call_count == 1  # Still 1, used cache
        
        assert prediction1.booking_id == prediction2.booking_id
        assert prediction1.delay_probability == prediction2.delay_probability
    
    @pytest.mark.asyncio
    async def test_batch_predictions(self, engine, mock_booking_data):
        """Test batch prediction functionality"""
        # Create multiple booking requests
        requests = [
            (f"booking_{i}", {**mock_booking_data, 'booking_id': f"booking_{i}"})
            for i in range(3)
        ]
        
        # Mock model
        mock_model = Mock(spec=MLModelInterface)
        mock_model.is_trained = True
        
        def mock_predict(input_data):
            return DelayPrediction(
                booking_id=input_data['booking_id'],
                route_id='JFK-LAX',
                prediction_model=PredictionModel.ROUTE_SPECIFIC,
                delay_probability=0.2,
                expected_delay_minutes=20.0,
                confidence_level=PredictionConfidence.MEDIUM,
                confidence_score=0.5,
                contributing_factors=["Batch prediction"],
                threshold_exceeded=False,
                risk_score=0.2,
                model_version="1.0",
                prediction_timestamp=datetime.now(timezone.utc),
                valid_until=datetime.now(timezone.utc) + timedelta(hours=2),
                historical_context={},
                route_pattern_data=None
            )
        
        mock_model.predict.side_effect = mock_predict
        engine.models[PredictionModel.ROUTE_SPECIFIC] = mock_model
        
        results = await engine.predict_multiple(requests)
        
        assert len(results) == 3
        for i in range(3):
            booking_id = f"booking_{i}"
            assert booking_id in results
            assert results[booking_id].booking_id == booking_id
    
    def test_model_performance_tracking(self, engine):
        """Test model performance tracking and reporting"""
        performance = engine.get_model_performance()
        
        assert 'engine_config' in performance
        assert 'models' in performance
        assert 'prediction_stats' in performance
        
        config = performance['engine_config']
        assert config['confidence_threshold'] == engine.confidence_threshold
        assert config['delay_probability_threshold'] == engine.delay_probability_threshold
        
        stats = performance['prediction_stats']
        assert 'total_predictions' in stats
        assert 'recent_predictions' in stats
    
    @pytest.mark.asyncio
    async def test_model_retraining(self, engine):
        """Test model retraining functionality"""
        # Mock training data loading
        with patch.object(engine, '_load_training_data') as mock_load:
            mock_load.return_value = [
                {'origin': 'JFK', 'destination': 'LAX', 'delay_minutes': 30}
            ]
            
            # Mock model training
            mock_model = Mock(spec=MLModelInterface)
            mock_model.train.return_value = True
            engine.models[PredictionModel.ROUTE_SPECIFIC] = mock_model
            
            results = await engine.retrain_models([PredictionModel.ROUTE_SPECIFIC])
            
            assert PredictionModel.ROUTE_SPECIFIC.value in results
            assert results[PredictionModel.ROUTE_SPECIFIC.value] is True
            assert mock_model.train.called
    
    @pytest.mark.asyncio
    async def test_fallback_prediction(self, engine, mock_booking_data):
        """Test fallback prediction when no models are available"""
        # Clear all models to force fallback
        engine.models = {}
        
        prediction = await engine.predict_delay(mock_booking_data['booking_id'], mock_booking_data)
        
        assert prediction.confidence_level == PredictionConfidence.VERY_LOW
        assert prediction.confidence_score == 0.1
        assert "No models available - using fallback" in prediction.contributing_factors[0]


class TestPredictionIntegration:
    """Test integration with existing systems"""
    
    @pytest.mark.asyncio
    async def test_predict_booking_delay_function(self):
        """Test the main predict_booking_delay function"""
        # This would require actual database setup
        # For now, test that it handles missing bookings gracefully
        
        result = await predict_booking_delay("nonexistent_booking")
        assert result is None  # Should return None for missing booking
    
    @pytest.mark.asyncio
    async def test_req_6_1_ml_model_interface_compliance(self):
        """REQ-6.1: Verify ML model interface provides consistent prediction capabilities"""
        model = RouteSpecificModel()
        
        # Test interface compliance
        assert hasattr(model, 'train')
        assert hasattr(model, 'predict') 
        assert hasattr(model, 'update_model')
        assert hasattr(model, 'get_feature_importance')
        assert hasattr(model, 'get_model_metrics')
        
        # Test that methods return expected types
        metrics = model.get_model_metrics()
        assert isinstance(metrics, dict)
        assert 'model_name' in metrics
        assert 'version' in metrics
        assert 'is_trained' in metrics
    
    @pytest.mark.asyncio
    async def test_req_6_4_route_specific_patterns(self):
        """REQ-6.4: Verify route-specific delay pattern recognition"""
        model = RouteSpecificModel()
        
        # Create sample data with clear patterns
        training_data = []
        base_time = datetime.now(timezone.utc)
        
        # Create pattern: JFK-LAX flights delayed more in morning
        for hour in range(24):
            for day in range(30):  # 30 days of data
                departure_time = base_time + timedelta(days=day, hours=hour)
                # Morning flights (6-9 AM) have higher delay probability
                is_delayed = hour >= 6 and hour <= 9 and (day % 3 == 0)  # Every third morning flight
                delay_minutes = 45 if is_delayed else 0
                
                training_data.append({
                    'origin': 'JFK',
                    'destination': 'LAX', 
                    'airline': 'AA',
                    'departure_time': departure_time,
                    'is_disrupted': is_delayed,
                    'delay_minutes': delay_minutes
                })
        
        # Train model
        success = await model.train(training_data)
        assert success is True
        
        # Verify pattern was learned
        pattern = model.route_patterns.get('JFK-LAX-AA')
        assert pattern is not None
        assert pattern.sample_size == len(training_data)
        
        # Test prediction for morning flight (should have higher delay probability)
        morning_input = {
            'origin': 'JFK',
            'destination': 'LAX',
            'airline': 'AA',
            'departure_time': base_time + timedelta(hours=8)  # 8 AM
        }
        morning_prediction = await model.predict(morning_input)
        
        # Test prediction for afternoon flight (should have lower delay probability)
        afternoon_input = {
            'origin': 'JFK',
            'destination': 'LAX',
            'airline': 'AA',
            'departure_time': base_time + timedelta(hours=14)  # 2 PM
        }
        afternoon_prediction = await model.predict(afternoon_input)
        
        # Morning should have higher delay probability due to pattern
        assert morning_prediction.delay_probability > afternoon_prediction.delay_probability
    
    @pytest.mark.asyncio
    async def test_req_6_5_confidence_scoring_and_thresholds(self):
        """REQ-6.5: Verify confidence scoring and threshold management"""
        engine = PredictionEngine()
        
        # Test initial threshold values
        assert engine.confidence_threshold == 0.5
        assert engine.delay_probability_threshold == 0.3
        
        # Test threshold updates
        assert await engine.update_threshold("confidence", 0.8) is True
        assert engine.confidence_threshold == 0.8
        
        assert await engine.update_threshold("delay_probability", 0.25) is True 
        assert engine.delay_probability_threshold == 0.25
        
        # Test threshold validation
        assert await engine.update_threshold("confidence", 1.5) is False
        assert await engine.update_threshold("delay_probability", -0.1) is False
        
        # Test confidence scoring affects prediction quality
        mock_model = Mock(spec=MLModelInterface)
        mock_model.is_trained = True
        
        # Low confidence prediction
        low_confidence_prediction = DelayPrediction(
            booking_id="test",
            route_id="JFK-LAX",
            prediction_model=PredictionModel.ROUTE_SPECIFIC,
            delay_probability=0.4,
            expected_delay_minutes=30.0,
            confidence_level=PredictionConfidence.LOW,
            confidence_score=0.3,  # Below engine threshold of 0.8
            contributing_factors=[],
            threshold_exceeded=False,
            risk_score=0.4,
            model_version="1.0",
            prediction_timestamp=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
            historical_context={},
            route_pattern_data=None
        )
        
        mock_model.predict.return_value = low_confidence_prediction
        engine.models[PredictionModel.ROUTE_SPECIFIC] = mock_model
        
        input_data = {'booking_id': 'test', 'origin': 'JFK', 'destination': 'LAX'}
        prediction = await engine.predict_delay('test', input_data)
        
        # Engine should add warning about low confidence
        assert any("Low confidence" in factor for factor in prediction.contributing_factors)


if __name__ == "__main__":
    pytest.main([__file__])
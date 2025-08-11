"""
Tests for Disruption Risk Detection Algorithm
Task 2.2: Create disruption risk detection algorithm

Test coverage for:
- Delay probability calculation (>30% threshold)
- Weather impact correlation logic
- Connection risk assessment for missed connections
- REQ-1.2 and REQ-1.5 compliance
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock

from flight_agent.services.disruption_risk_detector import (
    DisruptionRiskDetector,
    WeatherDataProvider,
    RiskLevel,
    DisruptionType,
    RiskFactor,
    DisruptionRisk,
    detect_disruption_risk
)
from flight_agent.models import (
    SessionLocal, Booking, User, create_user, create_booking, TripMonitor
)
from flight_agent.providers.interfaces import FlightStatusData


class TestWeatherDataProvider:
    """Test weather data integration"""
    
    def test_weather_provider_initialization(self):
        """Test weather provider initializes correctly"""
        provider = WeatherDataProvider()
        assert provider.base_url == "https://api.weatherapi.com/v1"
        assert hasattr(provider, 'api_key')
    
    @pytest.mark.asyncio
    async def test_get_weather_conditions_simulation(self):
        """Test simulated weather conditions"""
        provider = WeatherDataProvider()
        
        now = datetime.now(timezone.utc)
        conditions = await provider.get_weather_conditions("ORD", now)
        
        assert "visibility_miles" in conditions
        assert "wind_speed_mph" in conditions
        assert "precipitation_inches" in conditions
        assert "weather_risk_score" in conditions
        
        # ORD should have higher weather risk due to being weather-prone
        assert conditions["weather_risk_score"] >= 0.2
    
    def test_simulate_weather_conditions_patterns(self):
        """Test weather simulation produces realistic patterns"""
        provider = WeatherDataProvider()
        
        # Test weather-prone airport
        winter_date = datetime(2025, 1, 15, tzinfo=timezone.utc)
        ord_conditions = provider._simulate_weather_conditions("ORD", winter_date)
        
        # Test low-risk airport
        lax_conditions = provider._simulate_weather_conditions("LAX", winter_date)
        
        # ORD should generally have higher risk than LAX
        assert ord_conditions["weather_risk_score"] >= lax_conditions["weather_risk_score"]


class TestRiskFactor:
    """Test RiskFactor data structure"""
    
    def test_risk_factor_creation(self):
        """Test RiskFactor creation and attributes"""
        factor = RiskFactor(
            factor_type="test_factor",
            weight=0.3,
            probability=0.45,
            description="Test factor description",
            data={"test_key": "test_value"}
        )
        
        assert factor.factor_type == "test_factor"
        assert factor.weight == 0.3
        assert factor.probability == 0.45
        assert factor.description == "Test factor description"
        assert factor.data["test_key"] == "test_value"


class TestDisruptionRiskDetector:
    """Test main disruption risk detection functionality"""
    
    @pytest.fixture
    def detector(self):
        """Create DisruptionRiskDetector instance"""
        return DisruptionRiskDetector()
    
    @pytest.fixture
    def test_user(self):
        """Create test user"""
        return create_user("test@example.com", "+1234567890")
    
    @pytest.fixture
    def test_booking(self, test_user):
        """Create test booking"""
        departure_date = datetime.now(timezone.utc) + timedelta(days=1, hours=10)
        booking_data = {
            "pnr": "TEST123",
            "airline": "AA",
            "flight_number": "AA123", 
            "departure_date": departure_date,
            "origin": "JFK",
            "destination": "LAX"
        }
        return create_booking(test_user.user_id, booking_data)
    
    @pytest.fixture
    def connecting_booking(self, test_user, test_booking):
        """Create connecting flight booking"""
        # Connection departing 2 hours after first flight's scheduled arrival
        connection_departure = test_booking.departure_date + timedelta(hours=5)  # 5 hour total trip + connection
        
        booking_data = {
            "pnr": "CONNECT456",
            "airline": "DL", 
            "flight_number": "DL456",
            "departure_date": connection_departure,
            "origin": "LAX",  # Same as first flight's destination
            "destination": "SEA"
        }
        return create_booking(test_user.user_id, booking_data)
    
    def test_detector_initialization(self, detector):
        """Test detector initializes with correct parameters"""
        assert detector.risk_threshold == 0.3  # 30% threshold as specified
        assert hasattr(detector, 'weather_provider')
        assert hasattr(detector, 'weights')
        
        # Verify weights sum to reasonable total
        total_weight = sum(detector.weights.values())
        assert 0.9 <= total_weight <= 1.1  # Allow small rounding differences
    
    @pytest.mark.asyncio
    async def test_assess_disruption_risk_basic(self, detector, test_booking):
        """Test basic disruption risk assessment"""
        risk = await detector.assess_disruption_risk(test_booking)
        
        assert isinstance(risk, DisruptionRisk)
        assert risk.booking_id == test_booking.booking_id
        assert 0 <= risk.overall_probability <= 1
        assert isinstance(risk.risk_level, RiskLevel)
        assert isinstance(risk.primary_risk_type, DisruptionType)
        assert len(risk.risk_factors) >= 3  # Should have multiple factors
        assert risk.confidence_score > 0
        assert isinstance(risk.recommendations, list)
    
    @pytest.mark.asyncio
    async def test_calculate_delay_probability(self, detector, test_booking):
        """Test delay probability calculation"""
        delay_factor = await detector._calculate_delay_probability(test_booking, None)
        
        assert delay_factor.factor_type == "delay_probability"
        assert delay_factor.weight == detector.weights['historical_delay']
        assert 0 <= delay_factor.probability <= 1
        assert "Delay probability" in delay_factor.description
        assert isinstance(delay_factor.data, dict)
        
        # Test with flight status showing delay
        delayed_status = FlightStatusData(
            flight_id="AA123_20250115",
            status="DELAYED",
            delay_minutes=90,  # 1.5 hour delay
            scheduled_departure=test_booking.departure_date,
            actual_departure=None,
            scheduled_arrival=test_booking.departure_date + timedelta(hours=5),
            actual_arrival=None,
            gate=None,
            terminal=None,
            is_disrupted=True,
            disruption_type="DELAYED",
            last_updated=datetime.now(timezone.utc),
            source="Test",
            confidence_score=0.9,
            raw_data={}
        )
        
        delay_factor_with_status = await detector._calculate_delay_probability(test_booking, delayed_status)
        
        # Should have higher probability when already delayed
        assert delay_factor_with_status.probability > delay_factor.probability
    
    @pytest.mark.asyncio
    async def test_assess_weather_impact(self, detector, test_booking):
        """Test weather impact assessment"""
        weather_factor = await detector._assess_weather_impact(test_booking)
        
        assert weather_factor.factor_type == "weather_impact"
        assert weather_factor.weight == detector.weights['weather']
        assert 0 <= weather_factor.probability <= 1
        assert "Weather impact" in weather_factor.description
        
        # Should have both departure and arrival weather data
        assert 'departure_weather' in weather_factor.data
        assert 'arrival_weather' in weather_factor.data
        assert 'departure_risk' in weather_factor.data
        assert 'arrival_risk' in weather_factor.data
    
    @pytest.mark.asyncio
    async def test_assess_connection_risk_no_connections(self, detector, test_booking):
        """Test connection risk when no connections exist"""
        connection_factor = await detector._assess_connection_risk(test_booking)
        
        assert connection_factor.factor_type == "connection_risk"
        assert connection_factor.probability == 0.0
        assert "No connecting flights detected" in connection_factor.description
        assert connection_factor.data['connections_found'] == 0
    
    @pytest.mark.asyncio
    async def test_assess_connection_risk_with_connections(self, detector, test_booking, connecting_booking):
        """Test connection risk with actual connecting flights"""
        connection_factor = await detector._assess_connection_risk(test_booking)
        
        assert connection_factor.factor_type == "connection_risk"
        assert connection_factor.probability > 0.0  # Should detect some risk
        assert connection_factor.data['connections_found'] == 1
        assert len(connection_factor.data['connection_details']) == 1
        
        # Verify connection details
        conn_detail = connection_factor.data['connection_details'][0]
        assert conn_detail['connecting_flight'] == "DL456"
        assert conn_detail['layover_minutes'] > 0
        assert conn_detail['min_connection_time'] > 0
        assert conn_detail['risk_score'] >= 0
    
    @pytest.mark.asyncio
    async def test_assess_historical_patterns(self, detector, test_booking):
        """Test historical pattern analysis"""
        historical_factor = await detector._assess_historical_patterns(test_booking)
        
        assert historical_factor.factor_type == "historical_patterns"
        assert historical_factor.weight == detector.weights['airline_performance']
        assert 0 <= historical_factor.probability <= 1
        
        # Should have comprehensive historical data
        data = historical_factor.data
        assert 'airline_reliability' in data
        assert 'route_performance' in data
        assert 'seasonal_factor' in data
        assert 'analysis_period' in data
        
        # AA should have reasonable reliability score
        assert 0.5 <= data['airline_reliability'] <= 1.0
    
    @pytest.mark.asyncio
    async def test_assess_airport_congestion(self, detector, test_booking):
        """Test airport congestion assessment"""
        congestion_factor = await detector._assess_airport_congestion(test_booking)
        
        assert congestion_factor.factor_type == "airport_congestion"
        assert congestion_factor.weight == detector.weights['airport_congestion']
        assert 0 <= congestion_factor.probability <= 1
        
        # Should have both airports analyzed
        data = congestion_factor.data
        assert 'departure_congestion' in data
        assert 'arrival_congestion' in data
        assert 'peak_hours' in data
        
        # JFK and LAX should have notable congestion
        assert data['departure_congestion'] > 0.2  # JFK is congested
        assert data['arrival_congestion'] > 0.2    # LAX is congested
    
    def test_calculate_overall_risk(self, detector):
        """Test overall risk calculation"""
        risk_factors = [
            RiskFactor("test1", 0.3, 0.4, "Test 1", {}),
            RiskFactor("test2", 0.5, 0.6, "Test 2", {}),
            RiskFactor("test3", 0.2, 0.2, "Test 3", {})
        ]
        
        overall_risk = detector._calculate_overall_risk(risk_factors)
        
        # Should be weighted average: (0.4*0.3 + 0.6*0.5 + 0.2*0.2) / (0.3+0.5+0.2)
        expected = (0.4*0.3 + 0.6*0.5 + 0.2*0.2) / 1.0
        assert abs(overall_risk - expected) < 0.01
    
    def test_determine_risk_level(self, detector):
        """Test risk level determination based on 30% threshold"""
        # Test all risk levels
        assert detector._determine_risk_level(0.8) == RiskLevel.CRITICAL
        assert detector._determine_risk_level(0.6) == RiskLevel.HIGH
        assert detector._determine_risk_level(0.4) == RiskLevel.MEDIUM
        assert detector._determine_risk_level(0.35) == RiskLevel.MEDIUM  # Above 30% threshold
        assert detector._determine_risk_level(0.25) == RiskLevel.LOW     # Below 30% threshold
        assert detector._determine_risk_level(0.1) == RiskLevel.LOW
    
    def test_identify_primary_risk_type(self, detector):
        """Test primary risk type identification"""
        risk_factors = [
            RiskFactor("delay_probability", 0.2, 0.3, "Delay risk", {}),
            RiskFactor("weather_impact", 0.3, 0.7, "Weather risk", {}),  # Highest weighted risk
            RiskFactor("connection_risk", 0.1, 0.2, "Connection risk", {})
        ]
        
        primary_type = detector._identify_primary_risk_type(risk_factors)
        assert primary_type == DisruptionType.WEATHER  # Weather has highest probability * weight
    
    def test_thirty_percent_threshold_compliance(self, detector):
        """Test that 30% threshold is properly implemented (Task requirement)"""
        # Risk level should be MEDIUM at exactly 30%
        assert detector._determine_risk_level(0.30) == RiskLevel.MEDIUM
        assert detector._determine_risk_level(0.29) == RiskLevel.LOW
        
        # Verify threshold constant
        assert detector.risk_threshold == 0.3
    
    def test_generate_recommendations(self, detector):
        """Test recommendation generation"""
        # High overall risk should trigger threshold warning
        high_risk_factors = [
            RiskFactor("weather_impact", 0.3, 0.8, "High weather risk", {}),
            RiskFactor("delay_probability", 0.25, 0.4, "High delay risk", {})
        ]
        
        recommendations = detector._generate_recommendations(high_risk_factors, 0.6)
        
        # Should have threshold alert
        threshold_alert = any("30% threshold" in rec for rec in recommendations)
        assert threshold_alert
        
        # Should have weather-specific recommendation
        weather_rec = any("weather" in rec.lower() for rec in recommendations)
        assert weather_rec
    
    def test_calculate_confidence_score(self, detector):
        """Test confidence score calculation"""
        # Full set of factors should give high confidence
        complete_factors = [
            RiskFactor("factor1", 0.2, 0.3, "Factor 1", {}),
            RiskFactor("factor2", 0.2, 0.4, "Factor 2", {}),
            RiskFactor("factor3", 0.2, 0.5, "Factor 3", {}),
            RiskFactor("factor4", 0.2, 0.3, "Factor 4", {}),
            RiskFactor("factor5", 0.2, 0.4, "Factor 5", {})
        ]
        
        confidence = detector._calculate_confidence_score(complete_factors)
        assert confidence >= 0.9  # Should be high confidence with 5 factors
        
        # Factors with errors should reduce confidence
        error_factors = [
            RiskFactor("factor1", 0.5, 0.3, "Error in calculation", {}),
            RiskFactor("factor2", 0.5, 0.4, "API error occurred", {})
        ]
        
        error_confidence = detector._calculate_confidence_score(error_factors)
        assert error_confidence < confidence  # Should be lower due to errors
    
    def test_helper_method_accuracy(self, detector):
        """Test accuracy of helper calculation methods"""
        # Test historical delay rates
        aa_delay_rate = detector._get_historical_delay_rate("AA", "JFK", "LAX")
        nk_delay_rate = detector._get_historical_delay_rate("NK", "JFK", "LAX")  # Budget carrier
        
        # Budget carriers should have higher delay rates
        assert nk_delay_rate > aa_delay_rate
        
        # Test time factors
        morning_rush = datetime(2025, 1, 15, 8, 0, tzinfo=timezone.utc)
        midday = datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc)
        
        morning_factor = detector._get_time_of_day_factor(morning_rush)
        midday_factor = detector._get_time_of_day_factor(midday)
        
        # Morning rush should have higher factor
        assert morning_factor > midday_factor
        
        # Test minimum connection times
        jfk_domestic = detector._get_minimum_connection_time("JFK", "AA", "AA")
        jfk_different_airlines = detector._get_minimum_connection_time("JFK", "AA", "DL")
        
        # Different airlines should require more time
        assert jfk_different_airlines > jfk_domestic


class TestDisruptionRiskIntegration:
    """Integration tests for disruption risk detection"""
    
    @pytest.fixture
    def test_user(self):
        """Create test user"""
        return create_user("integration@example.com", "+1555000123")
    
    @pytest.fixture
    def high_risk_booking(self, test_user):
        """Create booking with high disruption risk factors"""
        # Flight during winter, peak hours, from congested airport
        departure_date = datetime(2025, 1, 15, 8, 30, tzinfo=timezone.utc)  # Winter, morning rush
        
        booking_data = {
            "pnr": "HIGHRISK123",
            "airline": "NK",  # Budget carrier with higher delays
            "flight_number": "NK999",
            "departure_date": departure_date,
            "origin": "LGA",  # Congested airport
            "destination": "ORD"  # Weather-prone destination
        }
        return create_booking(test_user.user_id, booking_data)
    
    @pytest.fixture
    def low_risk_booking(self, test_user):
        """Create booking with low disruption risk factors"""
        # Flight during good weather season, off-peak hours, reliable airline
        departure_date = datetime(2025, 5, 15, 14, 0, tzinfo=timezone.utc)  # Spring, midday
        
        booking_data = {
            "pnr": "LOWRISK456",
            "airline": "DL",  # Reliable carrier
            "flight_number": "DL100",
            "departure_date": departure_date,
            "origin": "ATL",  # DL hub, efficient
            "destination": "LAX"
        }
        return create_booking(test_user.user_id, booking_data)
    
    @pytest.mark.asyncio
    async def test_high_risk_scenario(self, high_risk_booking):
        """Test that high-risk scenario is properly detected"""
        risk = await detect_disruption_risk(high_risk_booking.booking_id)
        
        assert risk is not None
        assert risk.overall_probability > 0.3  # Should exceed 30% threshold
        assert risk.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        
        # Should have appropriate recommendations for high risk
        assert len(risk.recommendations) > 0
        threshold_warning = any("30%" in rec for rec in risk.recommendations)
        assert threshold_warning
    
    @pytest.mark.asyncio
    async def test_low_risk_scenario(self, low_risk_booking):
        """Test that low-risk scenario produces appropriate assessment"""
        risk = await detect_disruption_risk(low_risk_booking.booking_id)
        
        assert risk is not None
        # Should be below or just at threshold
        assert risk.overall_probability <= 0.4
        assert risk.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
        
        # Should have good confidence in the assessment
        assert risk.confidence_score > 0.5
    
    @pytest.mark.asyncio
    async def test_connection_risk_integration(self, test_user):
        """Test connection risk detection with real booking scenario"""
        # Create first flight
        first_departure = datetime.now(timezone.utc) + timedelta(days=1, hours=10)
        first_booking_data = {
            "pnr": "FIRST123",
            "airline": "AA",
            "flight_number": "AA100",
            "departure_date": first_departure,
            "origin": "JFK",
            "destination": "ORD"
        }
        first_booking = create_booking(test_user.user_id, first_booking_data)
        
        # Create tight connection (45 minutes - risky for ORD)
        second_departure = first_departure + timedelta(hours=3, minutes=45)  # Tight connection
        second_booking_data = {
            "pnr": "SECOND456", 
            "airline": "UA",  # Different airline = more risk
            "flight_number": "UA200",
            "departure_date": second_departure,
            "origin": "ORD",
            "destination": "DEN"
        }
        second_booking = create_booking(test_user.user_id, second_booking_data)
        
        # Assess risk for first flight
        risk = await detect_disruption_risk(first_booking.booking_id)
        
        assert risk is not None
        
        # Should detect connection risk
        connection_factor = next((f for f in risk.risk_factors if f.factor_type == "connection_risk"), None)
        assert connection_factor is not None
        assert connection_factor.probability > 0.3  # Should be risky connection
        assert connection_factor.data['connections_found'] == 1
        
        # Should have connection-related recommendations
        connection_rec = any("connection" in rec.lower() for rec in risk.recommendations)
        assert connection_rec
    
    @pytest.mark.asyncio
    async def test_weather_correlation_integration(self, test_user):
        """Test weather impact correlation in realistic scenario"""
        # Flight to/from weather-prone airports during winter
        winter_departure = datetime(2025, 2, 1, 16, 0, tzinfo=timezone.utc)  # Winter
        
        booking_data = {
            "pnr": "WEATHER789",
            "airline": "UA", 
            "flight_number": "UA300",
            "departure_date": winter_departure,
            "origin": "ORD",  # Weather-prone
            "destination": "BOS"  # Also weather-prone in winter
        }
        booking = create_booking(test_user.user_id, booking_data)
        
        risk = await detect_disruption_risk(booking.booking_id)
        
        assert risk is not None
        
        # Should have significant weather impact
        weather_factor = next((f for f in risk.risk_factors if f.factor_type == "weather_impact"), None)
        assert weather_factor is not None
        assert weather_factor.probability > 0.2  # Should detect weather risk
        
        # Weather should be correlated with overall risk
        assert risk.weather_impact > 0.1
        
        # Should have weather-specific recommendations if risk is high
        if risk.overall_probability > 0.4:
            weather_rec = any("weather" in rec.lower() for rec in risk.recommendations)
            assert weather_rec
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling for invalid booking IDs"""
        risk = await detect_disruption_risk("INVALID_BOOKING_ID")
        assert risk is None
    
    @pytest.mark.asyncio
    async def test_performance_requirements(self, low_risk_booking):
        """Test that risk assessment completes within performance requirements"""
        import time
        
        start_time = time.time()
        risk = await detect_disruption_risk(low_risk_booking.booking_id)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Should complete within reasonable time (REQ-1.5 equivalent)
        assert execution_time < 5.0  # 5 seconds max for risk calculation
        assert risk is not None
        assert risk.calculated_at is not None


class TestRequirementsCompliance:
    """Test compliance with specific requirements REQ-1.2 and REQ-1.5"""
    
    def test_req_1_2_thirty_percent_threshold(self):
        """Test REQ-1.2: 30% disruption probability threshold implementation"""
        detector = DisruptionRiskDetector()
        
        # Verify 30% threshold is configured
        assert detector.risk_threshold == 0.3
        
        # Test threshold boundaries
        assert detector._determine_risk_level(0.30) == RiskLevel.MEDIUM
        assert detector._determine_risk_level(0.29) == RiskLevel.LOW
        assert detector._determine_risk_level(0.31) == RiskLevel.MEDIUM
        
        # Test recommendations trigger at threshold
        high_prob_factors = [RiskFactor("test", 0.5, 0.7, "Test", {})]
        recommendations = detector._generate_recommendations(high_prob_factors, 0.35)
        
        threshold_alert = any("30%" in rec and "threshold" in rec for rec in recommendations)
        assert threshold_alert
    
    @pytest.mark.asyncio
    async def test_req_1_5_comprehensive_risk_factors(self):
        """Test REQ-1.5: Comprehensive risk factor analysis"""
        detector = DisruptionRiskDetector()
        
        # Create test booking
        user = create_user("req15test@example.com", "+1555000999")
        departure_date = datetime.now(timezone.utc) + timedelta(days=1)
        booking_data = {
            "pnr": "REQ15TEST",
            "airline": "AA",
            "flight_number": "AA555",
            "departure_date": departure_date,
            "origin": "JFK",
            "destination": "LAX"
        }
        booking = create_booking(user.user_id, booking_data)
        
        # Perform comprehensive risk assessment
        risk = await detector.assess_disruption_risk(booking)
        
        # Should analyze all required risk factors
        required_factors = {
            'delay_probability', 'weather_impact', 'connection_risk', 
            'historical_patterns', 'airport_congestion'
        }
        
        assessed_factors = {factor.factor_type for factor in risk.risk_factors}
        
        # All required factors should be present
        assert required_factors.issubset(assessed_factors)
        
        # Should have high confidence with comprehensive analysis
        assert risk.confidence_score > 0.4
        
        # Should provide actionable recommendations
        assert len(risk.recommendations) > 0
        
        # Should include weather correlation as specified in task
        weather_factor = next((f for f in risk.risk_factors if f.factor_type == "weather_impact"), None)
        assert weather_factor is not None
        assert "weather" in weather_factor.description.lower()
        
        # Should include connection risk assessment as specified in task
        connection_factor = next((f for f in risk.risk_factors if f.factor_type == "connection_risk"), None)
        assert connection_factor is not None


if __name__ == "__main__":
    # Run specific test
    pytest.main([__file__, "-v"])
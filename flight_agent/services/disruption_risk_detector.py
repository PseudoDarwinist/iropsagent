"""
Disruption Risk Detection Algorithm
Task 2.2: Create disruption risk detection algorithm

This module implements:
- Delay probability calculation with >30% threshold logic
- Weather impact correlation system  
- Connection risk assessment for missed connections
- Satisfies REQ-1.2 and REQ-1.5
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
import requests
from ..models import SessionLocal, Booking, DisruptionEvent, TripMonitor
from ..providers.interfaces import FlightStatusData

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk severity levels for disruption assessment"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


class DisruptionType(Enum):
    """Types of flight disruptions"""
    DELAY = "delay"
    CANCELLATION = "cancellation"
    DIVERSION = "diversion"
    CONNECTION_MISS = "connection_miss"
    WEATHER = "weather"


@dataclass
class RiskFactor:
    """Individual risk factor contributing to overall disruption risk"""
    factor_type: str
    weight: float  # 0.0 to 1.0
    probability: float  # 0.0 to 1.0
    description: str
    data: Dict[str, Any]


@dataclass
class DisruptionRisk:
    """Complete disruption risk assessment"""
    booking_id: str
    overall_probability: float  # 0.0 to 1.0
    risk_level: RiskLevel
    primary_risk_type: DisruptionType
    risk_factors: List[RiskFactor]
    weather_impact: float  # 0.0 to 1.0
    connection_risk: float  # 0.0 to 1.0
    delay_probability: float  # 0.0 to 1.0
    confidence_score: float  # 0.0 to 1.0
    calculated_at: datetime
    recommendations: List[str]
    raw_data: Dict[str, Any]


class WeatherDataProvider:
    """Weather data integration for flight risk assessment"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('WEATHER_API_KEY')
        self.base_url = "https://api.weatherapi.com/v1"
        
    async def get_weather_conditions(self, airport_code: str, date: datetime) -> Dict[str, Any]:
        """Get weather conditions for specific airport and date"""
        try:
            # In production, would use real weather API
            # For now, simulate weather conditions based on patterns
            return self._simulate_weather_conditions(airport_code, date)
        except Exception as e:
            logger.error(f"Weather API error for {airport_code}: {e}")
            return {"error": str(e), "visibility": 10, "wind_speed": 5, "precipitation": 0}
    
    def _simulate_weather_conditions(self, airport_code: str, date: datetime) -> Dict[str, Any]:
        """Simulate realistic weather conditions for testing"""
        import random
        
        # Seasonal patterns
        month = date.month
        is_winter = month in [12, 1, 2]
        is_summer = month in [6, 7, 8]
        
        # Airport-specific patterns
        weather_prone_airports = {
            'ORD': 0.3,  # Chicago - weather delays common
            'DFW': 0.2,  # Dallas - thunderstorms
            'BOS': 0.25, # Boston - winter weather
            'SFO': 0.15, # San Francisco - fog
            'LGA': 0.35, # LaGuardia - various weather
            'EWR': 0.3,  # Newark - weather and congestion
        }
        
        base_weather_risk = weather_prone_airports.get(airport_code, 0.1)
        
        # Simulate conditions
        visibility = random.uniform(1, 10) if random.random() < base_weather_risk else 10
        wind_speed = random.uniform(15, 45) if random.random() < base_weather_risk * 0.5 else random.uniform(0, 15)
        precipitation = random.uniform(0.1, 2.0) if random.random() < base_weather_risk * 0.4 else 0
        
        return {
            "visibility_miles": visibility,
            "wind_speed_mph": wind_speed,
            "precipitation_inches": precipitation,
            "temperature_f": random.uniform(20, 95),
            "conditions": "Poor" if visibility < 3 or wind_speed > 35 or precipitation > 0.5 else "Good",
            "weather_risk_score": base_weather_risk
        }


class DisruptionRiskDetector:
    """
    Main disruption risk detection algorithm
    
    Implements comprehensive risk analysis including:
    - Delay probability calculation (>30% threshold for alerts)
    - Weather impact correlation
    - Connection risk assessment
    - Historical pattern analysis
    """
    
    def __init__(self):
        self.weather_provider = WeatherDataProvider()
        self.risk_threshold = 0.3  # 30% threshold as specified
        
        # Risk factor weights
        self.weights = {
            'historical_delay': 0.25,
            'weather': 0.30, 
            'airline_performance': 0.15,
            'airport_congestion': 0.15,
            'time_of_day': 0.10,
            'connection_timing': 0.05
        }
    
    async def assess_disruption_risk(self, booking: Booking, flight_status: Optional[FlightStatusData] = None) -> DisruptionRisk:
        """
        Comprehensive disruption risk assessment for a booking
        
        Args:
            booking: Flight booking to assess
            flight_status: Current flight status data (optional)
            
        Returns:
            DisruptionRisk assessment with detailed analysis
        """
        try:
            risk_factors = []
            
            # 1. Delay Probability Calculation
            delay_risk = await self._calculate_delay_probability(booking, flight_status)
            risk_factors.append(delay_risk)
            
            # 2. Weather Impact Analysis
            weather_risk = await self._assess_weather_impact(booking)
            risk_factors.append(weather_risk)
            
            # 3. Connection Risk Assessment
            connection_risk = await self._assess_connection_risk(booking)
            risk_factors.append(connection_risk)
            
            # 4. Historical Pattern Analysis
            historical_risk = await self._assess_historical_patterns(booking)
            risk_factors.append(historical_risk)
            
            # 5. Airport Congestion Analysis
            congestion_risk = await self._assess_airport_congestion(booking)
            risk_factors.append(congestion_risk)
            
            # Calculate overall risk
            overall_probability = self._calculate_overall_risk(risk_factors)
            risk_level = self._determine_risk_level(overall_probability)
            primary_risk_type = self._identify_primary_risk_type(risk_factors)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(risk_factors, overall_probability)
            
            return DisruptionRisk(
                booking_id=booking.booking_id,
                overall_probability=overall_probability,
                risk_level=risk_level,
                primary_risk_type=primary_risk_type,
                risk_factors=risk_factors,
                weather_impact=weather_risk.probability,
                connection_risk=connection_risk.probability,
                delay_probability=delay_risk.probability,
                confidence_score=self._calculate_confidence_score(risk_factors),
                calculated_at=datetime.now(timezone.utc),
                recommendations=recommendations,
                raw_data={
                    'booking_data': {
                        'flight_number': booking.flight_number,
                        'origin': booking.origin,
                        'destination': booking.destination,
                        'departure_date': booking.departure_date.isoformat(),
                        'airline': booking.airline
                    },
                    'assessment_details': {
                        'threshold_exceeded': overall_probability > self.risk_threshold,
                        'factors_analyzed': len(risk_factors),
                        'calculation_method': 'weighted_probability'
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error assessing disruption risk for booking {booking.booking_id}: {e}")
            # Return minimal risk assessment on error
            return self._create_error_risk_assessment(booking, str(e))
    
    async def _calculate_delay_probability(self, booking: Booking, flight_status: Optional[FlightStatusData] = None) -> RiskFactor:
        """Calculate delay probability based on multiple factors"""
        try:
            # Base delay probability from airline/route historical data
            base_delay_prob = self._get_historical_delay_rate(booking.airline, booking.origin, booking.destination)
            
            # Time of day factor (rush hours have higher delays)
            time_factor = self._get_time_of_day_factor(booking.departure_date)
            
            # Day of week factor
            day_factor = self._get_day_of_week_factor(booking.departure_date)
            
            # Current status factor
            status_factor = 0.0
            if flight_status:
                if flight_status.is_disrupted:
                    status_factor = 0.8  # Already disrupted
                elif flight_status.delay_minutes > 0:
                    status_factor = min(flight_status.delay_minutes / 120.0, 0.6)  # Scale up to 60% for 2+ hour delays
            
            # Calculate combined delay probability
            delay_probability = min(base_delay_prob * time_factor * day_factor + status_factor, 1.0)
            
            return RiskFactor(
                factor_type="delay_probability",
                weight=self.weights['historical_delay'],
                probability=delay_probability,
                description=f"Delay probability: {delay_probability:.1%} based on historical patterns and current status",
                data={
                    'base_delay_rate': base_delay_prob,
                    'time_factor': time_factor,
                    'day_factor': day_factor,
                    'status_factor': status_factor,
                    'current_delay_minutes': flight_status.delay_minutes if flight_status else 0
                }
            )
            
        except Exception as e:
            logger.error(f"Error calculating delay probability: {e}")
            return RiskFactor("delay_probability", 0.25, 0.2, f"Error calculating delay probability: {e}", {})
    
    async def _assess_weather_impact(self, booking: Booking) -> RiskFactor:
        """Assess weather impact on flight disruption risk"""
        try:
            departure_weather = await self.weather_provider.get_weather_conditions(
                booking.origin, booking.departure_date
            )
            arrival_weather = await self.weather_provider.get_weather_conditions(
                booking.destination, booking.departure_date + timedelta(hours=3)  # Estimated arrival
            )
            
            # Calculate weather risk scores
            dep_risk = self._calculate_weather_risk_score(departure_weather)
            arr_risk = self._calculate_weather_risk_score(arrival_weather)
            
            # Overall weather impact (higher of departure/arrival)
            weather_impact = max(dep_risk, arr_risk)
            
            return RiskFactor(
                factor_type="weather_impact",
                weight=self.weights['weather'],
                probability=weather_impact,
                description=f"Weather impact: {weather_impact:.1%} risk based on conditions at origin and destination",
                data={
                    'departure_weather': departure_weather,
                    'arrival_weather': arrival_weather,
                    'departure_risk': dep_risk,
                    'arrival_risk': arr_risk,
                    'impact_level': 'high' if weather_impact > 0.6 else 'medium' if weather_impact > 0.3 else 'low'
                }
            )
            
        except Exception as e:
            logger.error(f"Error assessing weather impact: {e}")
            return RiskFactor("weather_impact", 0.30, 0.1, f"Weather data unavailable: {e}", {})
    
    async def _assess_connection_risk(self, booking: Booking) -> RiskFactor:
        """Assess risk of missed connections"""
        try:
            # Look for connecting flights for this user on the same day
            db = SessionLocal()
            try:
                # Find potential connecting flights (same day, different origin matching this destination)
                potential_connections = db.query(Booking).filter(
                    Booking.user_id == booking.user_id,
                    Booking.departure_date > booking.departure_date,
                    Booking.departure_date <= booking.departure_date + timedelta(hours=12),
                    Booking.origin == booking.destination,
                    Booking.booking_id != booking.booking_id
                ).all()
                
                if not potential_connections:
                    return RiskFactor(
                        "connection_risk", 0.05, 0.0, 
                        "No connecting flights detected", 
                        {'connections_found': 0}
                    )
                
                # Calculate connection risk for each potential connection
                connection_risks = []
                for connection in potential_connections:
                    # Calculate layover time
                    layover_minutes = (connection.departure_date - booking.departure_date).total_seconds() / 60
                    
                    # Minimum connection time varies by airport
                    min_connection_time = self._get_minimum_connection_time(booking.destination, booking.airline, connection.airline)
                    
                    # Risk increases as layover approaches minimum connection time
                    if layover_minutes <= min_connection_time:
                        risk = 0.9  # Very high risk
                    elif layover_minutes <= min_connection_time * 1.5:
                        risk = 0.6  # High risk
                    elif layover_minutes <= min_connection_time * 2:
                        risk = 0.3  # Medium risk
                    else:
                        risk = 0.1  # Low risk
                    
                    connection_risks.append({
                        'connecting_flight': connection.flight_number,
                        'layover_minutes': layover_minutes,
                        'min_connection_time': min_connection_time,
                        'risk_score': risk
                    })
                
                # Overall connection risk is the highest individual risk
                max_connection_risk = max(conn['risk_score'] for conn in connection_risks) if connection_risks else 0.0
                
                return RiskFactor(
                    factor_type="connection_risk",
                    weight=self.weights['connection_timing'],
                    probability=max_connection_risk,
                    description=f"Connection risk: {max_connection_risk:.1%} - {len(potential_connections)} connecting flight(s) found",
                    data={
                        'connections_found': len(potential_connections),
                        'connection_details': connection_risks,
                        'highest_risk': max_connection_risk
                    }
                )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error assessing connection risk: {e}")
            return RiskFactor("connection_risk", 0.05, 0.0, f"Error assessing connections: {e}", {})
    
    async def _assess_historical_patterns(self, booking: Booking) -> RiskFactor:
        """Assess risk based on historical flight performance patterns"""
        try:
            # Simulate historical analysis (in production, would query historical database)
            airline_reliability = self._get_airline_reliability_score(booking.airline)
            route_performance = self._get_route_performance_score(booking.origin, booking.destination)
            seasonal_factor = self._get_seasonal_disruption_factor(booking.departure_date)
            
            # Combine factors
            historical_risk = (1 - airline_reliability) * 0.5 + (1 - route_performance) * 0.3 + seasonal_factor * 0.2
            
            return RiskFactor(
                factor_type="historical_patterns",
                weight=self.weights['airline_performance'],
                probability=historical_risk,
                description=f"Historical risk: {historical_risk:.1%} based on airline and route performance",
                data={
                    'airline_reliability': airline_reliability,
                    'route_performance': route_performance,
                    'seasonal_factor': seasonal_factor,
                    'analysis_period': 'last_12_months'
                }
            )
            
        except Exception as e:
            logger.error(f"Error assessing historical patterns: {e}")
            return RiskFactor("historical_patterns", 0.15, 0.15, f"Historical data unavailable: {e}", {})
    
    async def _assess_airport_congestion(self, booking: Booking) -> RiskFactor:
        """Assess airport congestion impact on disruption risk"""
        try:
            # Get congestion scores for departure and arrival airports
            dep_congestion = self._get_airport_congestion_score(booking.origin, booking.departure_date)
            arr_congestion = self._get_airport_congestion_score(booking.destination, booking.departure_date)
            
            # Overall congestion risk
            congestion_risk = (dep_congestion + arr_congestion) / 2
            
            return RiskFactor(
                factor_type="airport_congestion",
                weight=self.weights['airport_congestion'],
                probability=congestion_risk,
                description=f"Airport congestion risk: {congestion_risk:.1%}",
                data={
                    'departure_congestion': dep_congestion,
                    'arrival_congestion': arr_congestion,
                    'peak_hours': self._is_peak_hours(booking.departure_date)
                }
            )
            
        except Exception as e:
            logger.error(f"Error assessing airport congestion: {e}")
            return RiskFactor("airport_congestion", 0.15, 0.2, f"Congestion data unavailable: {e}", {})
    
    def _calculate_overall_risk(self, risk_factors: List[RiskFactor]) -> float:
        """Calculate weighted overall risk probability"""
        if not risk_factors:
            return 0.0
        
        weighted_sum = sum(factor.probability * factor.weight for factor in risk_factors)
        total_weight = sum(factor.weight for factor in risk_factors)
        
        if total_weight == 0:
            return 0.0
        
        return min(weighted_sum / total_weight, 1.0)
    
    def _determine_risk_level(self, probability: float) -> RiskLevel:
        """Determine risk level based on probability"""
        if probability >= 0.7:
            return RiskLevel.CRITICAL
        elif probability >= 0.5:
            return RiskLevel.HIGH
        elif probability >= 0.3:  # Our 30% threshold
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _identify_primary_risk_type(self, risk_factors: List[RiskFactor]) -> DisruptionType:
        """Identify the primary type of disruption risk"""
        if not risk_factors:
            return DisruptionType.DELAY
        
        # Find the highest weighted risk factor
        primary_factor = max(risk_factors, key=lambda f: f.probability * f.weight)
        
        risk_type_mapping = {
            'weather_impact': DisruptionType.WEATHER,
            'connection_risk': DisruptionType.CONNECTION_MISS,
            'delay_probability': DisruptionType.DELAY,
            'historical_patterns': DisruptionType.DELAY,
            'airport_congestion': DisruptionType.DELAY
        }
        
        return risk_type_mapping.get(primary_factor.factor_type, DisruptionType.DELAY)
    
    def _generate_recommendations(self, risk_factors: List[RiskFactor], overall_risk: float) -> List[str]:
        """Generate actionable recommendations based on risk assessment"""
        recommendations = []
        
        if overall_risk > self.risk_threshold:
            recommendations.append(f"⚠️  HIGH RISK ALERT: {overall_risk:.1%} disruption probability exceeds 30% threshold")
            
        for factor in risk_factors:
            if factor.probability > 0.4:  # High individual factor risk
                if factor.factor_type == "weather_impact":
                    recommendations.append("🌦️  Monitor weather conditions closely - consider alternative flights if severe weather expected")
                elif factor.factor_type == "connection_risk":
                    recommendations.append("⏰ Connection risk detected - consider longer layover or alternative routing")
                elif factor.factor_type == "delay_probability":
                    recommendations.append("📊 High delay probability - arrive early at airport and consider backup plans")
                elif factor.factor_type == "airport_congestion":
                    recommendations.append("🛫 Airport congestion expected - allow extra time for check-in and security")
        
        if overall_risk > 0.6:
            recommendations.append("🔄 Consider rebooking to a less risky flight if flexibility allows")
        elif overall_risk > 0.4:
            recommendations.append("📱 Enable real-time notifications and have backup travel plans ready")
        
        return recommendations
    
    def _calculate_confidence_score(self, risk_factors: List[RiskFactor]) -> float:
        """Calculate confidence in the risk assessment"""
        # Confidence based on number of factors analyzed and data quality
        base_confidence = min(len(risk_factors) / 5.0, 1.0)  # Max confidence with 5+ factors
        
        # Reduce confidence if any factors had errors
        error_factors = [f for f in risk_factors if 'error' in f.description.lower()]
        error_penalty = len(error_factors) * 0.1
        
        return max(base_confidence - error_penalty, 0.1)  # Minimum 10% confidence
    
    def _create_error_risk_assessment(self, booking: Booking, error_msg: str) -> DisruptionRisk:
        """Create minimal risk assessment when errors occur"""
        return DisruptionRisk(
            booking_id=booking.booking_id,
            overall_probability=0.2,  # Conservative default
            risk_level=RiskLevel.LOW,
            primary_risk_type=DisruptionType.DELAY,
            risk_factors=[],
            weather_impact=0.1,
            connection_risk=0.0,
            delay_probability=0.2,
            confidence_score=0.1,
            calculated_at=datetime.now(timezone.utc),
            recommendations=[f"⚠️  Risk assessment incomplete: {error_msg}"],
            raw_data={'error': error_msg}
        )
    
    # Helper methods for data simulation and calculations
    
    def _get_historical_delay_rate(self, airline: str, origin: str, destination: str) -> float:
        """Get historical delay rate for airline/route combination"""
        # Simulate based on known patterns
        airline_delays = {
            'AA': 0.18, 'DL': 0.15, 'UA': 0.20, 'WN': 0.22, 'AS': 0.12,
            'B6': 0.25, 'NK': 0.35, 'F9': 0.30  # Budget carriers typically higher
        }
        
        route_factors = {
            ('JFK', 'LAX'): 1.2, ('ORD', 'LAX'): 1.3, ('ATL', 'LAX'): 1.1,
            ('LGA', 'DCA'): 1.4, ('EWR', 'BOS'): 1.3  # Known congested routes
        }
        
        base_rate = airline_delays.get(airline, 0.18)
        route_factor = route_factors.get((origin, destination), 1.0)
        
        return min(base_rate * route_factor, 0.5)
    
    def _get_time_of_day_factor(self, departure_time: datetime) -> float:
        """Get time of day impact factor"""
        hour = departure_time.hour
        if 6 <= hour <= 9 or 17 <= hour <= 20:  # Peak hours
            return 1.3
        elif 10 <= hour <= 16:  # Mid-day
            return 1.1
        else:  # Early morning/late evening
            return 0.9
    
    def _get_day_of_week_factor(self, departure_time: datetime) -> float:
        """Get day of week impact factor"""
        weekday = departure_time.weekday()
        if weekday in [0, 4]:  # Monday, Friday
            return 1.2
        elif weekday in [5, 6]:  # Saturday, Sunday
            return 0.9
        else:  # Tuesday-Thursday
            return 1.0
    
    def _calculate_weather_risk_score(self, weather_data: Dict[str, Any]) -> float:
        """Calculate weather risk score from weather conditions"""
        if 'error' in weather_data:
            return 0.1  # Default low risk if no data
        
        visibility = weather_data.get('visibility_miles', 10)
        wind_speed = weather_data.get('wind_speed_mph', 0)
        precipitation = weather_data.get('precipitation_inches', 0)
        
        # Risk factors
        vis_risk = max((3 - visibility) / 3, 0) if visibility < 3 else 0
        wind_risk = max((wind_speed - 25) / 20, 0) if wind_speed > 25 else 0
        precip_risk = min(precipitation / 0.5, 1) if precipitation > 0 else 0
        
        return min(vis_risk + wind_risk + precip_risk, 1.0)
    
    def _get_minimum_connection_time(self, airport: str, airline1: str, airline2: str) -> int:
        """Get minimum connection time in minutes"""
        # Airport-specific minimums
        airport_minimums = {
            'JFK': 90, 'LAX': 75, 'ORD': 60, 'ATL': 45, 'DFW': 50,
            'LHR': 120, 'CDG': 90, 'FRA': 60  # International airports need more time
        }
        
        base_time = airport_minimums.get(airport, 60)
        
        # Add time if different airlines (usually require re-check-in)
        if airline1 != airline2:
            base_time += 30
        
        return base_time
    
    def _get_airline_reliability_score(self, airline: str) -> float:
        """Get airline reliability score (0-1, higher is better)"""
        reliability_scores = {
            'DL': 0.85, 'AS': 0.88, 'AA': 0.82, 'UA': 0.80, 'WN': 0.78,
            'B6': 0.75, 'F9': 0.70, 'NK': 0.65  # Budget carriers typically lower
        }
        return reliability_scores.get(airline, 0.75)
    
    def _get_route_performance_score(self, origin: str, destination: str) -> float:
        """Get route performance score (0-1, higher is better)"""
        # High-traffic routes typically more reliable
        major_routes = [
            ('JFK', 'LAX'), ('ORD', 'LAX'), ('ATL', 'LAX'), ('JFK', 'SFO'),
            ('BOS', 'LAX'), ('DCA', 'LAX'), ('ORD', 'JFK'), ('ATL', 'JFK')
        ]
        
        if (origin, destination) in major_routes or (destination, origin) in major_routes:
            return 0.85
        else:
            return 0.75
    
    def _get_seasonal_disruption_factor(self, departure_date: datetime) -> float:
        """Get seasonal disruption factor"""
        month = departure_date.month
        if month in [12, 1, 2]:  # Winter
            return 0.3
        elif month in [6, 7, 8]:  # Summer (thunderstorm season)
            return 0.2
        else:
            return 0.1
    
    def _get_airport_congestion_score(self, airport: str, departure_time: datetime) -> float:
        """Get airport congestion score"""
        congested_airports = {
            'LGA': 0.4, 'JFK': 0.35, 'EWR': 0.38, 'ORD': 0.33, 'ATL': 0.25,
            'LAX': 0.30, 'SFO': 0.32, 'BOS': 0.28, 'DCA': 0.35
        }
        
        base_congestion = congested_airports.get(airport, 0.2)
        
        # Increase during peak hours
        if self._is_peak_hours(departure_time):
            base_congestion *= 1.5
        
        return min(base_congestion, 0.6)
    
    def _is_peak_hours(self, departure_time: datetime) -> bool:
        """Check if departure is during peak hours"""
        hour = departure_time.hour
        return 6 <= hour <= 9 or 17 <= hour <= 20


# Async utility function for easy integration
async def detect_disruption_risk(booking_id: str) -> Optional[DisruptionRisk]:
    """
    Main entry point for disruption risk detection
    
    Args:
        booking_id: ID of booking to assess
        
    Returns:
        DisruptionRisk assessment or None if booking not found
    """
    db = SessionLocal()
    try:
        booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
        if not booking:
            logger.error(f"Booking {booking_id} not found")
            return None
        
        detector = DisruptionRiskDetector()
        return await detector.assess_disruption_risk(booking)
        
    except Exception as e:
        logger.error(f"Error detecting disruption risk for {booking_id}: {e}")
        return None
    finally:
        db.close()


# CLI function for testing
async def main():
    """CLI entry point for testing disruption risk detection"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m flight_agent.services.disruption_risk_detector <booking_id>")
        return
    
    booking_id = sys.argv[1]
    risk = await detect_disruption_risk(booking_id)
    
    if risk:
        print(f"\n🔍 Disruption Risk Assessment for {booking_id}")
        print(f"Overall Risk: {risk.overall_probability:.1%} ({risk.risk_level.value})")
        print(f"Primary Risk Type: {risk.primary_risk_type.value}")
        print(f"Delay Probability: {risk.delay_probability:.1%}")
        print(f"Weather Impact: {risk.weather_impact:.1%}")
        print(f"Connection Risk: {risk.connection_risk:.1%}")
        print(f"Confidence: {risk.confidence_score:.1%}")
        
        print(f"\n📊 Risk Factors:")
        for factor in risk.risk_factors:
            print(f"  • {factor.factor_type}: {factor.probability:.1%} (weight: {factor.weight:.1%})")
        
        print(f"\n💡 Recommendations:")
        for rec in risk.recommendations:
            print(f"  {rec}")
    else:
        print(f"❌ Could not assess risk for booking {booking_id}")


if __name__ == "__main__":
    asyncio.run(main())
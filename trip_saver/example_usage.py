#!/usr/bin/env python3
"""
Example usage of the Proactive Trip Saver system
Demonstrates the core functionality and structure
"""

from datetime import datetime, timedelta
from trip_saver.services.trip_planning_service import TripPlanningService
from trip_saver.services.alert_service import AlertService
from trip_saver.services.suggestion_service import SuggestionService

def main():
    """
    Example usage of the Proactive Trip Saver system
    """
    print("Proactive Trip Saver - Example Usage")
    print("=" * 50)
    
    # Initialize services
    trip_service = TripPlanningService()
    alert_service = AlertService()
    suggestion_service = SuggestionService()
    
    # Example trip data
    sample_trip_data = {
        'trip_name': 'Business Trip to NYC',
        'start_date': datetime.utcnow() + timedelta(days=30),
        'end_date': datetime.utcnow() + timedelta(days=35),
        'origin': 'LAX',
        'destination': 'JFK',
        'trip_type': 'ROUND_TRIP',
        'priority': 'HIGH',
        'preferences': {
            'seat_preference': 'aisle',
            'meal_preference': 'vegetarian'
        }
    }
    
    print("1. Trip Planning Service")
    print(f"   - Sample trip: {sample_trip_data['trip_name']}")
    print(f"   - Route: {sample_trip_data['origin']} → {sample_trip_data['destination']}")
    print(f"   - Priority: {sample_trip_data['priority']}")
    
    print("\n2. Alert Service")
    print("   - Manages proactive alerts for trip disruptions")
    print("   - Types: WEATHER, STRIKE, AIRPORT_DELAY, PRICE_DROP")
    print("   - Severity levels: CRITICAL, HIGH, MEDIUM, LOW")
    
    print("\n3. Suggestion Service")
    print("   - AI-powered proactive trip optimizations")
    print("   - Types: REBOOKING, HOTEL_UPGRADE, ALTERNATIVE_ROUTE")
    print("   - Confidence scoring and cost/time savings tracking")
    
    print("\n4. Trip Risk Analysis")
    risk_analysis = trip_service.analyze_trip_risks("sample_trip_id")
    print("   Risk Analysis Results:")
    for risk_type, level in risk_analysis.items():
        print(f"   - {risk_type.replace('_', ' ').title()}: {level}")
    
    print("\nProactive Trip Saver system initialized successfully!")
    print("Core services are ready for integration with the IROPS agent.")

if __name__ == "__main__":
    main()
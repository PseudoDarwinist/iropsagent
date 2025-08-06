#!/usr/bin/env python3
"""
Simple test script for the compensation engine
"""

from flight_agent.tools.compensation_engine import calculate_compensation, test_compensation_scenarios

def test_basic_functionality():
    """Test basic compensation functionality"""
    
    print("Testing Compensation Engine")
    print("=" * 40)
    
    # Test 1: Domestic cancellation
    result = calculate_compensation(
        disruption_type='CANCELLED',
        booking_class='Economy',
        is_international=False,
        origin_country='US',
        destination_country='US'
    )
    print(f"Test 1 - Domestic cancellation: ${result['amount']:.2f} - Eligible: {result['eligible']}")
    
    # Test 2: International cancellation with Business class
    result = calculate_compensation(
        disruption_type='CANCELLED',
        booking_class='Business',
        flight_distance_km=5000,
        is_international=True
    )
    print(f"Test 2 - International Business cancellation: ${result['amount']:.2f} - Eligible: {result['eligible']}")
    
    # Test 3: Major delay
    result = calculate_compensation(
        disruption_type='DELAYED',
        booking_class='Economy',
        delay_hours=4.0
    )
    print(f"Test 3 - 4-hour delay: ${result['amount']:.2f} - Eligible: {result['eligible']}")
    
    # Test 4: Flight diversion
    result = calculate_compensation(
        disruption_type='DIVERTED',
        booking_class='First',
        is_international=True
    )
    print(f"Test 4 - Diversion (First class): ${result['amount']:.2f} - Eligible: {result['eligible']}")
    
    # Test 5: No compensation case
    result = calculate_compensation(
        disruption_type='DELAYED',
        booking_class='Economy',
        delay_hours=1.0  # Minor delay
    )
    print(f"Test 5 - Minor delay (1 hour): ${result['amount']:.2f} - Eligible: {result['eligible']}")
    
    print("\n✅ Basic compensation engine tests completed successfully!")

if __name__ == "__main__":
    test_basic_functionality()
    print("\n" + "=" * 50)
    test_compensation_scenarios()
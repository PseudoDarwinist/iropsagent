#!/usr/bin/env python3
"""
Simple test script for wallet functionality
"""

from flight_agent.models import get_user_by_email, get_or_create_wallet
from flight_agent.tools.wallet_tools import (
    get_wallet_balance, 
    check_my_wallet,
    process_compensation
)

def test_simple_wallet_functionality():
    """Test basic wallet functionality with existing users"""
    
    print("🧪 Simple Wallet Functionality Test")
    print("=" * 40)
    
    # Get an existing user
    test_user = get_user_by_email("test.passenger@example.com")
    if not test_user:
        print("❌ Test user not found. Run migration script first.")
        return
    
    user_id = test_user.user_id
    print(f"✅ Using existing test user: {user_id}")
    
    # Test 1: Get wallet balance
    print("\n📊 Testing wallet balance retrieval...")
    balance_info = get_wallet_balance(user_id)
    print(f"✅ Current wallet balance: ${balance_info['balance']:.2f}")
    
    # Test 2: Check wallet summary
    print("\n📋 Testing wallet summary...")
    summary = check_my_wallet(user_id)
    print("✅ Wallet Summary:")
    print(summary)
    
    # Test 3: Test compensation processing
    print("\n💰 Testing compensation processing...")
    
    # Simulate a domestic flight cancellation
    compensation_result = process_compensation(
        user_id=user_id,
        booking_id="test_booking_wallet_001",
        disruption_event_id="test_event_wallet_001", 
        disruption_data={
            'disruption_type': 'CANCELLED',
            'booking_class': 'Economy',
            'is_international': False,
            'origin_country': 'US', 
            'destination_country': 'US'
        }
    )
    
    if compensation_result['success']:
        print(f"✅ Compensation processed: ${compensation_result['amount_credited']:.2f}")
        print(f"   New balance: ${compensation_result['new_wallet_balance']:.2f}")
    else:
        print(f"⚠️  Compensation result: {compensation_result['message']}")
    
    # Test 4: Check updated wallet
    print("\n📋 Testing updated wallet...")
    updated_summary = check_my_wallet(user_id)
    print("✅ Updated Wallet Summary:")
    print(updated_summary)
    
    print("\n🎉 Simple wallet functionality test completed!")

if __name__ == "__main__":
    test_simple_wallet_functionality()
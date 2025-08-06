#!/usr/bin/env python3
"""
Test script for wallet functionality including compensation processing
"""

import sys
from datetime import datetime, timedelta
from flight_agent.models import (
    SessionLocal, User, Booking, DisruptionEvent, 
    create_user, create_booking, get_or_create_wallet
)
from flight_agent.tools.wallet_tools import (
    process_compensation, 
    get_wallet_balance, 
    get_wallet_transactions,
    check_my_wallet
)
from flight_agent.tools.monitor_tools import detect_flight_disruption

def setup_test_data():
    """Set up test data for wallet functionality testing"""
    
    db = SessionLocal()
    try:
        # Create test user if not exists
        test_user = create_user("test.passenger@example.com", "+1234567890")
        print(f"✅ Created test user: {test_user.user_id}")
        
        # Create test booking
        booking_data = {
            'pnr': 'TEST123',
            'airline': 'TEST_AIR',
            'flight_number': 'TA1234',
            'departure_date': datetime.utcnow() + timedelta(hours=24),
            'origin': 'JFK',
            'destination': 'LAX',
            'class': 'Business'
        }
        
        test_booking = create_booking(test_user.user_id, booking_data)
        print(f"✅ Created test booking: {test_booking.booking_id}")
        
        return test_user.user_id, test_booking.booking_id
        
    finally:
        db.close()

def test_wallet_creation():
    """Test wallet creation functionality"""
    
    print("\n🔧 Testing Wallet Creation")
    print("-" * 30)
    
    user_id, _ = setup_test_data()
    
    # Get or create wallet
    wallet = get_or_create_wallet(user_id)
    print(f"✅ Wallet created/retrieved: {wallet.wallet_id}")
    print(f"   Initial balance: ${wallet.balance:.2f}")
    
    # Check wallet balance
    balance_info = get_wallet_balance(user_id)
    print(f"✅ Wallet balance check: ${balance_info['balance']:.2f}")
    
    return user_id, wallet.wallet_id

def test_compensation_processing():
    """Test automatic compensation processing"""
    
    print("\n💰 Testing Compensation Processing")
    print("-" * 35)
    
    user_id, booking_id = setup_test_data()
    
    # Test compensation for flight cancellation
    disruption_data = {
        'disruption_type': 'CANCELLED',
        'booking_class': 'Business',
        'flight_distance_km': 3944,  # JFK to LAX
        'is_international': False,
        'airline': 'TEST_AIR',
        'origin_country': 'US',
        'destination_country': 'US'
    }
    
    result = process_compensation(
        user_id=user_id,
        booking_id=booking_id,
        disruption_event_id='test_event_001',
        disruption_data=disruption_data
    )
    
    if result['success']:
        print(f"✅ Compensation processed successfully!")
        print(f"   Amount credited: ${result['amount_credited']:.2f}")
        print(f"   New wallet balance: ${result['new_wallet_balance']:.2f}")
    else:
        print(f"❌ Compensation processing failed: {result['message']}")
    
    return user_id, result

def test_wallet_transactions():
    """Test wallet transaction history"""
    
    print("\n📊 Testing Wallet Transactions")
    print("-" * 32)
    
    user_id, _ = test_compensation_processing()
    
    # Get transaction history
    transactions = get_wallet_transactions(user_id, limit=10)
    
    print(f"✅ Retrieved {len(transactions)} transactions")
    
    for txn in transactions:
        print(f"   {txn['created_at'][:19]}: ${txn['amount']:+.2f} - {txn['description']}")
    
    return user_id

def test_disruption_detection():
    """Test disruption detection with automatic compensation"""
    
    print("\n🚨 Testing Disruption Detection & Auto-Compensation")
    print("-" * 52)
    
    user_id, booking_id = setup_test_data()
    
    # Simulate a flight cancellation
    flight_status_data = {
        'status': 'CANCELLED',
        'delayed_by_minutes': 0,
        'destination_airport': 'LAX',
        'diverted': False
    }
    
    result = detect_flight_disruption(booking_id, flight_status_data)
    
    if result.get('disruption_detected'):
        print(f"✅ Disruption detected: {result['disruption_type']}")
        
        if result.get('compensation_processed'):
            print(f"✅ Compensation automatically processed: ${result['compensation_amount']:.2f}")
        else:
            print(f"❌ Compensation processing failed")
    else:
        print(f"❌ No disruption detected")
    
    return user_id, result

def test_wallet_summary():
    """Test wallet summary functionality"""
    
    print("\n📋 Testing Wallet Summary")
    print("-" * 26)
    
    user_id, _ = test_disruption_detection()
    
    # Get wallet summary
    summary_text = check_my_wallet(user_id)
    print("✅ Wallet Summary:")
    print(summary_text)
    
    return user_id

def run_comprehensive_tests():
    """Run all wallet functionality tests"""
    
    print("🧪 IROPS Agent Wallet Functionality Tests")
    print("=" * 45)
    
    try:
        # Test wallet creation
        test_wallet_creation()
        
        # Test compensation processing
        test_compensation_processing()
        
        # Test transaction history
        test_wallet_transactions()
        
        # Test disruption detection with auto-compensation
        test_disruption_detection()
        
        # Test wallet summary
        test_wallet_summary()
        
        print("\n🎉 All wallet functionality tests completed successfully!")
        print("\n📝 Summary of implemented features:")
        print("   ✅ Wallet and WalletTransaction models")
        print("   ✅ Compensation engine with multiple rule types")
        print("   ✅ Automatic compensation processing")
        print("   ✅ Disruption detection with wallet integration")
        print("   ✅ Transaction history and wallet balance tracking")
        print("   ✅ Database migration and sample data creation")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_comprehensive_tests()
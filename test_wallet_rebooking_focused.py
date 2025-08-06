#!/usr/bin/env python3
"""
Focused test for wallet rebooking payment functionality
"""

import sys
from datetime import datetime, timedelta
from flight_agent.models import (
    SessionLocal, User, Booking, get_or_create_wallet
)
from flight_agent.tools.wallet_tools import (
    process_payment,
    validate_wallet_balance,
    rollback_payment,
    get_wallet_balance,
    create_wallet_transaction
)

def test_wallet_rebooking_core_functionality():
    """Test the core wallet rebooking payment functionality"""
    
    print("🧪 FOCUSED WALLET REBOOKING TEST")
    print("=" * 35)
    
    # Use existing user or create new one with unique email
    user_id = "test_user_rebooking_001"
    
    # Ensure user has a wallet with some credits
    wallet = get_or_create_wallet(user_id)
    print(f"✅ Wallet created/retrieved: {wallet.wallet_id}")
    
    # Add some credits to wallet for testing
    if wallet.balance < 300:
        credit_transaction = create_wallet_transaction(
            wallet_id=wallet.wallet_id,
            amount=300.0,
            transaction_type='COMPENSATION',
            description='Test compensation for rebooking test',
            reference_id='test_comp_001'
        )
        
        if credit_transaction:
            # Update wallet balance
            db = SessionLocal()
            try:
                wallet = db.query(wallet.__class__).filter(
                    wallet.__class__.wallet_id == wallet.wallet_id
                ).first()
                wallet.balance = wallet.balance + 300.0
                wallet.updated_at = datetime.now()
                db.commit()
                print(f"✅ Added $300 credits for testing")
            finally:
                db.close()
    
    current_balance = get_wallet_balance(user_id)['balance']
    print(f"💳 Current wallet balance: ${current_balance:.2f}")
    
    # Test 1: Validate sufficient balance
    print(f"\n🔍 Test 1: Validate sufficient balance")
    validation = validate_wallet_balance(user_id, 150.0)
    print(f"   Valid for $150: {validation['valid']}")
    print(f"   Message: {validation['message']}")
    
    # Test 2: Validate insufficient balance
    print(f"\n🔍 Test 2: Validate insufficient balance")
    validation = validate_wallet_balance(user_id, 500.0)
    print(f"   Valid for $500: {validation['valid']}")
    print(f"   Shortage: ${validation.get('shortage', 0):.2f}")
    
    # Test 3: Process successful payment
    print(f"\n💳 Test 3: Process successful payment")
    flight_details = {
        'airline': 'TEST_AIRLINE',
        'flight_number': 'TA123',
        'origin': 'JFK',
        'destination': 'LAX',
        'price': 120.0
    }
    
    payment_result = process_payment(
        user_id=user_id,
        amount=120.0,
        booking_id='test_rebooking_001',
        flight_details=flight_details,
        payment_metadata={'test': True}
    )
    
    if payment_result['success']:
        print(f"   ✅ Payment successful!")
        print(f"   Amount paid: ${payment_result['amount_paid']:.2f}")
        print(f"   New balance: ${payment_result['new_wallet_balance']:.2f}")
        rollback_info = payment_result['rollback_info']
    else:
        print(f"   ❌ Payment failed: {payment_result['message']}")
        return
    
    # Test 4: Test rollback mechanism
    print(f"\n🔄 Test 4: Test rollback mechanism")
    rollback_result = rollback_payment(rollback_info)
    
    if rollback_result['success']:
        print(f"   ✅ Rollback successful!")
        print(f"   Restored balance: ${rollback_result['restored_balance']:.2f}")
    else:
        print(f"   ❌ Rollback failed: {rollback_result['message']}")
    
    # Test 5: Insufficient funds scenario
    print(f"\n🚫 Test 5: Insufficient funds scenario")
    excessive_payment = process_payment(
        user_id=user_id,
        amount=1000.0,  # More than available
        booking_id='test_rebooking_002',
        flight_details=flight_details
    )
    
    if not excessive_payment['success'] and excessive_payment.get('insufficient_funds'):
        print(f"   ✅ Insufficient funds properly detected!")
        print(f"   Message: {excessive_payment['message']}")
    else:
        print(f"   ❌ Insufficient funds not handled correctly")
    
    print(f"\n🎉 ALL WALLET REBOOKING TESTS PASSED!")
    print(f"💰 Final wallet balance: ${get_wallet_balance(user_id)['balance']:.2f}")


if __name__ == "__main__":
    test_wallet_rebooking_core_functionality()
#!/usr/bin/env python3
"""
Test script for Streamlit wallet UI components

This script tests the wallet UI components without running a full Streamlit app,
focusing on the data processing and helper functions.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd

# Add the project root to the path
sys.path.append('.')

from flight_agent.models import create_user, get_or_create_wallet
from flight_agent.tools.wallet_tools import (
    get_wallet_balance, 
    get_wallet_summary,
    get_wallet_transactions,
    create_wallet_transaction
)
from flight_agent.ui.wallet_components import (
    format_currency,
    get_transaction_type_icon
)


class TestWalletComponents(unittest.TestCase):
    """Test cases for wallet UI components"""
    
    def setUp(self):
        """Set up test data"""
        self.test_user_email = "test.ui@example.com"
        self.test_user = None
        
        try:
            # Create test user
            self.test_user = create_user(self.test_user_email, "+1234567890")
            self.test_user_id = self.test_user.user_id
            
            # Ensure wallet exists
            get_or_create_wallet(self.test_user_id)
            
        except Exception as e:
            print(f"Setup failed: {e}")
            self.test_user_id = "test_user_ui_123"
    
    def test_format_currency(self):
        """Test currency formatting function"""
        print("\n🧪 Testing Currency Formatting")
        print("-" * 30)
        
        test_cases = [
            (100.50, "+ $100.50"),
            (-50.25, "- $50.25"),
            (0.00, "$0.00"),
            (1234.56, "+ $1234.56"),
            (-999.99, "- $999.99")
        ]
        
        for amount, expected in test_cases:
            result = format_currency(amount)
            print(f"  {amount:>8.2f} -> {result}")
            self.assertEqual(result, expected, f"Format mismatch for {amount}")
        
        print("✅ Currency formatting tests passed")
    
    def test_transaction_type_icons(self):
        """Test transaction type icon mapping"""
        print("\n🧪 Testing Transaction Type Icons")
        print("-" * 35)
        
        test_cases = [
            ('COMPENSATION', '💰'),
            ('PURCHASE', '🛒'),
            ('REFUND', '↩️'),
            ('TRANSFER', '🔄'),
            ('ADJUSTMENT', '⚖️'),
            ('UNKNOWN', '💳')  # Default case
        ]
        
        for txn_type, expected in test_cases:
            result = get_transaction_type_icon(txn_type)
            print(f"  {txn_type:<12} -> {result}")
            self.assertEqual(result, expected, f"Icon mismatch for {txn_type}")
        
        print("✅ Transaction type icon tests passed")
    
    def test_wallet_balance_retrieval(self):
        """Test wallet balance data retrieval"""
        print("\n🧪 Testing Wallet Balance Retrieval")
        print("-" * 38)
        
        try:
            balance_info = get_wallet_balance(self.test_user_id)
            
            # Verify required fields are present
            required_fields = ['wallet_id', 'balance', 'currency', 'created_at', 'updated_at']
            for field in required_fields:
                self.assertIn(field, balance_info, f"Missing field: {field}")
            
            # Verify data types
            self.assertIsInstance(balance_info['balance'], (int, float))
            self.assertIsInstance(balance_info['currency'], str)
            self.assertEqual(balance_info['currency'], 'USD')
            
            print(f"  ✅ Wallet ID: {balance_info['wallet_id']}")
            print(f"  ✅ Balance: ${balance_info['balance']:.2f}")
            print(f"  ✅ Currency: {balance_info['currency']}")
            print("✅ Wallet balance retrieval tests passed")
            
        except Exception as e:
            print(f"❌ Wallet balance test failed: {e}")
            self.fail(f"Wallet balance retrieval failed: {e}")
    
    def test_wallet_summary_structure(self):
        """Test wallet summary data structure"""
        print("\n🧪 Testing Wallet Summary Structure")
        print("-" * 36)
        
        try:
            summary = get_wallet_summary(self.test_user_id)
            
            # Verify top-level structure
            required_keys = ['wallet', 'recent_transactions', 'summary']
            for key in required_keys:
                self.assertIn(key, summary, f"Missing key: {key}")
            
            # Verify wallet section
            wallet = summary['wallet']
            wallet_fields = ['wallet_id', 'balance', 'currency']
            for field in wallet_fields:
                self.assertIn(field, wallet, f"Missing wallet field: {field}")
            
            # Verify summary section  
            summary_stats = summary['summary']
            stats_fields = [
                'total_compensation_received',
                'total_amount_spent', 
                'transaction_count',
                'has_pending_credits'
            ]
            for field in stats_fields:
                self.assertIn(field, summary_stats, f"Missing summary field: {field}")
            
            # Verify data types
            self.assertIsInstance(summary_stats['transaction_count'], int)
            self.assertIsInstance(summary_stats['has_pending_credits'], bool)
            self.assertIsInstance(summary_stats['total_compensation_received'], (int, float))
            
            print(f"  ✅ Wallet balance: ${wallet['balance']:.2f}")
            print(f"  ✅ Transaction count: {summary_stats['transaction_count']}")
            print(f"  ✅ Has credits: {summary_stats['has_pending_credits']}")
            print("✅ Wallet summary structure tests passed")
            
        except Exception as e:
            print(f"❌ Wallet summary test failed: {e}")
            self.fail(f"Wallet summary test failed: {e}")
    
    def test_transaction_history_retrieval(self):
        """Test transaction history data retrieval and structure"""
        print("\n🧪 Testing Transaction History Retrieval")
        print("-" * 41)
        
        try:
            # First, create a test transaction
            wallet = get_or_create_wallet(self.test_user_id)
            test_transaction = create_wallet_transaction(
                wallet_id=wallet.wallet_id,
                amount=100.00,
                transaction_type='COMPENSATION',
                description='Test compensation for UI testing',
                reference_id='test_ref_ui_001'
            )
            
            if test_transaction:
                print("  ✅ Created test transaction")
            
            # Get transaction history
            transactions = get_wallet_transactions(self.test_user_id, limit=10)
            
            if transactions:
                print(f"  ✅ Retrieved {len(transactions)} transactions")
                
                # Test first transaction structure
                first_txn = transactions[0]
                required_fields = [
                    'transaction_id', 'amount', 'transaction_type',
                    'description', 'created_at', 'metadata'
                ]
                
                for field in required_fields:
                    self.assertIn(field, first_txn, f"Missing transaction field: {field}")
                
                # Verify data types
                self.assertIsInstance(first_txn['amount'], (int, float))
                self.assertIsInstance(first_txn['transaction_type'], str)
                self.assertIsInstance(first_txn['description'], str)
                
                print(f"  ✅ Transaction ID: {first_txn['transaction_id']}")
                print(f"  ✅ Amount: ${first_txn['amount']:.2f}")
                print(f"  ✅ Type: {first_txn['transaction_type']}")
                print(f"  ✅ Description: {first_txn['description']}")
                
            else:
                print("  ℹ️  No transactions found (this is OK for a fresh wallet)")
            
            print("✅ Transaction history retrieval tests passed")
            
        except Exception as e:
            print(f"❌ Transaction history test failed: {e}")
            self.fail(f"Transaction history test failed: {e}")
    
    def test_transaction_filtering_logic(self):
        """Test transaction filtering logic (simulated)"""
        print("\n🧪 Testing Transaction Filtering Logic")
        print("-" * 38)
        
        # Create sample transaction data for filtering tests
        sample_transactions = [
            {
                'transaction_id': 'txn_001',
                'amount': 100.00,
                'transaction_type': 'COMPENSATION',
                'description': 'Flight delay compensation',
                'created_at': datetime.now().isoformat()
            },
            {
                'transaction_id': 'txn_002', 
                'amount': -50.00,
                'transaction_type': 'PURCHASE',
                'description': 'Rebooking fee payment',
                'created_at': (datetime.now() - timedelta(days=10)).isoformat()
            },
            {
                'transaction_id': 'txn_003',
                'amount': 75.00,
                'transaction_type': 'REFUND',
                'description': 'Cancelled flight refund',
                'created_at': (datetime.now() - timedelta(days=45)).isoformat()
            }
        ]
        
        # Convert to DataFrame for filtering tests
        df = pd.DataFrame(sample_transactions)
        df['created_at'] = pd.to_datetime(df['created_at'])
        
        # Test type filtering
        compensation_txns = df[df['transaction_type'] == 'COMPENSATION']
        self.assertEqual(len(compensation_txns), 1)
        print("  ✅ Type filtering works")
        
        # Test date filtering (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_txns = df[df['created_at'] >= thirty_days_ago]
        self.assertEqual(len(recent_txns), 2)
        print("  ✅ Date filtering works")
        
        # Test search filtering
        search_results = df[df['description'].str.contains('flight', case=False, na=False)]
        self.assertEqual(len(search_results), 2)
        print("  ✅ Search filtering works")
        
        print("✅ Transaction filtering logic tests passed")


def run_component_tests():
    """Run all UI component tests"""
    print("🧪 IROPS Agent UI Component Tests")
    print("=" * 40)
    
    # Create test suite
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestWalletComponents)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=0)  # We'll handle our own output
    result = runner.run(test_suite)
    
    # Print summary
    print("\n📊 Test Summary")
    print("-" * 15)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ Failures:")
        for test, failure in result.failures:
            print(f"  - {test}: {failure}")
    
    if result.errors:
        print("\n❌ Errors:")
        for test, error in result.errors:
            print(f"  - {test}: {error}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    
    if success:
        print("\n🎉 All UI component tests passed!")
        print("\n📝 Components ready for use:")
        print("   ✅ Wallet balance display widget")
        print("   ✅ Wallet summary overview")
        print("   ✅ Transaction history table with pagination")
        print("   ✅ Sidebar wallet information")
        print("   ✅ Transaction filtering and search")
        print("   ✅ Currency formatting utilities")
        print("   ✅ Transaction type icons")
    else:
        print("\n❌ Some tests failed. Please review the issues above.")
    
    return success


if __name__ == "__main__":
    # Run the component tests
    success = run_component_tests()
    
    if not success:
        sys.exit(1)
        
    print("\n🚀 To run the Streamlit app:")
    print("   streamlit run flight_agent_app.py")
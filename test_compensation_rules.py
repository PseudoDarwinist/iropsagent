#!/usr/bin/env python3
"""
Comprehensive test script for the new CompensationRule system
Tests database rules, admin functionality, and integration with compensation engine
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flight_agent.models import (
    create_compensation_rule, update_compensation_rule, get_all_compensation_rules,
    get_compensation_rule_by_id, deactivate_compensation_rule, get_compensation_rule_history,
    validate_compensation_rule, get_active_compensation_rules, Base, engine
)

from flight_agent.tools.compensation_engine import (
    calculate_compensation, populate_default_rules, get_active_rules_summary,
    calculate_compensation_with_rule_details
)


def setup_test_database():
    """Create test database tables"""
    print("Setting up test database...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")


def test_rule_validation():
    """Test rule validation functionality"""
    print("\n--- Testing Rule Validation ---")
    
    # Test valid rule
    valid_rule = {
        'rule_name': 'Test Valid Rule',
        'description': 'A valid test rule for cancellations',
        'disruption_type': 'CANCELLED',
        'amount': 250.0,
        'priority': 80,
        'conditions': {
            'flight_distance_km_max': 1500,
            'is_international': True
        }
    }
    
    validation = validate_compensation_rule(valid_rule)
    print(f"Valid rule test: {'✅ PASS' if validation['valid'] else '❌ FAIL'}")
    if validation['warnings']:
        print(f"  Warnings: {validation['warnings']}")
    
    # Test invalid rule (missing required fields)
    invalid_rule = {
        'rule_name': '',
        'disruption_type': 'INVALID_TYPE',
        'amount': -50.0
    }
    
    validation = validate_compensation_rule(invalid_rule)
    print(f"Invalid rule test: {'✅ PASS' if not validation['valid'] else '❌ FAIL'}")
    print(f"  Errors: {validation['errors'][:2]}...")  # Show first 2 errors
    
    return True


def test_rule_creation():
    """Test compensation rule creation"""
    print("\n--- Testing Rule Creation ---")
    
    test_rule = {
        'rule_name': 'Test Domestic Cancellation',
        'description': 'Test rule for domestic flight cancellations',
        'disruption_type': 'CANCELLED',
        'amount': 300.0,
        'priority': 85,
        'conditions': {
            'origin_country': 'US',
            'destination_country': 'US',
            'is_international': False
        }
    }
    
    try:
        created_rule = create_compensation_rule(test_rule, created_by="test_system")
        print(f"✅ Rule created: {created_rule.rule_name} (ID: {created_rule.rule_id})")
        
        # Verify rule was created correctly
        retrieved_rule = get_compensation_rule_by_id(created_rule.rule_id)
        if retrieved_rule and retrieved_rule.rule_name == test_rule['rule_name']:
            print("✅ Rule retrieval test passed")
        else:
            print("❌ Rule retrieval test failed")
            return False
        
        return created_rule
        
    except Exception as e:
        print(f"❌ Rule creation failed: {str(e)}")
        return False


def test_rule_updates_and_versioning(test_rule):
    """Test rule updates and versioning system"""
    print("\n--- Testing Rule Updates and Versioning ---")
    
    if not test_rule:
        print("❌ No test rule provided")
        return False
    
    original_version = test_rule.version
    rule_id = test_rule.rule_id
    
    # Update the rule
    updated_data = {
        'amount': 350.0,
        'priority': 90,
        'description': 'Updated test rule for domestic flight cancellations'
    }
    
    try:
        updated_rule = update_compensation_rule(rule_id, updated_data, updated_by="test_updater")
        
        # Check version increment
        if updated_rule.version == original_version + 1:
            print("✅ Rule version incremented correctly")
        else:
            print(f"❌ Version increment failed: {original_version} -> {updated_rule.version}")
            return False
        
        # Check updated fields
        if updated_rule.amount == 350.0 and updated_rule.priority == 90:
            print("✅ Rule fields updated correctly")
        else:
            print("❌ Rule fields update failed")
            return False
        
        # Check audit trail
        history = get_compensation_rule_history(rule_id)
        if len(history) >= 2:  # CREATED + UPDATED
            print(f"✅ Audit trail created: {len(history)} entries")
            
            # Check history entries
            latest_entry = history[0]  # Most recent first
            if latest_entry.action == "UPDATED" and latest_entry.version == updated_rule.version:
                print("✅ Latest audit entry is correct")
            else:
                print(f"❌ Latest audit entry incorrect: {latest_entry.action}, v{latest_entry.version}")
                return False
        else:
            print(f"❌ Insufficient audit trail entries: {len(history)}")
            return False
        
        return updated_rule
        
    except Exception as e:
        print(f"❌ Rule update failed: {str(e)}")
        return False


def test_rule_deactivation(test_rule):
    """Test rule activation/deactivation"""
    print("\n--- Testing Rule Activation/Deactivation ---")
    
    if not test_rule:
        print("❌ No test rule provided")
        return False
    
    rule_id = test_rule.rule_id
    
    try:
        # Deactivate the rule
        deactivated_rule = deactivate_compensation_rule(rule_id, deactivated_by="test_deactivator")
        
        if not deactivated_rule.is_active:
            print("✅ Rule deactivated successfully")
        else:
            print("❌ Rule deactivation failed")
            return False
        
        # Check audit trail for deactivation
        history = get_compensation_rule_history(rule_id)
        latest_entry = history[0]
        if latest_entry.action == "DEACTIVATED":
            print("✅ Deactivation audit entry created")
        else:
            print(f"❌ Deactivation audit entry missing: {latest_entry.action}")
            return False
        
        # Reactivate the rule
        reactivated_rule = update_compensation_rule(rule_id, {'is_active': True}, updated_by="test_reactivator")
        
        if reactivated_rule.is_active:
            print("✅ Rule reactivated successfully")
        else:
            print("❌ Rule reactivation failed")
            return False
        
        return reactivated_rule
        
    except Exception as e:
        print(f"❌ Rule activation/deactivation failed: {str(e)}")
        return False


def test_compensation_engine_integration():
    """Test integration between database rules and compensation engine"""
    print("\n--- Testing Compensation Engine Integration ---")
    
    try:
        # Populate default rules if needed
        populate_default_rules()
        
        # Test basic compensation calculation
        result = calculate_compensation(
            disruption_type='CANCELLED',
            booking_class='Economy',
            is_international=False,
            origin_country='US',
            destination_country='US'
        )
        
        if result['eligible'] and result['amount'] > 0:
            print(f"✅ Basic compensation calculation: ${result['amount']:.2f}")
        else:
            print(f"❌ Basic compensation calculation failed: {result}")
            return False
        
        # Test enhanced calculation with rule details
        enhanced_result = calculate_compensation_with_rule_details(
            disruption_type='CANCELLED',
            booking_class='Business',
            flight_distance_km=5000,
            is_international=True
        )
        
        if enhanced_result['eligible'] and 'rule_details' in enhanced_result:
            print("✅ Enhanced compensation calculation with rule details")
            rule_details = enhanced_result['rule_details']
            if 'rule_name' in rule_details:
                print(f"  Applied rule: {rule_details['rule_name']}")
            else:
                print(f"  Rule details error: {rule_details}")
        else:
            print("❌ Enhanced compensation calculation failed")
            return False
        
        # Test rules summary
        summary = get_active_rules_summary()
        if 'error' not in summary and summary['active_rules'] > 0:
            print(f"✅ Rules summary: {summary['active_rules']} active rules")
        else:
            print(f"❌ Rules summary failed: {summary}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Compensation engine integration failed: {str(e)}")
        return False


def test_rule_priority_system():
    """Test that rule priority system works correctly"""
    print("\n--- Testing Rule Priority System ---")
    
    try:
        # Create two rules with different priorities for the same disruption type
        high_priority_rule = {
            'rule_name': 'High Priority Test Rule',
            'description': 'High priority test rule',
            'disruption_type': 'DELAYED',
            'amount': 500.0,
            'priority': 95,
            'conditions': {'delay_hours_min': 2.0}
        }
        
        low_priority_rule = {
            'rule_name': 'Low Priority Test Rule',
            'description': 'Low priority test rule',
            'disruption_type': 'DELAYED',
            'amount': 200.0,
            'priority': 50,
            'conditions': {'delay_hours_min': 2.0}
        }
        
        rule1 = create_compensation_rule(high_priority_rule, created_by="priority_test")
        rule2 = create_compensation_rule(low_priority_rule, created_by="priority_test")
        
        print(f"✅ Created priority test rules: {rule1.rule_name} (p{rule1.priority}), {rule2.rule_name} (p{rule2.priority})")
        
        # Test compensation calculation - should use high priority rule
        result = calculate_compensation(
            disruption_type='DELAYED',
            booking_class='Economy',
            delay_hours=3.0
        )
        
        if result['eligible'] and result['amount'] == 500.0:
            print("✅ Priority system working: High priority rule applied")
        else:
            print(f"❌ Priority system failed: Expected $500, got ${result['amount']}")
            print(f"  Rule applied: {result['rule_applied']}")
            return False
        
        # Clean up test rules
        deactivate_compensation_rule(rule1.rule_id, deactivated_by="cleanup")
        deactivate_compensation_rule(rule2.rule_id, deactivated_by="cleanup")
        
        return True
        
    except Exception as e:
        print(f"❌ Priority system test failed: {str(e)}")
        return False


def run_comprehensive_tests():
    """Run all compensation rule system tests"""
    print("🧪 STARTING COMPREHENSIVE COMPENSATION RULE TESTS")
    print("=" * 60)
    
    # Setup
    setup_test_database()
    
    # Run tests
    tests_passed = 0
    total_tests = 6
    
    # Test 1: Rule Validation
    if test_rule_validation():
        tests_passed += 1
    
    # Test 2: Rule Creation
    test_rule = test_rule_creation()
    if test_rule:
        tests_passed += 1
    
    # Test 3: Rule Updates and Versioning
    if test_rule_updates_and_versioning(test_rule):
        tests_passed += 1
    
    # Test 4: Rule Deactivation
    if test_rule_deactivation(test_rule):
        tests_passed += 1
    
    # Test 5: Compensation Engine Integration
    if test_compensation_engine_integration():
        tests_passed += 1
    
    # Test 6: Rule Priority System
    if test_rule_priority_system():
        tests_passed += 1
    
    # Results
    print("\n" + "=" * 60)
    print("🏁 TEST RESULTS")
    print("=" * 60)
    print(f"Tests Passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 ALL TESTS PASSED! The CompensationRule system is working correctly.")
        return True
    else:
        print(f"❌ {total_tests - tests_passed} tests failed. Please review the issues above.")
        return False


if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)
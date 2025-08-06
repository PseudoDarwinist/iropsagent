"""
Unit Tests for Compensation Engine

Tests the flight disruption compensation calculation logic, rules,
and various scenarios for different types of disruptions.
"""

import unittest
from datetime import datetime, timedelta

# Import the compensation engine functions
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flight_agent.tools.compensation_engine import (
    calculate_compensation,
    get_compensation_summary,
    CompensationRule,
    _get_compensation_rules,
    _rule_applies,
    _calculate_final_amount,
    _get_multipliers
)


class TestCompensationEngine(unittest.TestCase):
    """Test cases for the compensation engine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.sample_booking_id = "test_booking_123"
        self.base_disruption_data = {
            'disruption_type': 'CANCELLED',
            'booking_class': 'Economy',
            'flight_distance_km': 1500,
            'delay_hours': 0,
            'is_international': False,
            'airline': 'TEST_AIRLINE',
            'origin_country': 'US',
            'destination_country': 'US'
        }
    
    def test_domestic_cancellation_economy(self):
        """Test compensation for domestic flight cancellation in Economy"""
        result = calculate_compensation(**self.base_disruption_data)
        
        self.assertTrue(result['eligible'])
        self.assertEqual(result['amount'], 200.0)  # US_DOMESTIC_CANCELLATION rule
        self.assertEqual(result['currency'], 'USD')
        self.assertEqual(result['rule_applied'], 'US_DOMESTIC_CANCELLATION')
    
    def test_international_cancellation_short_haul(self):
        """Test compensation for international short-haul cancellation"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['is_international'] = True
        disruption_data['flight_distance_km'] = 1200  # Short haul
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        self.assertEqual(result['amount'], 250.0)  # EU261_CANCELLATION_SHORT
        self.assertEqual(result['rule_applied'], 'EU261_CANCELLATION_SHORT')
    
    def test_international_cancellation_medium_haul(self):
        """Test compensation for international medium-haul cancellation"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['is_international'] = True
        disruption_data['flight_distance_km'] = 2500  # Medium haul
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        self.assertEqual(result['amount'], 400.0)  # EU261_CANCELLATION_MEDIUM
        self.assertEqual(result['rule_applied'], 'EU261_CANCELLATION_MEDIUM')
    
    def test_international_cancellation_long_haul(self):
        """Test compensation for international long-haul cancellation"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['is_international'] = True
        disruption_data['flight_distance_km'] = 5000  # Long haul
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        self.assertEqual(result['amount'], 600.0)  # EU261_CANCELLATION_LONG
        self.assertEqual(result['rule_applied'], 'EU261_CANCELLATION_LONG')
    
    def test_major_delay_compensation(self):
        """Test compensation for major delay (3+ hours)"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['disruption_type'] = 'DELAYED'
        disruption_data['delay_hours'] = 4.0
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        self.assertEqual(result['amount'], 150.0)  # MAJOR_DELAY_3H
        self.assertEqual(result['rule_applied'], 'MAJOR_DELAY_3H')
    
    def test_severe_delay_compensation(self):
        """Test compensation for severe delay (6+ hours)"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['disruption_type'] = 'DELAYED'
        disruption_data['delay_hours'] = 8.0
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        self.assertEqual(result['amount'], 300.0)  # SEVERE_DELAY_6H (higher priority)
        self.assertEqual(result['rule_applied'], 'SEVERE_DELAY_6H')
    
    def test_flight_diversion_compensation(self):
        """Test compensation for flight diversion"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['disruption_type'] = 'DIVERTED'
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        self.assertEqual(result['amount'], 250.0)  # FLIGHT_DIVERSION
        self.assertEqual(result['rule_applied'], 'FLIGHT_DIVERSION')
    
    def test_overbooking_domestic(self):
        """Test compensation for domestic overbooking"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['disruption_type'] = 'OVERBOOKED'
        disruption_data['is_international'] = False
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        self.assertEqual(result['amount'], 400.0)  # OVERBOOKING_DOMESTIC
        self.assertEqual(result['rule_applied'], 'OVERBOOKING_DOMESTIC')
    
    def test_overbooking_international(self):
        """Test compensation for international overbooking"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['disruption_type'] = 'OVERBOOKED'
        disruption_data['is_international'] = True
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        self.assertEqual(result['amount'], 675.0)  # OVERBOOKING_INTERNATIONAL
        self.assertEqual(result['rule_applied'], 'OVERBOOKING_INTERNATIONAL')
    
    def test_business_class_multiplier(self):
        """Test multiplier for Business class bookings"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['booking_class'] = 'Business'
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        # Base amount (200) * business class multiplier (1.5) = 300
        self.assertEqual(result['amount'], 300.0)
        self.assertIn('business_class', result['details']['multipliers_applied'])
        self.assertEqual(result['details']['multipliers_applied']['business_class'], 1.5)
    
    def test_first_class_multiplier(self):
        """Test multiplier for First class bookings"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['booking_class'] = 'First'
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        # Base amount (200) * first class multiplier (2.0) = 400
        self.assertEqual(result['amount'], 400.0)
        self.assertIn('first_class', result['details']['multipliers_applied'])
        self.assertEqual(result['details']['multipliers_applied']['first_class'], 2.0)
    
    def test_international_multiplier(self):
        """Test multiplier for international flights"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['is_international'] = True
        disruption_data['flight_distance_km'] = 5000  # Long haul international
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        # Should get EU261_CANCELLATION_LONG (600) * international multiplier (1.2) = 720
        self.assertEqual(result['amount'], 720.0)
        self.assertIn('international', result['details']['multipliers_applied'])
        self.assertEqual(result['details']['multipliers_applied']['international'], 1.2)
    
    def test_severe_delay_multiplier(self):
        """Test multiplier for very long delays"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['disruption_type'] = 'DELAYED'
        disruption_data['delay_hours'] = 14.0  # Very severe delay
        
        result = calculate_compensation(**disruption_data)
        
        self.assertTrue(result['eligible'])
        # SEVERE_DELAY_6H (300) * severe_delay multiplier (1.5) = 450
        self.assertEqual(result['amount'], 450.0)
        self.assertIn('severe_delay', result['details']['multipliers_applied'])
        self.assertEqual(result['details']['multipliers_applied']['severe_delay'], 1.5)
    
    def test_no_compensation_minor_delay(self):
        """Test no compensation for minor delay (<2 hours)"""
        disruption_data = self.base_disruption_data.copy()
        disruption_data['disruption_type'] = 'DELAYED'
        disruption_data['delay_hours'] = 1.5  # Minor delay
        
        result = calculate_compensation(**disruption_data)
        
        self.assertFalse(result['eligible'])
        self.assertEqual(result['amount'], 0.0)
        self.assertIsNone(result['rule_applied'])
    
    def test_rule_priority_system(self):
        """Test that higher priority rules take precedence"""
        disruption_data = {
            'disruption_type': 'CANCELLED',
            'booking_class': 'Business',
            'flight_distance_km': 2000,
            'is_international': True
        }
        
        result = calculate_compensation(**disruption_data)
        
        # Should get EU261_CANCELLATION_MEDIUM (priority 90) instead of BUSINESS_CLASS_BONUS (priority 50)
        self.assertEqual(result['rule_applied'], 'EU261_CANCELLATION_MEDIUM')
        
        # But should still apply business class multiplier
        expected_amount = 400.0 * 1.5 * 1.2  # base * business * international
        self.assertEqual(result['amount'], expected_amount)
    
    def test_compensation_summary_generation(self):
        """Test comprehensive compensation summary generation"""
        summary = get_compensation_summary(self.sample_booking_id, self.base_disruption_data)
        
        self.assertEqual(summary['booking_id'], self.sample_booking_id)
        self.assertIn('timestamp', summary)
        self.assertIn('compensation', summary)
        self.assertTrue(summary['automatic_processing'])
        self.assertFalse(summary['requires_manual_review'])  # Amount < $1000
        self.assertEqual(summary['estimated_processing_time'], '1-2 business days')
    
    def test_high_value_compensation_requires_review(self):
        """Test that high-value compensation requires manual review"""
        # Create scenario that results in >$1000 compensation
        disruption_data = {
            'disruption_type': 'OVERBOOKED',
            'booking_class': 'First',
            'is_international': True,
            'delay_hours': 14.0  # Severe delay for extra multiplier
        }
        
        summary = get_compensation_summary(self.sample_booking_id, disruption_data)
        
        # Should exceed $1000 threshold
        self.assertGreater(summary['compensation']['amount'], 1000)
        self.assertTrue(summary['requires_manual_review'])
    
    def test_rule_matching_logic(self):
        """Test the rule matching logic"""
        rules = _get_compensation_rules()
        
        # Test exact match
        context = {
            'disruption_type': 'CANCELLED',
            'origin_country': 'US',
            'destination_country': 'US'
        }
        
        us_domestic_rule = next(r for r in rules if r.rule_id == 'US_DOMESTIC_CANCELLATION')
        self.assertTrue(_rule_applies(us_domestic_rule, context))
        
        # Test range match
        context = {
            'flight_distance_km': 2000
        }
        
        medium_haul_rule = next(r for r in rules if r.rule_id == 'EU261_CANCELLATION_MEDIUM')
        self.assertTrue(_rule_applies(medium_haul_rule, context))
        
        # Test range mismatch
        context = {
            'flight_distance_km': 500  # Too short for medium haul
        }
        
        self.assertFalse(_rule_applies(medium_haul_rule, context))
    
    def test_multiplier_calculation(self):
        """Test multiplier calculation logic"""
        # Test business class
        context = {'booking_class': 'Business'}
        multipliers = _get_multipliers(context)
        self.assertEqual(multipliers['business_class'], 1.5)
        
        # Test first class
        context = {'booking_class': 'First'}
        multipliers = _get_multipliers(context)
        self.assertEqual(multipliers['first_class'], 2.0)
        
        # Test international
        context = {'is_international': True}
        multipliers = _get_multipliers(context)
        self.assertEqual(multipliers['international'], 1.2)
        
        # Test severe delay
        context = {'delay_hours': 15.0}
        multipliers = _get_multipliers(context)
        self.assertEqual(multipliers['severe_delay'], 1.5)
        
        # Test major delay
        context = {'delay_hours': 9.0}
        multipliers = _get_multipliers(context)
        self.assertEqual(multipliers['major_delay'], 1.25)
    
    def test_amount_bounds(self):
        """Test that compensation amounts stay within reasonable bounds"""
        # Create extreme scenario
        disruption_data = {
            'disruption_type': 'OVERBOOKED',
            'booking_class': 'First',
            'is_international': True,
            'delay_hours': 20.0
        }
        
        result = calculate_compensation(**disruption_data)
        
        # Should not exceed maximum bound of $2000
        self.assertLessEqual(result['amount'], 2000.0)
        self.assertGreater(result['amount'], 0.0)
    
    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        # Test with missing data
        minimal_data = {
            'disruption_type': 'CANCELLED'
        }
        
        result = calculate_compensation(**minimal_data)
        # Should still work with defaults
        self.assertIsInstance(result, dict)
        self.assertIn('eligible', result)
        
        # Test with invalid disruption type
        invalid_data = {
            'disruption_type': 'INVALID_TYPE',
            'booking_class': 'Economy'
        }
        
        result = calculate_compensation(**invalid_data)
        self.assertFalse(result['eligible'])
        self.assertEqual(result['amount'], 0.0)


class TestCompensationRules(unittest.TestCase):
    """Test cases for compensation rule definitions"""
    
    def test_rule_structure(self):
        """Test that all rules have required fields"""
        rules = _get_compensation_rules()
        
        for rule in rules:
            self.assertIsInstance(rule, CompensationRule)
            self.assertIsInstance(rule.rule_id, str)
            self.assertIsInstance(rule.description, str)
            self.assertIsInstance(rule.amount, (int, float))
            self.assertIsInstance(rule.conditions, dict)
            self.assertIsInstance(rule.priority, int)
            self.assertGreater(len(rule.rule_id), 0)
            self.assertGreater(len(rule.description), 0)
            self.assertGreaterEqual(rule.amount, 0)
    
    def test_rule_priorities(self):
        """Test that rule priorities make sense"""
        rules = _get_compensation_rules()
        
        # Overbooking should have highest priority
        overbooking_rules = [r for r in rules if 'OVERBOOKING' in r.rule_id]
        for rule in overbooking_rules:
            self.assertGreaterEqual(rule.priority, 90)
        
        # EU261 rules should have high priority
        eu261_rules = [r for r in rules if 'EU261' in r.rule_id]
        for rule in eu261_rules:
            self.assertGreaterEqual(rule.priority, 80)
        
        # Class bonuses should have lower priority
        class_rules = [r for r in rules if 'CLASS' in r.rule_id]
        for rule in class_rules:
            self.assertLessEqual(rule.priority, 60)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
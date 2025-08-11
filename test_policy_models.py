#!/usr/bin/env python3
"""
Test suite for Policy Compliance and Approval Workflow Models

Tests the new TravelPolicy, ApprovalRequest, and PolicyException models
along with their relationships and helper functions.

Supporting Requirements:
- REQ-5.1: Policy rule definitions and compliance checking
- REQ-5.2: Approval workflows with escalation chains
- REQ-5.4: Exception tracking and violation management
"""

import unittest
import tempfile
import os
from datetime import datetime, timedelta
from flight_agent.models import (
    Base, engine, SessionLocal,
    User, Booking, TravelPolicy, ApprovalRequest, PolicyException,
    create_user, create_booking, create_travel_policy, create_approval_request,
    create_policy_exception, get_active_travel_policies, get_pending_approval_requests,
    get_policy_exceptions_by_booking, escalate_approval_request, approve_request,
    reject_request, resolve_policy_exception, check_policy_compliance
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestPolicyComplianceModels(unittest.TestCase):
    """Test cases for policy compliance and approval workflow models"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database"""
        # Create test database in memory
        cls.test_engine = create_engine("sqlite:///:memory:", echo=False)
        cls.TestSession = sessionmaker(bind=cls.test_engine)
        
        # Create all tables
        Base.metadata.create_all(bind=cls.test_engine)
    
    def setUp(self):
        """Set up test data for each test"""
        self.session = self.TestSession()
        
        # Create unique user for each test to avoid conflicts
        unique_id = str(int(datetime.now().timestamp() * 1000000))
        
        # Create test user
        self.test_user = User(
            user_id=f"test_user_{unique_id}",
            email=f"test_{unique_id}@example.com",
            phone="+1234567890",
            preferences={"sms": {"enabled": True}}
        )
        self.session.add(self.test_user)
        self.session.commit()
        
        # Create test booking
        self.test_booking = Booking(
            booking_id=f"booking_{unique_id}",
            user_id=self.test_user.user_id,
            pnr='ABC123',
            airline='AA',
            flight_number='1234',
            departure_date=datetime(2025, 8, 15, 8, 30),
            origin='JFK',
            destination='LAX',
            booking_class='Business',
            fare_amount=1500.00,
            currency='USD'
        )
        self.session.add(self.test_booking)
        self.session.commit()
        
        # Sample travel policy data
        self.sample_policy_data = {
            'policy_name': 'Standard Travel Policy',
            'description': 'Standard corporate travel policy for all employees',
            'policy_type': 'BOOKING',
            'rules': {
                'booking_limits': {
                    'max_fare_amount': 1000,
                    'allowed_booking_classes': ['Economy', 'Premium Economy'],
                    'advance_booking_days': 7,
                    'preferred_airlines': ['AA', 'DL', 'UA']
                },
                'expense_limits': {
                    'max_hotel_rate': 200,
                    'max_meal_allowance': 50
                },
                'approval_thresholds': {
                    'auto_approve_below': 500,
                    'manager_approval_below': 2000,
                    'director_approval_above': 2000
                }
            },
            'effective_date': datetime(2025, 1, 1),
            'enforcement_level': 'STRICT'
        }
        
        # Sample escalation chain
        self.sample_escalation_chain = [
            {"level": 0, "approver_role": "manager", "approver_id": "mgr_123", "timeout_hours": 24},
            {"level": 1, "approver_role": "director", "approver_id": "dir_456", "timeout_hours": 48},
            {"level": 2, "approver_role": "vp", "approver_id": "vp_789", "timeout_hours": 72}
        ]
    
    def tearDown(self):
        """Clean up after each test"""
        self.session.rollback()
        self.session.close()
    
    def test_travel_policy_model_creation(self):
        """Test TravelPolicy model creation and attributes"""
        # Create travel policy
        policy = TravelPolicy(
            policy_id="policy_test_123",
            policy_name=self.sample_policy_data['policy_name'],
            description=self.sample_policy_data['description'],
            policy_type=self.sample_policy_data['policy_type'],
            rules=self.sample_policy_data['rules'],
            effective_date=self.sample_policy_data['effective_date'],
            created_by='system'
        )
        self.session.add(policy)
        self.session.commit()
        
        # Test attributes
        retrieved_policy = self.session.query(TravelPolicy).filter_by(policy_id="policy_test_123").first()
        self.assertIsNotNone(retrieved_policy)
        self.assertEqual(retrieved_policy.policy_name, 'Standard Travel Policy')
        self.assertEqual(retrieved_policy.policy_type, 'BOOKING')
        self.assertEqual(retrieved_policy.enforcement_level, 'STRICT')
        self.assertTrue(retrieved_policy.is_active)
        self.assertTrue(retrieved_policy.auto_compliance_check)
        self.assertTrue(retrieved_policy.allow_exceptions)
        self.assertTrue(retrieved_policy.exception_requires_approval)
        
        # Test rules structure
        rules = retrieved_policy.rules
        self.assertIn('booking_limits', rules)
        self.assertEqual(rules['booking_limits']['max_fare_amount'], 1000)
        self.assertIn('Economy', rules['booking_limits']['allowed_booking_classes'])
        self.assertEqual(rules['booking_limits']['advance_booking_days'], 7)
        self.assertIsNotNone(retrieved_policy.created_at)
    
    def test_approval_request_model_creation(self):
        """Test ApprovalRequest model creation and escalation chain"""
        # Create approval request
        request = ApprovalRequest(
            request_id="approval_test_123",
            user_id=self.test_user.user_id,
            booking_id=self.test_booking.booking_id,
            request_type='BOOKING_APPROVAL',
            title='High-cost flight booking approval',
            description='Request approval for business class booking exceeding policy limits',
            justification='Critical client meeting requiring business travel',
            request_data={
                'booking_details': {'fare_amount': 1500, 'class': 'Business'},
                'policy_violations': ['FARE_LIMIT_EXCEEDED', 'CLASS_RESTRICTION'],
                'business_justification': 'Important client presentation'
            },
            escalation_chain=self.sample_escalation_chain,
            current_approver_id='mgr_123',
            current_approver_role='manager',
            priority='HIGH',
            due_date=datetime.utcnow() + timedelta(days=3)
        )
        self.session.add(request)
        self.session.commit()
        
        # Test attributes
        retrieved_request = self.session.query(ApprovalRequest).filter_by(request_id="approval_test_123").first()
        self.assertIsNotNone(retrieved_request)
        self.assertEqual(retrieved_request.request_type, 'BOOKING_APPROVAL')
        self.assertEqual(retrieved_request.title, 'High-cost flight booking approval')
        self.assertEqual(retrieved_request.status, 'PENDING')
        self.assertEqual(retrieved_request.priority, 'HIGH')
        self.assertEqual(retrieved_request.escalation_level, 0)
        self.assertEqual(retrieved_request.current_approver_id, 'mgr_123')
        self.assertEqual(retrieved_request.current_approver_role, 'manager')
        
        # Test escalation chain structure
        chain = retrieved_request.escalation_chain
        self.assertEqual(len(chain), 3)
        self.assertEqual(chain[0]['level'], 0)
        self.assertEqual(chain[0]['approver_role'], 'manager')
        self.assertEqual(chain[0]['timeout_hours'], 24)
        self.assertEqual(chain[1]['approver_role'], 'director')
        self.assertEqual(chain[2]['approver_role'], 'vp')
        
        # Test request data structure
        request_data = retrieved_request.request_data
        self.assertIn('booking_details', request_data)
        self.assertEqual(request_data['booking_details']['fare_amount'], 1500)
        self.assertIn('FARE_LIMIT_EXCEEDED', request_data['policy_violations'])
        
        # Test relationships
        self.assertEqual(retrieved_request.user.user_id, self.test_user.user_id)
        self.assertEqual(retrieved_request.booking.booking_id, self.test_booking.booking_id)
    
    def test_policy_exception_model_creation(self):
        """Test PolicyException model creation and violation tracking"""
        # Create travel policy first
        policy = TravelPolicy(
            policy_id="policy_exception_test",
            policy_name="Test Policy",
            description="Test policy for exceptions",
            policy_type="BOOKING",
            rules={'booking_limits': {'max_fare_amount': 1000}},
            effective_date=datetime(2025, 1, 1),
            created_by='system'
        )
        self.session.add(policy)
        self.session.commit()
        
        # Create policy exception
        exception = PolicyException(
            exception_id="exception_test_123",
            booking_id=self.test_booking.booking_id,
            policy_id=policy.policy_id,
            exception_type='RULE_VIOLATION',
            violation_category='BOOKING_LIMIT',
            severity='HIGH',
            violated_rule='booking_limits.max_fare_amount',
            expected_value='$1000',
            actual_value='$1500',
            violation_amount=500.0,
            title='Fare amount exceeds policy limit',
            description='Business class booking exceeds maximum allowed fare amount',
            violation_details={
                'rule_path': 'booking_limits.max_fare_amount',
                'policy_value': 1000,
                'actual_value': 1500,
                'violation_percentage': 50,
                'context': {
                    'booking_class': 'Business',
                    'route': 'JFK-LAX',
                    'advance_days': 2
                }
            },
            user_justification='Critical client meeting requiring urgent travel',
            business_justification='High-priority client engagement with potential $100K deal',
            cost_impact=500.0,
            savings_foregone=0.0
        )
        self.session.add(exception)
        self.session.commit()
        
        # Test attributes
        retrieved_exception = self.session.query(PolicyException).filter_by(exception_id="exception_test_123").first()
        self.assertIsNotNone(retrieved_exception)
        self.assertEqual(retrieved_exception.exception_type, 'RULE_VIOLATION')
        self.assertEqual(retrieved_exception.violation_category, 'BOOKING_LIMIT')
        self.assertEqual(retrieved_exception.severity, 'HIGH')
        self.assertEqual(retrieved_exception.violated_rule, 'booking_limits.max_fare_amount')
        self.assertEqual(retrieved_exception.expected_value, '$1000')
        self.assertEqual(retrieved_exception.actual_value, '$1500')
        self.assertEqual(retrieved_exception.violation_amount, 500.0)
        self.assertEqual(retrieved_exception.status, 'OPEN')
        self.assertTrue(retrieved_exception.requires_approval)
        self.assertEqual(retrieved_exception.cost_impact, 500.0)
        self.assertFalse(retrieved_exception.is_recurring)
        
        # Test violation details structure
        details = retrieved_exception.violation_details
        self.assertEqual(details['rule_path'], 'booking_limits.max_fare_amount')
        self.assertEqual(details['policy_value'], 1000)
        self.assertEqual(details['actual_value'], 1500)
        self.assertEqual(details['violation_percentage'], 50)
        self.assertIn('context', details)
        self.assertEqual(details['context']['booking_class'], 'Business')
        
        # Test relationships
        self.assertEqual(retrieved_exception.booking.booking_id, self.test_booking.booking_id)
        self.assertEqual(retrieved_exception.travel_policy.policy_id, policy.policy_id)
    
    def test_model_relationships_consistency(self):
        """Test that all policy model relationships are consistent"""
        # Create complete data chain: User -> Booking -> Policy -> ApprovalRequest -> PolicyException
        policy = TravelPolicy(
            policy_id="relationship_test_policy",
            policy_name="Relationship Test Policy",
            description="Test policy relationships",
            policy_type="BOOKING",
            rules={'booking_limits': {'max_fare_amount': 1000}},
            effective_date=datetime(2025, 1, 1),
            created_by='system'
        )
        self.session.add(policy)
        
        approval_request = ApprovalRequest(
            request_id="relationship_test_approval",
            user_id=self.test_user.user_id,
            booking_id=self.test_booking.booking_id,
            policy_id=policy.policy_id,
            request_type='POLICY_EXCEPTION',
            title='Test approval request',
            description='Test approval request for relationships',
            request_data={'test': 'data'},
            escalation_chain=[{"level": 0, "approver_id": "test_mgr"}]
        )
        self.session.add(approval_request)
        
        policy_exception = PolicyException(
            exception_id="relationship_test_exception",
            booking_id=self.test_booking.booking_id,
            policy_id=policy.policy_id,
            exception_type='RULE_VIOLATION',
            violation_category='BOOKING_LIMIT',
            violated_rule='test_rule',
            title='Test exception',
            description='Test exception for relationships',
            violation_details={'test': 'details'}
        )
        self.session.add(policy_exception)
        self.session.commit()
        
        # Test forward relationships
        user = self.session.query(User).filter_by(user_id=self.test_user.user_id).first()
        self.assertGreater(len(user.approval_requests), 0)
        
        booking = self.session.query(Booking).filter_by(booking_id=self.test_booking.booking_id).first()
        self.assertGreater(len(booking.approval_requests), 0)
        self.assertGreater(len(booking.policy_exceptions), 0)
        
        retrieved_policy = self.session.query(TravelPolicy).filter_by(policy_id="relationship_test_policy").first()
        self.assertGreater(len(retrieved_policy.approval_requests), 0)
        self.assertGreater(len(retrieved_policy.policy_exceptions), 0)
        
        # Test backward relationships
        retrieved_approval = self.session.query(ApprovalRequest).filter_by(request_id="relationship_test_approval").first()
        self.assertEqual(retrieved_approval.user.user_id, self.test_user.user_id)
        self.assertEqual(retrieved_approval.booking.booking_id, self.test_booking.booking_id)
        self.assertEqual(retrieved_approval.travel_policy.policy_id, policy.policy_id)
        
        retrieved_exception = self.session.query(PolicyException).filter_by(exception_id="relationship_test_exception").first()
        self.assertEqual(retrieved_exception.booking.booking_id, self.test_booking.booking_id)
        self.assertEqual(retrieved_exception.travel_policy.policy_id, policy.policy_id)
    
    def test_helper_functions(self):
        """Test helper functions for policy compliance models"""
        # Test create_travel_policy
        policy = create_travel_policy(self.sample_policy_data, 'test_user')
        self.assertIsNotNone(policy)
        self.assertEqual(policy.policy_name, 'Standard Travel Policy')
        self.assertEqual(policy.created_by, 'test_user')
        
        # Test get_active_travel_policies
        active_policies = get_active_travel_policies()
        self.assertGreater(len(active_policies), 0)
        
        # Test filtered policies
        booking_policies = get_active_travel_policies(policy_type='BOOKING')
        self.assertGreater(len(booking_policies), 0)
        
        # Test create_approval_request
        approval_data = {
            'request_type': 'BOOKING_APPROVAL',
            'title': 'Test Approval',
            'description': 'Test approval request',
            'request_data': {'test': 'data'},
            'escalation_chain': self.sample_escalation_chain,
            'priority': 'MEDIUM'
        }
        approval_request = create_approval_request(approval_data, self.test_user.user_id)
        self.assertIsNotNone(approval_request)
        self.assertEqual(approval_request.request_type, 'BOOKING_APPROVAL')
        self.assertEqual(approval_request.current_approver_id, 'mgr_123')
        
        # Test get_pending_approval_requests
        pending_requests = get_pending_approval_requests()
        self.assertGreater(len(pending_requests), 0)
        
        # Test filtered pending requests
        manager_requests = get_pending_approval_requests(approver_id='mgr_123')
        self.assertGreater(len(manager_requests), 0)
        
        # Test create_policy_exception
        exception_data = {
            'exception_type': 'RULE_VIOLATION',
            'violation_category': 'BOOKING_LIMIT',
            'violated_rule': 'test_rule',
            'title': 'Test Exception',
            'description': 'Test policy exception',
            'violation_details': {'test': 'details'}
        }
        exception = create_policy_exception(exception_data, self.test_booking.booking_id, policy.policy_id)
        self.assertIsNotNone(exception)
        self.assertEqual(exception.exception_type, 'RULE_VIOLATION')
        
        # Test get_policy_exceptions_by_booking
        booking_exceptions = get_policy_exceptions_by_booking(self.test_booking.booking_id)
        self.assertGreater(len(booking_exceptions), 0)
    
    def test_approval_workflow_functions(self):
        """Test approval workflow management functions"""
        # Create approval request
        approval_data = {
            'request_type': 'BOOKING_APPROVAL',
            'title': 'Workflow Test',
            'description': 'Test approval workflow',
            'request_data': {'test': 'data'},
            'escalation_chain': self.sample_escalation_chain,
            'priority': 'HIGH'
        }
        request = create_approval_request(approval_data, self.test_user.user_id)
        
        # Test escalation
        escalated_request = escalate_approval_request(request.request_id)
        self.assertEqual(escalated_request.escalation_level, 1)
        self.assertEqual(escalated_request.current_approver_id, 'dir_456')
        self.assertEqual(escalated_request.status, 'ESCALATED')
        self.assertGreater(len(escalated_request.approval_history), 1)
        
        # Test approval
        approved_request = approve_request(request.request_id, 'dir_456', 'Approved for business reasons')
        self.assertEqual(approved_request.status, 'APPROVED')
        self.assertEqual(approved_request.approved_by, 'dir_456')
        self.assertIsNotNone(approved_request.approved_at)
        self.assertIsNotNone(approved_request.resolved_at)
        self.assertEqual(approved_request.approval_notes, 'Approved for business reasons')
        
        # Test rejection (create new request)
        rejection_data = {
            'request_type': 'EXPENSE_APPROVAL',
            'title': 'Rejection Test',
            'description': 'Test rejection workflow',
            'request_data': {'test': 'data'},
            'escalation_chain': [{"level": 0, "approver_id": "mgr_123"}]
        }
        reject_request_obj = create_approval_request(rejection_data, self.test_user.user_id)
        
        rejected_request = reject_request(reject_request_obj.request_id, 'mgr_123', 'Exceeds budget limits')
        self.assertEqual(rejected_request.status, 'REJECTED')
        self.assertEqual(rejected_request.rejection_reason, 'Exceeds budget limits')
        self.assertIsNotNone(rejected_request.resolved_at)
    
    def test_policy_exception_resolution(self):
        """Test policy exception resolution workflow"""
        # Create policy and exception
        policy = create_travel_policy(self.sample_policy_data, 'system')
        exception_data = {
            'exception_type': 'RULE_VIOLATION',
            'violation_category': 'BOOKING_LIMIT',
            'violated_rule': 'booking_limits.max_fare_amount',
            'title': 'Fare Limit Exception',
            'description': 'Booking exceeds fare limits',
            'violation_details': {
                'rule_path': 'booking_limits.max_fare_amount',
                'policy_value': 1000,
                'actual_value': 1500
            }
        }
        exception = create_policy_exception(exception_data, self.test_booking.booking_id, policy.policy_id)
        
        # Test resolution
        resolved_exception = resolve_policy_exception(
            exception.exception_id,
            'manager_123',
            'APPROVED',
            'Approved due to business criticality'
        )
        self.assertEqual(resolved_exception.status, 'RESOLVED')
        self.assertEqual(resolved_exception.resolved_by, 'manager_123')
        self.assertEqual(resolved_exception.resolution_action, 'APPROVED')
        self.assertEqual(resolved_exception.resolution_notes, 'Approved due to business criticality')
        self.assertIsNotNone(resolved_exception.resolved_at)
        self.assertIsNotNone(resolved_exception.resolution_date)
    
    def test_policy_compliance_checking(self):
        """Test policy compliance checking function"""
        # Create test policy
        policy = create_travel_policy(self.sample_policy_data, 'system')
        
        # Test compliant booking data
        compliant_booking = {
            'fare_amount': 800,
            'booking_class': 'Economy',
            'departure_date': datetime.utcnow() + timedelta(days=10)
        }
        violations = check_policy_compliance(compliant_booking, [policy])
        self.assertEqual(len(violations), 0)
        
        # Test non-compliant booking data
        non_compliant_booking = {
            'fare_amount': 1500,  # Exceeds limit of 1000
            'booking_class': 'Business',  # Not in allowed classes
            'departure_date': datetime.utcnow() + timedelta(days=2)  # Less than 7 days advance
        }
        violations = check_policy_compliance(non_compliant_booking, [policy])
        self.assertGreater(len(violations), 0)
        
        # Check specific violations
        violation_types = [v['violation_type'] for v in violations]
        self.assertIn('FARE_LIMIT_EXCEEDED', violation_types)
        self.assertIn('BOOKING_CLASS_VIOLATION', violation_types)
        self.assertIn('ADVANCE_BOOKING_VIOLATION', violation_types)
        
        # Test violation details
        fare_violation = next(v for v in violations if v['violation_type'] == 'FARE_LIMIT_EXCEEDED')
        self.assertEqual(fare_violation['expected_value'], 1000)
        self.assertEqual(fare_violation['actual_value'], 1500)
        self.assertIn('exceeds policy limit', fare_violation['message'])


def run_simple_validation():
    """Run simple validation that doesn't rely on the full database"""
    print("Running simple policy model validation...")
    
    # Test model imports
    from flight_agent.models import TravelPolicy, ApprovalRequest, PolicyException
    print("✓ All new policy models imported successfully")
    
    # Test basic model instantiation
    try:
        policy = TravelPolicy(
            policy_id="test_policy_123",
            policy_name="Test Policy",
            description="Test policy description",
            policy_type="BOOKING",
            rules={'test': 'rule'},
            effective_date=datetime.now(),
            created_by="test_user"
        )
        print("✓ TravelPolicy model instantiation works")
    except Exception as e:
        print(f"✗ TravelPolicy model instantiation failed: {e}")
        
    try:
        approval = ApprovalRequest(
            request_id="test_approval_123",
            user_id="test_user",
            request_type="BOOKING_APPROVAL",
            title="Test Approval",
            description="Test approval description",
            request_data={'test': 'data'},
            escalation_chain=[{'level': 0, 'approver_id': 'mgr_123'}]
        )
        print("✓ ApprovalRequest model instantiation works")
    except Exception as e:
        print(f"✗ ApprovalRequest model instantiation failed: {e}")
        
    try:
        exception = PolicyException(
            exception_id="test_exception_123",
            booking_id="test_booking",
            policy_id="test_policy",
            exception_type="RULE_VIOLATION",
            violation_category="BOOKING_LIMIT",
            violated_rule="test_rule",
            title="Test Exception",
            description="Test exception description",
            violation_details={'test': 'details'}
        )
        print("✓ PolicyException model instantiation works")
    except Exception as e:
        print(f"✗ PolicyException model instantiation failed: {e}")

    print("✓ Simple policy model validation completed!")


if __name__ == '__main__':
    # First run simple validation
    run_simple_validation()
    
    print("\n" + "="*50 + "\n")
    
    # Run unit tests
    print("Running policy model unit tests...")
    unittest.main(exit=False, verbosity=2)
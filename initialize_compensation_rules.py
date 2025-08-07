#!/usr/bin/env python3
"""
Initialize the compensation rules database with default rules
This script sets up the database and populates it with a comprehensive set of compensation rules
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flight_agent.models import Base, engine, create_compensation_rule
from flight_agent.tools.compensation_engine import populate_default_rules


def create_sample_rules():
    """Create a comprehensive set of sample compensation rules"""
    print("Creating comprehensive sample compensation rules...")
    
    sample_rules = [
        # EU261-style rules
        {
            'rule_name': 'EU261 Short Haul Cancellation',
            'description': 'EU261 compensation for cancelled flights under 1500km',
            'disruption_type': 'CANCELLED',
            'amount': 250.0,
            'priority': 90,
            'conditions': {
                'flight_distance_km_max': 1500,
                'is_international': True
            }
        },
        {
            'rule_name': 'EU261 Medium Haul Cancellation',
            'description': 'EU261 compensation for cancelled flights 1500-3500km',
            'disruption_type': 'CANCELLED',
            'amount': 400.0,
            'priority': 90,
            'conditions': {
                'flight_distance_km_min': 1500,
                'flight_distance_km_max': 3500,
                'is_international': True
            }
        },
        {
            'rule_name': 'EU261 Long Haul Cancellation',
            'description': 'EU261 compensation for cancelled flights over 3500km',
            'disruption_type': 'CANCELLED',
            'amount': 600.0,
            'priority': 90,
            'conditions': {
                'flight_distance_km_min': 3500,
                'is_international': True
            }
        },
        
        # US domestic rules
        {
            'rule_name': 'US Domestic Cancellation Standard',
            'description': 'Standard compensation for US domestic flight cancellations',
            'disruption_type': 'CANCELLED',
            'amount': 200.0,
            'priority': 80,
            'conditions': {
                'origin_country': 'US',
                'destination_country': 'US',
                'is_international': False
            }
        },
        {
            'rule_name': 'US Domestic Business Class Cancellation',
            'description': 'Enhanced compensation for US domestic business class cancellations',
            'disruption_type': 'CANCELLED',
            'amount': 400.0,
            'priority': 85,
            'conditions': {
                'origin_country': 'US',
                'destination_country': 'US',
                'booking_class': 'Business',
                'is_international': False
            }
        },
        
        # Delay rules
        {
            'rule_name': 'Major Delay 3+ Hours',
            'description': 'Compensation for delays of 3 hours or more',
            'disruption_type': 'DELAYED',
            'amount': 150.0,
            'priority': 70,
            'conditions': {
                'delay_hours_min': 3.0
            }
        },
        {
            'rule_name': 'Severe Delay 6+ Hours',
            'description': 'Enhanced compensation for severe delays of 6+ hours',
            'disruption_type': 'DELAYED',
            'amount': 300.0,
            'priority': 75,
            'conditions': {
                'delay_hours_min': 6.0
            }
        },
        {
            'rule_name': 'Extreme Delay 12+ Hours',
            'description': 'Maximum compensation for extreme delays of 12+ hours',
            'disruption_type': 'DELAYED',
            'amount': 500.0,
            'priority': 80,
            'conditions': {
                'delay_hours_min': 12.0
            }
        },
        
        # Overbooking rules
        {
            'rule_name': 'Domestic Overbooking',
            'description': 'Compensation for domestic flight overbooking',
            'disruption_type': 'OVERBOOKED',
            'amount': 400.0,
            'priority': 95,
            'conditions': {
                'is_international': False
            }
        },
        {
            'rule_name': 'International Overbooking',
            'description': 'Enhanced compensation for international flight overbooking',
            'disruption_type': 'OVERBOOKED',
            'amount': 675.0,
            'priority': 95,
            'conditions': {
                'is_international': True
            }
        },
        
        # Diversion rules
        {
            'rule_name': 'Flight Diversion Standard',
            'description': 'Standard compensation for flight diversions',
            'disruption_type': 'DIVERTED',
            'amount': 250.0,
            'priority': 85,
            'conditions': {}
        },
        {
            'rule_name': 'International Flight Diversion',
            'description': 'Enhanced compensation for international flight diversions',
            'disruption_type': 'DIVERTED',
            'amount': 400.0,
            'priority': 88,
            'conditions': {
                'is_international': True
            }
        },
        
        # Premium class bonuses
        {
            'rule_name': 'First Class Service Disruption',
            'description': 'Additional compensation for First class service disruptions',
            'disruption_type': 'CANCELLED',
            'amount': 300.0,
            'priority': 60,
            'conditions': {
                'booking_class': 'First'
            }
        },
        {
            'rule_name': 'Business Class Delay Premium',
            'description': 'Premium compensation for Business class delays',
            'disruption_type': 'DELAYED',
            'amount': 200.0,
            'priority': 60,
            'conditions': {
                'booking_class': 'Business',
                'delay_hours_min': 2.0
            }
        }
    ]
    
    created_count = 0
    failed_count = 0
    
    for rule_data in sample_rules:
        try:
            created_rule = create_compensation_rule(rule_data, created_by="system_initialization")
            print(f"✅ Created: {created_rule.rule_name}")
            created_count += 1
        except Exception as e:
            print(f"❌ Failed to create '{rule_data['rule_name']}': {str(e)}")
            failed_count += 1
    
    print(f"\n📊 Summary: {created_count} rules created, {failed_count} failed")
    return created_count > 0


def main():
    """Main initialization function"""
    print("🚀 INITIALIZING COMPENSATION RULES DATABASE")
    print("=" * 60)
    
    # Create database tables
    print("Setting up database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")
    
    # Check if rules already exist
    try:
        from flight_agent.models import get_all_compensation_rules
        existing_rules = get_all_compensation_rules()
        
        if existing_rules:
            print(f"⚠️  Database already contains {len(existing_rules)} compensation rules")
            response = input("Do you want to add more sample rules anyway? (y/N): ").lower().strip()
            if response not in ['y', 'yes']:
                print("Initialization cancelled by user")
                return
        
    except Exception as e:
        print(f"Warning: Could not check existing rules: {str(e)}")
    
    # Create comprehensive sample rules
    success = create_sample_rules()
    
    if success:
        print("\n🎉 Compensation rules database initialized successfully!")
        print("\nNext steps:")
        print("1. Start the admin interface: python3 admin_app.py")
        print("2. Open http://localhost:5000 in your browser")
        print("3. Test the compensation engine: python3 test_compensation_rules.py")
    else:
        print("\n❌ Failed to initialize compensation rules database")
        sys.exit(1)


if __name__ == "__main__":
    main()
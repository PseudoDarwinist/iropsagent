# flight_agent/tools/compensation_engine.py
"""
Compensation Engine for Flight Disruptions

This module calculates appropriate compensation amounts based on disruption type,
flight details, and regulatory requirements (EU261, US DOT, etc.).
Now uses dynamic database rules instead of hardcoded rules.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, List
from enum import Enum


class DisruptionType(Enum):
    """Types of flight disruptions"""
    CANCELLED = "CANCELLED"
    DELAYED = "DELAYED"
    DIVERTED = "DIVERTED"
    OVERBOOKED = "OVERBOOKED"


class CompensationReason(Enum):
    """Reasons for compensation eligibility"""
    CARRIER_FAULT = "CARRIER_FAULT"
    WEATHER = "WEATHER"
    AIR_TRAFFIC_CONTROL = "AIR_TRAFFIC_CONTROL"
    MECHANICAL = "MECHANICAL"
    CREW_SHORTAGE = "CREW_SHORTAGE"
    EXTRAORDINARY_CIRCUMSTANCES = "EXTRAORDINARY_CIRCUMSTANCES"


class CompensationRule:
    """Defines a compensation rule with conditions and amount"""
    
    def __init__(self, rule_id: str, description: str, amount: float, 
                 conditions: Dict, priority: int = 0):
        self.rule_id = rule_id
        self.description = description
        self.amount = amount
        self.conditions = conditions
        self.priority = priority  # Higher priority rules take precedence


def calculate_compensation(
    disruption_type: str,
    booking_class: str,
    flight_distance_km: Optional[int] = None,
    delay_hours: Optional[float] = None,
    is_international: bool = False,
    airline: Optional[str] = None,
    origin_country: str = "US",
    destination_country: str = "US"
) -> Dict:
    """
    Calculate compensation amount for a flight disruption using database rules
    
    Args:
        disruption_type: Type of disruption (CANCELLED, DELAYED, etc.)
        booking_class: Booking class (Economy, Business, First)
        flight_distance_km: Flight distance in kilometers
        delay_hours: Hours of delay (for DELAYED type)
        is_international: Whether it's an international flight
        airline: Airline code/name
        origin_country: Origin country code
        destination_country: Destination country code
    
    Returns:
        Dict containing compensation details
    """
    
    # Get active compensation rules from database
    try:
        from ..models import get_active_compensation_rules
        db_rules = get_active_compensation_rules(disruption_type)
    except ImportError:
        # Fallback to hardcoded rules if database is not available
        db_rules = []
        print("Warning: Could not load database rules, falling back to hardcoded rules")
    
    # Convert database rules to legacy format for compatibility
    rules = []
    for db_rule in db_rules:
        legacy_rule = CompensationRule(
            rule_id=db_rule.rule_id,
            description=db_rule.description,
            amount=db_rule.amount,
            conditions=db_rule.conditions or {},
            priority=db_rule.priority
        )
        rules.append(legacy_rule)
    
    # If no database rules found, fall back to hardcoded rules for backwards compatibility
    if not rules:
        rules = _get_fallback_compensation_rules()
    
    # Context for rule evaluation
    context = {
        'disruption_type': disruption_type,
        'booking_class': booking_class,
        'flight_distance_km': flight_distance_km or 0,
        'delay_hours': delay_hours or 0,
        'is_international': is_international,
        'airline': airline,
        'origin_country': origin_country,
        'destination_country': destination_country
    }
    
    # Find applicable rules and calculate compensation
    applicable_rules = []
    for rule in rules:
        if _rule_applies(rule, context):
            applicable_rules.append(rule)
    
    # Sort by priority (highest first)
    applicable_rules.sort(key=lambda x: x.priority, reverse=True)
    
    if not applicable_rules:
        return {
            'amount': 0.0,
            'currency': 'USD',
            'reason': 'No applicable compensation rules',
            'rule_applied': None,
            'eligible': False,
            'details': {}
        }
    
    # Apply the highest priority rule
    best_rule = applicable_rules[0]
    
    # Calculate actual amount (may include multipliers)
    final_amount = _calculate_final_amount(best_rule, context)
    
    return {
        'amount': final_amount,
        'currency': 'USD',
        'reason': best_rule.description,
        'rule_applied': best_rule.rule_id,
        'eligible': True,
        'details': {
            'disruption_type': disruption_type,
            'booking_class': booking_class,
            'base_amount': best_rule.amount,
            'multipliers_applied': _get_multipliers(context),
            'all_applicable_rules': [r.rule_id for r in applicable_rules]
        }
    }


def _get_fallback_compensation_rules() -> list[CompensationRule]:
    """Define compensation rules based on various regulations and policies"""
    
    rules = [
        # EU261-inspired rules for international flights
        CompensationRule(
            rule_id="EU261_CANCELLATION_SHORT",
            description="EU261-style compensation for cancelled short-haul flights",
            amount=250.0,
            conditions={
                'disruption_type': 'CANCELLED',
                'flight_distance_km_max': 1500,
                'is_international': True
            },
            priority=90
        ),
        
        CompensationRule(
            rule_id="EU261_CANCELLATION_MEDIUM",
            description="EU261-style compensation for cancelled medium-haul flights",
            amount=400.0,
            conditions={
                'disruption_type': 'CANCELLED',
                'flight_distance_km_min': 1500,
                'flight_distance_km_max': 3500,
                'is_international': True
            },
            priority=90
        ),
        
        CompensationRule(
            rule_id="EU261_CANCELLATION_LONG",
            description="EU261-style compensation for cancelled long-haul flights",
            amount=600.0,
            conditions={
                'disruption_type': 'CANCELLED',
                'flight_distance_km_min': 3500,
                'is_international': True
            },
            priority=90
        ),
        
        # Domestic US compensation rules
        CompensationRule(
            rule_id="US_DOMESTIC_CANCELLATION",
            description="Domestic US flight cancellation compensation",
            amount=200.0,
            conditions={
                'disruption_type': 'CANCELLED',
                'origin_country': 'US',
                'destination_country': 'US'
            },
            priority=80
        ),
        
        # Delay compensation rules
        CompensationRule(
            rule_id="MAJOR_DELAY_3H",
            description="Major delay compensation (3+ hours)",
            amount=150.0,
            conditions={
                'disruption_type': 'DELAYED',
                'delay_hours_min': 3.0
            },
            priority=70
        ),
        
        CompensationRule(
            rule_id="SEVERE_DELAY_6H",
            description="Severe delay compensation (6+ hours)",
            amount=300.0,
            conditions={
                'disruption_type': 'DELAYED',
                'delay_hours_min': 6.0
            },
            priority=75
        ),
        
        # Diversion compensation
        CompensationRule(
            rule_id="FLIGHT_DIVERSION",
            description="Flight diversion compensation",
            amount=250.0,
            conditions={
                'disruption_type': 'DIVERTED'
            },
            priority=85
        ),
        
        # Overbooking compensation
        CompensationRule(
            rule_id="OVERBOOKING_DOMESTIC",
            description="Domestic overbooking compensation",
            amount=400.0,
            conditions={
                'disruption_type': 'OVERBOOKED',
                'is_international': False
            },
            priority=95
        ),
        
        CompensationRule(
            rule_id="OVERBOOKING_INTERNATIONAL",
            description="International overbooking compensation",
            amount=675.0,
            conditions={
                'disruption_type': 'OVERBOOKED',
                'is_international': True
            },
            priority=95
        ),
        
        # Premium class multipliers
        CompensationRule(
            rule_id="BUSINESS_CLASS_BONUS",
            description="Additional compensation for Business class disruptions",
            amount=100.0,
            conditions={
                'booking_class': 'Business'
            },
            priority=50
        ),
        
        CompensationRule(
            rule_id="FIRST_CLASS_BONUS",
            description="Additional compensation for First class disruptions",
            amount=200.0,
            conditions={
                'booking_class': 'First'
            },
            priority=50
        )
    ]
    
    return rules


def _rule_applies(rule: CompensationRule, context: Dict) -> bool:
    """Check if a compensation rule applies to the given context"""
    
    conditions = rule.conditions
    
    for condition, expected_value in conditions.items():
        context_value = context.get(condition.replace('_min', '').replace('_max', ''))
        
        if condition.endswith('_min'):
            if context_value is None or context_value < expected_value:
                return False
        elif condition.endswith('_max'):
            if context_value is None or context_value > expected_value:
                return False
        else:
            if context_value != expected_value:
                return False
    
    return True


def _calculate_final_amount(rule: CompensationRule, context: Dict) -> float:
    """Calculate final compensation amount with any applicable multipliers"""
    
    base_amount = rule.amount
    multipliers = _get_multipliers(context)
    
    final_amount = base_amount
    for multiplier_name, multiplier_value in multipliers.items():
        final_amount *= multiplier_value
    
    # Ensure reasonable bounds
    final_amount = max(0.0, min(final_amount, 2000.0))
    
    return round(final_amount, 2)


def _get_multipliers(context: Dict) -> Dict[str, float]:
    """Get applicable multipliers based on context"""
    
    multipliers = {}
    
    # Premium class multipliers
    booking_class = context.get('booking_class', '').lower()
    if 'business' in booking_class:
        multipliers['business_class'] = 1.5
    elif 'first' in booking_class:
        multipliers['first_class'] = 2.0
    
    # International flight multiplier
    if context.get('is_international'):
        multipliers['international'] = 1.2
    
    # Severe delay multiplier
    delay_hours = context.get('delay_hours', 0)
    if delay_hours >= 12:
        multipliers['severe_delay'] = 1.5
    elif delay_hours >= 8:
        multipliers['major_delay'] = 1.25
    
    return multipliers


def populate_default_rules() -> None:
    """
    Populate the database with default compensation rules if none exist.
    This should be called during system initialization.
    """
    try:
        from ..models import get_all_compensation_rules, create_compensation_rule
        
        # Check if any rules exist
        existing_rules = get_all_compensation_rules()
        if existing_rules:
            print(f"Database already contains {len(existing_rules)} compensation rules")
            return
        
        print("No compensation rules found in database, populating with defaults...")
        
        # Get fallback rules and convert to database format
        default_rules = _get_fallback_compensation_rules()
        
        for rule in default_rules:
            rule_data = {
                'rule_name': rule.description,  # Use description as name for defaults
                'description': rule.description,
                'disruption_type': rule.conditions.get('disruption_type', 'CANCELLED'),
                'amount': rule.amount,
                'conditions': {k: v for k, v in rule.conditions.items() if k != 'disruption_type'},
                'priority': rule.priority
            }
            
            try:
                created_rule = create_compensation_rule(rule_data, created_by="system_initialization")
                print(f"Created default rule: {created_rule.rule_name}")
            except Exception as e:
                print(f"Error creating rule {rule.description}: {str(e)}")
        
        print("Default compensation rules populated successfully")
        
    except ImportError:
        print("Warning: Could not populate default rules - database models not available")
    except Exception as e:
        print(f"Error populating default rules: {str(e)}")


def get_active_rules_summary() -> Dict:
    """
    Get a summary of all active compensation rules
    
    Returns:
        Dict containing rule statistics and summaries
    """
    try:
        from ..models import get_active_compensation_rules, get_all_compensation_rules
        
        active_rules = get_active_compensation_rules()
        all_rules = get_all_compensation_rules()
        
        # Calculate statistics
        stats = {
            'total_rules': len(all_rules),
            'active_rules': len(active_rules),
            'inactive_rules': len(all_rules) - len(active_rules),
            'disruption_types': {}
        }
        
        # Group by disruption type
        for rule in active_rules:
            dtype = rule.disruption_type
            if dtype not in stats['disruption_types']:
                stats['disruption_types'][dtype] = []
            
            stats['disruption_types'][dtype].append({
                'rule_id': rule.rule_id,
                'rule_name': rule.rule_name,
                'amount': rule.amount,
                'priority': rule.priority,
                'conditions': rule.conditions
            })
        
        return stats
        
    except ImportError:
        return {
            'total_rules': 0,
            'active_rules': 0,
            'inactive_rules': 0,
            'disruption_types': {},
            'error': 'Database models not available'
        }
    except Exception as e:
        return {
            'total_rules': 0,
            'active_rules': 0,
            'inactive_rules': 0,
            'disruption_types': {},
            'error': str(e)
        }


def calculate_compensation_with_rule_details(
    disruption_type: str,
    booking_class: str,
    flight_distance_km: Optional[int] = None,
    delay_hours: Optional[float] = None,
    is_international: bool = False,
    airline: Optional[str] = None,
    origin_country: str = "US",
    destination_country: str = "US"
) -> Dict:
    """
    Enhanced compensation calculation that returns detailed rule information
    
    Returns the same result as calculate_compensation but with additional
    rule metadata and evaluation details.
    """
    
    # Get basic compensation result
    result = calculate_compensation(
        disruption_type=disruption_type,
        booking_class=booking_class,
        flight_distance_km=flight_distance_km,
        delay_hours=delay_hours,
        is_international=is_international,
        airline=airline,
        origin_country=origin_country,
        destination_country=destination_country
    )
    
    # Add enhanced rule information
    if result['eligible'] and result['rule_applied']:
        try:
            from ..models import get_compensation_rule_by_id
            rule = get_compensation_rule_by_id(result['rule_applied'])
            
            if rule:
                result['rule_details'] = {
                    'rule_name': rule.rule_name,
                    'version': rule.version,
                    'created_at': rule.created_at.isoformat() if rule.created_at else None,
                    'updated_at': rule.updated_at.isoformat() if rule.updated_at else None,
                    'created_by': rule.created_by,
                    'conditions': rule.conditions
                }
        except ImportError:
            result['rule_details'] = {'error': 'Database models not available'}
        except Exception as e:
            result['rule_details'] = {'error': str(e)}
    
    return result


def get_compensation_summary(booking_id: str, disruption_data: Dict) -> Dict:
    """
    Get a comprehensive compensation summary for a specific booking disruption
    
    Args:
        booking_id: The booking ID
        disruption_data: Dictionary containing disruption details
    
    Returns:
        Detailed compensation summary
    """
    
    compensation_result = calculate_compensation(**disruption_data)
    
    return {
        'booking_id': booking_id,
        'timestamp': datetime.utcnow().isoformat(),
        'compensation': compensation_result,
        'automatic_processing': True,
        'requires_manual_review': compensation_result['amount'] > 1000,
        'estimated_processing_time': '1-2 business days' if compensation_result['eligible'] else 'N/A'
    }


# Test function for compensation calculation
def test_compensation_scenarios():
    """Test various compensation scenarios"""
    
    scenarios = [
        {
            'name': 'Domestic Cancellation - Economy',
            'params': {
                'disruption_type': 'CANCELLED',
                'booking_class': 'Economy',
                'is_international': False,
                'origin_country': 'US',
                'destination_country': 'US'
            }
        },
        {
            'name': 'International Cancellation - Business',
            'params': {
                'disruption_type': 'CANCELLED',
                'booking_class': 'Business',
                'flight_distance_km': 5000,
                'is_international': True
            }
        },
        {
            'name': '4-hour Delay - Economy',
            'params': {
                'disruption_type': 'DELAYED',
                'booking_class': 'Economy',
                'delay_hours': 4.0,
                'is_international': False
            }
        },
        {
            'name': 'Flight Diversion - First Class',
            'params': {
                'disruption_type': 'DIVERTED',
                'booking_class': 'First',
                'is_international': True
            }
        }
    ]
    
    print("Compensation Engine Test Results:")
    print("=" * 50)
    
    for scenario in scenarios:
        result = calculate_compensation(**scenario['params'])
        print(f"\nScenario: {scenario['name']}")
        print(f"Amount: ${result['amount']:.2f}")
        print(f"Eligible: {result['eligible']}")
        print(f"Rule: {result['rule_applied']}")
        print(f"Reason: {result['reason']}")


if __name__ == "__main__":
    # Initialize default rules if needed
    print("Initializing compensation engine...")
    populate_default_rules()
    
    # Run test scenarios
    test_compensation_scenarios()
    
    # Show active rules summary
    print("\n" + "=" * 50)
    print("ACTIVE RULES SUMMARY")
    print("=" * 50)
    
    summary = get_active_rules_summary()
    if 'error' in summary:
        print(f"Error getting rules summary: {summary['error']}")
    else:
        print(f"Total Rules: {summary['total_rules']}")
        print(f"Active Rules: {summary['active_rules']}")
        print(f"Inactive Rules: {summary['inactive_rules']}")
        
        for disruption_type, rules in summary['disruption_types'].items():
            print(f"\n{disruption_type} Rules ({len(rules)}):")
            for rule in rules:
                print(f"  - {rule['rule_name']}: ${rule['amount']} (Priority: {rule['priority']})")
    
    # Test enhanced calculation
    print("\n" + "=" * 50)
    print("ENHANCED CALCULATION TEST")
    print("=" * 50)
    
    enhanced_result = calculate_compensation_with_rule_details(
        disruption_type='CANCELLED',
        booking_class='Business',
        flight_distance_km=5000,
        is_international=True
    )
    
    print(f"Enhanced Result:")
    print(f"Amount: ${enhanced_result['amount']:.2f}")
    print(f"Eligible: {enhanced_result['eligible']}")
    if 'rule_details' in enhanced_result:
        rule_details = enhanced_result['rule_details']
        if 'rule_name' in rule_details:
            print(f"Applied Rule: {rule_details['rule_name']} (v{rule_details['version']})")
            print(f"Created by: {rule_details['created_by']}")
        else:
            print(f"Rule details error: {rule_details}")
    print(f"Reason: {enhanced_result['reason']}")
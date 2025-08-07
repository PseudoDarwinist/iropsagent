# Automatic Compensation Rules System

This document describes the new automatic compensation rules system implemented for the IROPS Agent, allowing travel coordinators to set and manage compensation rules dynamically through a web interface.

## Overview

The compensation rules system consists of:
- **Database Models**: `CompensationRule` and `CompensationRuleHistory` for storing rules and audit trails
- **Admin Web Interface**: Flask-based web application for rule management
- **Integration Layer**: Updated compensation engine that uses database rules instead of hardcoded logic
- **Validation System**: Comprehensive rule validation to prevent conflicts
- **Versioning & Audit**: Complete audit trail for all rule changes

## Key Features

### ✅ Dynamic Rule Management
- Create, edit, activate/deactivate compensation rules through web interface
- Real-time validation to prevent rule conflicts
- Priority-based rule system for handling overlapping conditions

### ✅ Comprehensive Rule Configuration
- Support for all disruption types: CANCELLED, DELAYED, DIVERTED, OVERBOOKED
- Flexible condition system using JSON configuration
- Amount, priority, and activation status management

### ✅ Audit Trail & Versioning
- Complete history of all rule changes
- Version tracking with automatic increment
- User attribution for all modifications

### ✅ Integration with Existing System
- Seamless integration with existing compensation engine
- Backward compatibility with fallback to hardcoded rules
- API endpoints for programmatic access

## Quick Start

### 1. Initialize the System

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database and create sample rules
python3 initialize_compensation_rules.py

# Run comprehensive tests
python3 test_compensation_rules.py
```

### 2. Start the Admin Interface

```bash
# Start the Flask admin application
python3 admin_app.py

# Open in browser
# http://localhost:5000
```

### 3. Use the System

```python
# Use in your code
from flight_agent.tools.compensation_engine import calculate_compensation

result = calculate_compensation(
    disruption_type='CANCELLED',
    booking_class='Business',
    flight_distance_km=5000,
    is_international=True
)

print(f"Compensation: ${result['amount']}")
```

## Database Schema

### CompensationRule Table
- `rule_id` (Primary Key): Unique identifier
- `rule_name`: Human-readable rule name
- `description`: Detailed rule description
- `disruption_type`: CANCELLED, DELAYED, DIVERTED, OVERBOOKED
- `amount`: Base compensation amount (USD)
- `conditions`: JSON object with rule conditions
- `priority`: Rule priority (0-100, higher takes precedence)
- `is_active`: Boolean activation status
- `version`: Rule version number
- `created_at/updated_at`: Timestamps
- `created_by`: User attribution

### CompensationRuleHistory Table
- Complete audit trail of all rule changes
- Links to parent rule via `rule_id`
- Tracks action type (CREATED, UPDATED, DEACTIVATED, DELETED)
- Preserves rule state at time of change

## Rule Conditions

Rules support flexible JSON conditions:

```json
{
  "flight_distance_km_min": 1500,
  "flight_distance_km_max": 3500,
  "delay_hours_min": 3.0,
  "booking_class": "Business",
  "is_international": true,
  "origin_country": "US",
  "destination_country": "US"
}
```

### Common Condition Types
- **Distance**: `flight_distance_km_min`, `flight_distance_km_max`
- **Delay**: `delay_hours_min` (for DELAYED disruption type)
- **Geography**: `origin_country`, `destination_country`, `is_international`
- **Service Class**: `booking_class` (Economy, Business, First)
- **Airline**: `airline` (airline code or name)

## Admin Web Interface

### Main Dashboard (`/`)
- Overview of active/inactive rules
- Statistics by disruption type
- Quick actions and navigation

### Rules List (`/rules`)
- Filterable and sortable list of all rules
- Status indicators (Active/Inactive)
- Bulk operations

### Rule Creation (`/rules/new`)
- Comprehensive form with validation
- JSON condition editor with syntax highlighting
- Real-time validation feedback

### Rule Details (`/rules/<id>`)
- Complete rule information
- Version history and audit trail
- Rule export functionality

### Rule Editing (`/rules/<id>/edit`)
- In-place editing with validation
- Version increment on save
- Change tracking

## API Endpoints

### REST API
- `GET /api/rules` - List all rules (with filters)
- `POST /api/rules/validate` - Validate rule data
- `POST /rules/<id>/toggle` - Activate/deactivate rule

### Python API
```python
from flight_agent.models import (
    create_compensation_rule,
    update_compensation_rule,
    get_active_compensation_rules,
    validate_compensation_rule
)

# Create rule
rule_data = {
    'rule_name': 'New Rule',
    'description': 'Rule description',
    'disruption_type': 'CANCELLED',
    'amount': 250.0,
    'priority': 80
}
rule = create_compensation_rule(rule_data)

# Get active rules
active_rules = get_active_compensation_rules('CANCELLED')
```

## Rule Priority System

Rules are evaluated by priority (highest first):
- **90-100**: Regulatory requirements (EU261, DOT)
- **80-89**: Standard policies
- **60-79**: Premium service adjustments
- **40-59**: Special conditions
- **0-39**: Fallback rules

When multiple rules match a disruption, the highest priority rule is applied.

## Testing

### Comprehensive Test Suite
```bash
python3 test_compensation_rules.py
```

Tests cover:
- Rule validation logic
- CRUD operations
- Version control and audit trail
- Priority system
- Integration with compensation engine
- Database constraints

### Manual Testing
1. Create conflicting rules to test validation
2. Test rule priority with overlapping conditions
3. Verify audit trail after rule changes
4. Test deactivation/reactivation workflow

## Integration Points

### Existing Compensation Engine
The updated `compensation_engine.py`:
- Loads active rules from database first
- Falls back to hardcoded rules if database unavailable
- Maintains backward compatibility
- Adds enhanced calculation functions

### Agent System Integration
Rules integrate seamlessly with existing agent tools:
```python
from flight_agent.tools.compensation_engine import calculate_compensation

# Agent can use this directly
compensation = calculate_compensation(
    disruption_type=event.disruption_type,
    booking_class=booking.booking_class,
    # ... other parameters
)
```

## Security Considerations

### Input Validation
- JSON condition validation
- SQL injection prevention via ORM
- XSS protection in web interface

### Access Control
- Admin interface should be secured with authentication
- API endpoints should validate permissions
- Audit trail preserves user attribution

### Data Integrity
- Database constraints prevent invalid states
- Version control prevents data loss
- Backup recommendations for rule data

## Performance Optimization

### Database Indexing
Recommended indexes:
- `disruption_type` for filtered queries
- `is_active` for active rule lookups
- `priority` for sorting
- `created_at` for audit trail queries

### Caching Strategy
Consider implementing:
- Rule caching with TTL
- Compiled condition evaluation
- Memoized calculation results

## Deployment

### Production Considerations
1. Use PostgreSQL instead of SQLite for production
2. Set up proper Flask secret key
3. Configure logging and monitoring
4. Implement authentication/authorization
5. Set up database backups
6. Monitor rule performance impact

### Environment Variables
```bash
DATABASE_URL=postgresql://user:pass@localhost/irops
FLASK_SECRET_KEY=your-secret-key
```

### Migration Path
For existing systems:
1. Deploy new code with database models
2. Run `initialize_compensation_rules.py` to populate defaults
3. Gradually migrate from hardcoded to database rules
4. Monitor and tune rule performance

## Troubleshooting

### Common Issues

**Database Connection Errors**
- Verify DATABASE_URL is set correctly
- Ensure database tables are created (`Base.metadata.create_all()`)

**Rule Validation Failures**
- Check JSON syntax in conditions
- Verify required fields are present
- Review field type constraints

**Priority Conflicts**
- Use rule validation to identify conflicts
- Adjust priorities to resolve ambiguity
- Consider rule deactivation vs deletion

**Performance Issues**
- Add database indexes for frequently queried fields
- Consider rule caching for high-volume scenarios
- Monitor database query performance

### Debugging
Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

### Planned Features
- Rule templates and duplication
- Bulk rule operations
- Import/export functionality
- Advanced condition operators
- Machine learning rule suggestions
- Integration with external regulatory databases

### API Expansion
- GraphQL interface
- Webhook notifications for rule changes
- Rule simulation and testing tools
- Integration with monitoring systems

## Contributing

### Code Organization
- Models: `flight_agent/models.py`
- Business Logic: `flight_agent/tools/compensation_engine.py`
- Web Interface: `admin_app.py` and `templates/`
- Tests: `test_compensation_rules.py`

### Development Workflow
1. Make changes to models or logic
2. Update tests to cover new functionality
3. Test admin interface manually
4. Run comprehensive test suite
5. Update documentation

This compensation rules system provides a flexible, maintainable foundation for managing passenger compensation policies while maintaining full audit trails and integration with the existing IROPS agent system.
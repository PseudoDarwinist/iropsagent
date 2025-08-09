# Proactive Trip Saver

AI-powered proactive trip management and disruption prevention system integrated with the IROPS Agent.

## Overview

The Proactive Trip Saver extends the IROPS Agent with predictive capabilities, allowing for proactive trip monitoring, intelligent alerts, and AI-generated optimization suggestions before disruptions occur.

## Core Features

- **Proactive Trip Planning**: Monitor planned trips and identify potential issues before they occur
- **Intelligent Alerting**: AI-powered alerts for weather, strikes, airport delays, and price changes
- **Optimization Suggestions**: Machine learning recommendations for rebooking, route alternatives, and cost savings
- **Risk Analysis**: Comprehensive risk assessment for upcoming trips

## Architecture

### Directory Structure
```
trip_saver/
├── __init__.py
├── README.md
├── example_usage.py
├── models/
│   ├── __init__.py
│   └── trip_models.py          # Domain models for trips, alerts, suggestions
├── services/
│   ├── __init__.py
│   ├── trip_planning_service.py # Core trip planning operations
│   ├── alert_service.py         # Alert management and notifications
│   └── suggestion_service.py    # AI-powered suggestions and optimizations
└── tests/
    ├── __init__.py
    ├── test_trip_planning_service.py
    └── test_api.py
```

### Models

1. **TripPlan**: Represents planned trips requiring proactive monitoring
2. **TripAlert**: Proactive alerts for potential trip disruptions
3. **ProactiveSuggestion**: AI-generated optimization recommendations
4. **TripOptimization**: Tracks optimization results and performance metrics

### Services

1. **TripPlanningService**: Manages trip creation, status updates, and risk analysis
2. **AlertService**: Handles alert generation, notification, and lifecycle management
3. **SuggestionService**: Generates and manages AI-powered optimization suggestions

### API

The `trip_saver_api.py` provides RESTful endpoints for:
- Trip management (`/api/trips`)
- Alert management (`/api/alerts`)
- Suggestion management (`/api/suggestions`)
- Monitoring dashboard (`/api/monitoring/trips`)

## Integration with IROPS Agent

The Trip Saver integrates seamlessly with the existing IROPS Agent architecture:
- Extends the existing `flight_agent.models` SQLAlchemy Base
- Uses the same database session management patterns
- Follows established service layer architecture
- Maintains compatibility with existing user and booking models

## Usage Example

```python
from trip_saver.services.trip_planning_service import TripPlanningService
from trip_saver.services.alert_service import AlertService
from trip_saver.services.suggestion_service import SuggestionService

# Initialize services
trip_service = TripPlanningService()
alert_service = AlertService()
suggestion_service = SuggestionService()

# Create a proactive trip plan
trip_data = {
    'trip_name': 'Business Trip to NYC',
    'start_date': datetime.utcnow() + timedelta(days=30),
    'end_date': datetime.utcnow() + timedelta(days=35),
    'origin': 'LAX',
    'destination': 'JFK',
    'priority': 'HIGH'
}
trip = trip_service.create_trip_plan('user123', trip_data)

# Generate proactive alerts
alert_data = {
    'alert_type': 'WEATHER',
    'severity': 'HIGH',
    'title': 'Severe Weather Alert',
    'description': 'Heavy snow expected at destination'
}
alert = alert_service.create_alert(trip.trip_id, alert_data)

# Create optimization suggestions
suggestion_data = {
    'suggestion_type': 'REBOOKING',
    'title': 'Better Flight Available',
    'description': 'Earlier flight saves 2 hours',
    'confidence_score': 0.85,
    'time_savings_minutes': 120
}
suggestion = suggestion_service.create_suggestion(trip.trip_id, suggestion_data)
```

## Testing

Run tests with:
```bash
python -m pytest tests/trip_saver/ -v
```

## API Documentation

Start the API server:
```bash
python trip_saver_api.py
```

The API will be available at `http://localhost:5001`

### Key Endpoints

- `GET /` - System status and statistics
- `POST /api/trips` - Create new trip plan
- `GET /api/trips` - List active trips
- `POST /api/alerts` - Create new alert
- `GET /api/alerts` - List active alerts
- `POST /api/suggestions` - Create new suggestion
- `GET /api/suggestions` - List active suggestions
- `POST /api/suggestions/{id}/respond` - Respond to suggestion
- `GET /api/monitoring/trips` - Get trips requiring monitoring

## Future Enhancements

- External API integration for weather and airline data
- Machine learning models for predictive analytics
- Real-time notification system
- Mobile app integration
- Advanced optimization algorithms
# Design Document - IROPS Agent

## System Architecture Overview

The IROPS Agent follows a multi-agent architecture pattern using Google's Agent Development Kit (ADK), implementing a hierarchical agent coordination system with specialized sub-agents for distinct operational responsibilities.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    IROPS Agent System                      │
├─────────────────────────────────────────────────────────────┤
│  Travel Disruption Coordinator (Root Agent)                │
│  ├── Booking Import Agent                                   │
│  ├── Disruption Monitor Agent                              │
│  └── Rebooking Specialist Agent                            │
├─────────────────────────────────────────────────────────────┤
│  Tool Layer                                                 │
│  ├── Flight Tools (FlightAware API)                        │
│  ├── Booking Tools (Email Parsing)                         │
│  └── Monitor Tools (Bulk Monitoring)                       │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                 │
│  ├── User Management                                        │
│  ├── Booking Storage                                        │
│  └── Disruption Events                                      │
├─────────────────────────────────────────────────────────────┤
│  External APIs                                              │
│  ├── FlightAware AeroAPI                                    │
│  ├── Amadeus Travel API                                     │
│  └── Email Provider APIs                                    │
└─────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Agent Architecture

#### 1.1 Travel Disruption Coordinator (Root Agent)
- **Model**: Gemini-2.5-flash
- **Responsibility**: Master orchestration of all travel disruption management
- **Capabilities**:
  - User interaction and request routing
  - Sub-agent delegation
  - Context management across agent interactions
  - High-level decision making

#### 1.2 Sub-Agents

**Booking Import Agent**
- **Purpose**: Handle flight booking import and management
- **Tools**: Email scanning, manual booking entry
- **Responsibilities**:
  - Parse booking confirmations from email
  - Validate and normalize booking data
  - Store bookings in the database

**Disruption Monitor Agent**
- **Purpose**: Continuous flight status monitoring
- **Tools**: Flight status checking, bulk monitoring
- **Responsibilities**:
  - Check individual flight statuses
  - Detect disruptions (cancellations, significant delays)
  - Classify disruption severity
  - Trigger rebooking workflows

**Rebooking Specialist Agent**
- **Purpose**: Handle alternative flight search and rebooking
- **Tools**: Amadeus API integration, alternative flight search
- **Responsibilities**:
  - Search for alternative flights during disruptions
  - Present options to passengers
  - Process rebooking selections
  - Update booking records

### 2. Data Architecture

#### 2.1 Database Schema

```sql
-- Core Entities
Users
├── user_id (PK)
├── email (unique)
├── phone
├── preferences (JSON)
└── created_at

Bookings
├── booking_id (PK)
├── user_id (FK)
├── pnr
├── airline
├── flight_number
├── departure_date
├── origin/destination
├── booking_class
├── status
└── raw_data (JSON)

DisruptionEvents
├── event_id (PK)
├── booking_id (FK)
├── disruption_type
├── detected_at
├── original_departure
├── new_departure
├── rebooking_status
└── rebooking_options (JSON)

EmailConnections
├── id (PK)
├── user_id (FK)
├── email_provider
├── access_token
└── last_sync
```

#### 2.2 Data Flow

```
Email Import → Booking Extraction → Database Storage
     ↓
Flight Monitoring → Disruption Detection → Event Creation
     ↓
Alternative Search → Option Presentation → Selection Processing
     ↓
Rebooking Execution → Status Update → User Notification
```

### 3. Tool Architecture

#### 3.1 Flight Tools Module
```python
# Primary Functions
- get_flight_status(flight_identifier) → flight_data
- find_alternative_flights(origin, destination, date) → flight_options
- check_my_flights(user_id) → user_flight_list
```

#### 3.2 Booking Tools Module
```python
# Primary Functions
- scan_email_for_bookings(email_credentials) → booking_list
- manual_booking_entry(booking_details) → booking_record
- validate_booking_data(raw_booking) → normalized_booking
```

#### 3.3 Monitor Tools Module
```python
# Primary Functions
- check_all_monitored_flights() → disruption_list
- schedule_monitoring_job(booking_id) → job_id
- process_disruption_event(event_data) → processed_event
```

## API Integration Design

### 4.1 FlightAware Integration
- **Purpose**: Real-time flight status data
- **Endpoint**: `https://aeroapi.flightaware.com/aeroapi/flights/{flight_id}`
- **Authentication**: API key header
- **Rate Limits**: Managed with exponential backoff
- **Data Processing**: Status normalization and disruption classification

### 4.2 Amadeus Integration
- **Purpose**: Alternative flight search and booking
- **Authentication**: OAuth 2.0 client credentials
- **Key Endpoints**:
  - Flight Offers Search
  - Flight Offers Price
  - Flight Create Orders
- **Error Handling**: Comprehensive API error mapping

### 4.3 Email Provider Integration
- **Supported Providers**: Gmail, Outlook
- **Authentication**: OAuth 2.0 with refresh tokens
- **Booking Detection**: Pattern matching and ML-based extraction
- **Privacy**: Minimal data retention, encrypted storage

## Security Design

### 5.1 Secrets Management
- **Environment Variables**: All API keys via environment configuration
- **Encryption**: Sensitive data encrypted at rest
- **Access Control**: Role-based access to booking data
- **Audit Logging**: Comprehensive operation logging

### 5.2 Data Privacy
- **PII Protection**: Minimal collection, encrypted storage
- **Consent Management**: Explicit user consent for email access
- **Data Retention**: Configurable retention policies
- **GDPR Compliance**: Right to deletion and data portability

## Performance Design

### 6.1 Monitoring Strategy
- **Batch Processing**: Efficient bulk status checks
- **Caching**: Flight data caching with TTL
- **Async Operations**: Non-blocking I/O for API calls
- **Connection Pooling**: Efficient database connections

### 6.2 Scalability Considerations
- **Horizontal Scaling**: Stateless agent design
- **Load Balancing**: Multiple agent instances
- **Database Optimization**: Indexed queries, connection pooling
- **API Rate Management**: Distributed rate limiting

## Error Handling Design

### 7.1 API Failure Patterns
```python
# Retry Strategy
- Exponential backoff for temporary failures
- Circuit breaker for persistent failures
- Fallback mechanisms for critical operations
- Graceful degradation when external services fail
```

### 7.2 Agent Error Recovery
- **Context Preservation**: Maintain conversation state during errors
- **Graceful Fallbacks**: Alternative approaches when primary methods fail
- **User Communication**: Clear error messages and recovery options
- **Logging**: Comprehensive error tracking for debugging

## Testing Strategy

### 8.1 Unit Testing
- **Agent Behavior**: Mock external APIs for isolated testing
- **Tool Functions**: Comprehensive input/output validation
- **Data Models**: Database operation testing
- **API Integration**: Mock responses for various scenarios

### 8.2 Integration Testing
- **End-to-End Workflows**: Complete user journey testing
- **API Integration**: Real API testing in staging environment
- **Multi-Agent Coordination**: Agent interaction testing
- **Error Scenarios**: Failure mode testing

### 8.3 Performance Testing
- **Load Testing**: Multiple concurrent user simulation
- **API Rate Limits**: Boundary condition testing
- **Database Performance**: Query optimization validation
- **Memory Usage**: Resource consumption monitoring

## Deployment Architecture

### 9.1 Environment Configuration
```
Development
├── Local SQLite database
├── Mock API responses
└── Development API keys

Staging
├── PostgreSQL database
├── Real API integration
└── Staging API keys

Production
├── PostgreSQL with replication
├── Production API keys
└── Monitoring and alerting
```

### 9.2 Configuration Management
- **Environment Variables**: All environment-specific settings
- **Secret Management**: Secure API key storage
- **Database Migrations**: Version-controlled schema updates
- **Deployment Scripts**: Automated deployment process

## Monitoring and Observability

### 10.1 Application Metrics
- Response times for each agent operation
- API call success/failure rates
- Disruption detection accuracy
- User satisfaction metrics

### 10.2 System Health
- Database connection health
- External API availability
- Agent response times
- Error rate monitoring

### 10.3 Business Metrics
- Booking import success rate
- Disruption detection speed
- Rebooking completion rate
- User engagement levels

## Future Architecture Considerations

### 11.1 Scalability Enhancements
- Microservices decomposition
- Event-driven architecture
- Message queue integration
- Distributed caching

### 11.2 AI/ML Enhancements
- Predictive disruption modeling
- Personalized rebooking recommendations
- Natural language understanding improvements
- Automated preference learning

### 11.3 Integration Expansions
- Additional airline APIs
- Hotel and ground transportation
- Travel insurance integration
- Corporate travel management systems

## Implementation Guidelines

### 12.1 Code Organization
```
flight_agent/
├── agents/           # Agent definitions
├── tools/           # Tool implementations
├── models/          # Data models
├── services/        # Business logic
├── integrations/    # External API clients
└── utils/           # Shared utilities
```

### 12.2 Development Standards
- **Code Style**: Follow PEP 8 guidelines
- **Documentation**: Comprehensive docstrings
- **Testing**: Minimum 80% code coverage
- **Error Handling**: Consistent exception patterns
- **Logging**: Structured logging throughout

### 12.3 Security Guidelines
- **No Hardcoded Secrets**: Environment-based configuration only
- **Input Validation**: Sanitize all external inputs
- **Access Control**: Principle of least privilege
- **Audit Trails**: Log all sensitive operations

This design document provides the architectural foundation for implementing a robust, scalable, and secure flight disruption management system using AI agents.
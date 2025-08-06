# IROPS Agent - Flight Disruption Management System

An AI-powered flight disruption management system built with Google's Agent Development Kit (ADK). The system automatically monitors flight bookings, detects disruptions, and coordinates rebooking options for affected passengers.

## Features

- 🤖 **Multi-Agent Architecture**: Specialized AI agents for different tasks
- ✈️ **Real-time Flight Monitoring**: Continuous status checking using FlightAware API
- 🔄 **Automated Rebooking**: Alternative flight search using Amadeus API
- 📧 **Email Integration**: Import bookings from email confirmations
- 💾 **Persistent Storage**: SQLAlchemy-based data management
- 🛡️ **Security**: Environment-based secret management

## Architecture

The system uses a hierarchical multi-agent architecture:

- **Travel Coordinator** (Root Agent): Orchestrates all operations
- **Booking Import Agent**: Handles flight booking import and management
- **Disruption Monitor Agent**: Monitors flights for disruptions
- **Rebooking Specialist Agent**: Manages alternative flight search and rebooking

## Prerequisites

- Python 3.8+
- Google AI Studio API key
- FlightAware AeroAPI key
- Amadeus Travel API credentials (optional, for rebooking)
- Email API credentials (optional, for booking import)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd iropsagent
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual API keys
   ```

4. **Initialize the database**
   ```bash
   python -c "from flight_agent.models import Base, engine; Base.metadata.create_all(bind=engine)"
   ```

## Configuration

### Required Environment Variables

```bash
# Google AI Studio API Key (Required)
GOOGLE_API_KEY=your_google_api_key_here

# FlightAware API Key (Required for flight monitoring)
FLIGHTAWARE_API_KEY=your_flightaware_api_key_here

# Amadeus API (Optional, for rebooking features)
AMADEUS_CLIENT_ID=your_amadeus_client_id_here
AMADEUS_CLIENT_SECRET=your_amadeus_client_secret_here

# Database URL (Optional, defaults to SQLite)
DATABASE_URL=sqlite:///./travel_disruption.db
```

### API Key Setup

1. **Google AI Studio**: Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. **FlightAware**: Register at [FlightAware AeroAPI](https://www.flightaware.com/commercial/aeroapi/)
3. **Amadeus**: Get credentials from [Amadeus for Developers](https://developers.amadeus.com/)

## Usage

### Running the Application

**Option 1: Programmatic Execution**
```bash
python flight_agent_app.py
```

**Option 2: ADK Web Interface**
```bash
adk web
```

**Option 3: ADK CLI**
```bash
adk run
```

### Example Interactions

**Check Flight Status**
```
User: "Please check the status of flight BA249"
Agent: [Checks flight status and reports current information]
```

**Handle Disruption**
```
User: "My flight AA100 was cancelled. Can you find alternatives?"
Agent: [Searches for alternative flights and presents options]
```

**Import Booking**
```
User: "I have a new booking confirmation email"
Agent: [Guides through booking import process]
```

## Project Structure

```
iropsagent/
├── flight_agent/                 # Main package
│   ├── agents/                   # Agent definitions
│   │   ├── coordinator.py        # Root coordinator agent
│   │   └── sub_agents/           # Specialized sub-agents
│   ├── tools/                    # Tool implementations
│   │   ├── flight_tools.py       # Flight status and search
│   │   ├── booking_tools.py      # Booking import and management
│   │   └── monitor_tools.py      # Monitoring operations
│   ├── models.py                 # Database models
│   └── __init__.py
├── flight_agent_app.py           # Main application entry point
├── requirements.txt              # Python dependencies
├── requirements.md               # Functional requirements
├── design.md                     # System design document
├── .env.example                  # Environment configuration template
└── README.md                     # This file
```

## Database Schema

The system uses SQLAlchemy with the following main entities:

- **Users**: User profiles and preferences
- **Bookings**: Flight booking details
- **DisruptionEvents**: Disruption tracking and resolution
- **EmailConnections**: Email integration for booking import

## API Integration

### FlightAware AeroAPI
- **Purpose**: Real-time flight status data
- **Rate Limits**: Managed with exponential backoff
- **Error Handling**: Comprehensive retry logic

### Amadeus Travel API
- **Purpose**: Alternative flight search and booking
- **Authentication**: OAuth 2.0 client credentials
- **Features**: Flight search, pricing, booking creation

## Security Considerations

- ✅ **No Hardcoded Secrets**: All API keys via environment variables
- ✅ **Input Validation**: Sanitized external inputs
- ✅ **Error Handling**: Secure error messages
- ✅ **Data Encryption**: Sensitive data encrypted at rest

## Development

### Running Tests
```bash
python -m pytest tests/ -v
```

### Code Style
The project follows PEP 8 guidelines. Format code with:
```bash
black flight_agent/
flake8 flight_agent/
```

### Adding New Features

1. **New Agent**: Create in `flight_agent/agents/sub_agents/`
2. **New Tool**: Add to appropriate module in `flight_agent/tools/`
3. **Database Changes**: Add migrations in `flight_agent/models.py`
4. **Tests**: Add corresponding tests in `tests/`

## Troubleshooting

### Common Issues

**API Key Errors**
```
ValueError: GOOGLE_API_KEY environment variable is required but not set
```
- Solution: Ensure all required API keys are set in your `.env` file

**Database Connection Issues**
```
sqlalchemy.exc.OperationalError: unable to open database file
```
- Solution: Ensure database directory exists and is writable

**Import Errors**
```
ModuleNotFoundError: No module named 'google.adk'
```
- Solution: Install dependencies with `pip install -r requirements.txt`

### Debug Mode

Enable debug logging by setting:
```bash
LOG_LEVEL=DEBUG
DEBUG=true
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions and support:
- Review the [requirements.md](requirements.md) for functional specifications
- Check the [design.md](design.md) for architectural details
- Open an issue for bugs or feature requests

## Roadmap

- [ ] Mobile application interface
- [ ] SMS/push notification integration
- [ ] Multi-language support
- [ ] Advanced passenger preference learning
- [ ] Integration with loyalty programs
- [ ] Predictive disruption analytics
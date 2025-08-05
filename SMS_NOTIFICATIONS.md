# SMS Notifications for Urgent Flight Changes

This document explains the SMS notification system implemented for urgent flight disruptions.

## Overview

The SMS notification system provides immediate alerts to users when their flights experience high-priority disruptions such as cancellations or diversions. This ensures users are notified even when offline.

## Features Implemented

### 1. SMS Sending via Twilio API
- **File**: `flight_agent/tools/communication_tools.py`
- Integration with Twilio REST API for reliable SMS delivery
- Support for international phone numbers in E.164 format
- Error handling and status reporting

### 2. Phone Number Validation and Formatting
- Automatic formatting of phone numbers to E.164 format
- Support for various input formats (US domestic, international)
- Validation to prevent invalid numbers

### 3. SMS Message Templates
- **Cancellation**: Urgent alert with alternative finding mention
- **Delay**: Time change information with monitoring advice
- **Diversion**: Alert with email reference for details
- **Generic**: Fallback template for other disruptions
- All messages include timestamp and concise information

### 4. Rate Limiting
- **Hourly limit**: 5 SMS per phone number per hour (configurable)
- **Daily limit**: 20 SMS per phone number per day (configurable)
- Prevents spam and reduces costs
- Automatic cleanup of old rate limit entries

### 5. User SMS Preferences
- **Database Integration**: Uses existing `preferences` JSON column in User model
- **Settings**: Enable/disable SMS notifications, urgent-only option
- **Phone Management**: Phone number storage and validation
- **Easy Management**: Functions to update preferences

### 6. High-Priority Disruption Detection
- **Priority System**: HIGH, MEDIUM, LOW priority levels
- **Automatic Triggering**: High-priority disruptions trigger SMS
- **Disruption Types**: 
  - CANCELLED → HIGH priority
  - DIVERTED → HIGH priority
  - DELAYED → MEDIUM priority (SMS only if >30 minutes)

### 7. Integration with Monitoring System
- **Auto-Detection**: Monitor system detects disruptions and triggers SMS
- **Batch Processing**: Handle multiple disruptions efficiently
- **Status Tracking**: Track notification status per disruption

## Configuration

### Environment Variables
Add to your `.env` file:
```bash
# Twilio SMS Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890
```

### Database Schema
The system uses existing database schema with enhancements:
- `users.phone`: Phone number storage
- `users.preferences`: SMS preferences in JSON format
- `disruption_events.priority`: Priority level for SMS filtering

## Usage

### Enable SMS for a User
```python
from flight_agent.tools.communication_tools import update_sms_preferences

# Enable SMS notifications for urgent disruptions only
update_sms_preferences("user@example.com", enabled=True, urgent_only=True)
```

### Manual SMS Sending
```python
from flight_agent.tools.communication_tools import send_manual_sms

# Send a test SMS
send_manual_sms("user@example.com", "Test message from Flight Agent")
```

### Check SMS System Status
```python
from flight_agent.tools.communication_tools import get_sms_status

# Get system status
status = get_sms_status()
print(status)
```

### Monitor and Send Disruption SMS
```python
from flight_agent.tools.monitor_tools import detect_and_process_disruptions

# Detect disruptions and send SMS for high-priority ones
result = detect_and_process_disruptions()
print(result)
```

## SMS Message Examples

### Flight Cancellation
```
🚨 FLIGHT ALERT: UA1234 (ORD->SFO) has been CANCELLED. We're finding alternatives. Check email for details. Alert sent at 14:30
```

### Flight Delay
```
⏰ FLIGHT DELAY: UA1234 (ORD->SFO) delayed from 14:30 to 16:45. Monitor for updates. Alert sent at 14:30
```

### Flight Diversion
```
✈️ FLIGHT DIVERSION: UA1234 (ORD->SFO) has been diverted. Check email for new destination and arrangements. Alert sent at 14:30
```

## Rate Limiting Details

The system prevents SMS spam through:
- **5 SMS per hour** per phone number
- **20 SMS per day** per phone number
- Automatic cleanup of old entries
- Configurable limits per instance

## Error Handling

The system handles various error conditions:
- Invalid phone numbers (formatted or rejected)
- Twilio API errors (logged and reported)
- Rate limit exceeded (graceful rejection)
- Missing credentials (clear error messages)
- Database connection issues (transaction safety)

## Testing

### Core Function Tests
Run the direct communication tests:
```bash
python test_communication_direct.py
```

### Full Integration Tests
For complete testing with database:
```bash
python test_sms_notifications.py
```

## Dependencies

- `twilio`: SMS sending via Twilio API
- `sqlalchemy`: Database operations
- `python-dotenv`: Environment variable management
- `re`: Phone number formatting

## Security Considerations

- Phone numbers are validated before storage
- Rate limiting prevents abuse
- Twilio credentials stored securely in environment variables
- No sensitive information in SMS messages
- User opt-in required for SMS notifications

## Cost Management

- Rate limiting reduces unnecessary SMS costs
- Priority-based sending (only urgent disruptions)
- User preferences allow opt-out
- Message templates are concise to minimize character count

## Future Enhancements

- Redis-based rate limiting for production scale
- SMS delivery status tracking
- International carrier support optimization
- Advanced message personalization
- Integration with push notifications as fallback
# SMS Notifications for Flight Disruptions

This implementation provides SMS notifications for urgent flight changes using the Twilio API.

## Features

✅ **SMS sending functionality** using Twilio API  
✅ **SMS message templates** with concise disruption information  
✅ **Phone number validation** and formatting utilities  
✅ **Rate limiting** for SMS notifications (5 SMS per user per hour)  
✅ **SMS preferences** in user model  
✅ **High-priority disruption triggers** for SMS notifications  

## High-Priority Disruptions

SMS notifications are automatically sent for:

- **Cancelled flights** (always high priority)
- **Diverted flights** (always high priority)  
- **Delays of 2+ hours** (high priority)
- **Same-day flight delays** (high priority)

## Setup Instructions

### 1. Twilio Account Setup

1. Create a [Twilio account](https://www.twilio.com/try-twilio)
2. Get your Account SID and Auth Token from the Twilio Console
3. Purchase a Twilio phone number for sending SMS

### 2. Environment Configuration

Copy `.env.example` to `.env` and fill in your Twilio credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your Twilio credentials:

```env
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here  
TWILIO_PHONE_NUMBER=+1234567890
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Test the SMS System

Run the test script to verify everything is working:

```bash
python test_sms_notifications.py
```

## Usage

### Enable SMS for a User

```python
from flight_agent.tools.communication_tools import update_user_sms_preferences

# Enable SMS notifications for a user
result = update_user_sms_preferences(
    user_id="user123",
    sms_enabled=True,
    phone="+15551234567"
)
```

### Process High-Priority Disruptions

```python
from flight_agent.tools.communication_tools import process_high_priority_disruptions

# Check for and send SMS alerts for high-priority disruptions
summary = process_high_priority_disruptions()
print(summary)
```

### Test SMS Functionality

```python
from flight_agent.tools.communication_tools import test_sms_functionality

# Send a test SMS to a user
result = test_sms_functionality("user@example.com", "Test message")
print(result)
```

## SMS Message Templates

### Cancellation
```
🚨 URGENT: Flight AA123 (LAX-JFK) has been CANCELLED. We're finding alternatives. Check app for rebooking options. Reply STOP to opt out.
```

### Delay
```
⏰ Flight AA123 (LAX-JFK) DELAYED to 3:45 PM. Monitor for updates. Reply STOP to opt out.
```

### Diversion
```
✈️ Flight AA123 (LAX-JFK) has been DIVERTED. Check app for new arrival details. Reply STOP to opt out.
```

## Rate Limiting

- **Limit**: 5 SMS per user per hour
- **Purpose**: Prevent spam and control costs
- **Implementation**: In-memory tracking (use Redis for production)

## Database Schema Changes

### User Model
- `phone` column already exists for phone numbers
- `preferences` JSON column stores SMS preferences:
  ```json
  {
    "sms_notifications_enabled": true
  }
  ```

### DisruptionEvent Model  
- Added `sms_sent` boolean column to track SMS delivery

## Phone Number Validation

The system validates and formats phone numbers to E.164 format:

- US 10-digit: `5551234567` → `+15551234567`
- US with country code: `15551234567` → `+15551234567`  
- Formatted: `(555) 123-4567` → `+15551234567`
- International: `+442079460958` (UK format)

## Integration with Flight Agent

The SMS functionality is integrated into the main flight agent system:

1. **Monitoring**: Flight monitoring detects disruptions
2. **Classification**: System determines if disruption is high-priority
3. **SMS Trigger**: High-priority disruptions automatically trigger SMS
4. **User Preferences**: Only users with SMS enabled receive notifications
5. **Rate Limiting**: Prevents spam and excessive SMS costs

## Error Handling

The system handles various error conditions:

- **Invalid phone numbers**: Validation prevents sending to invalid numbers
- **Missing Twilio credentials**: Graceful degradation with error messages
- **Rate limit exceeded**: Prevents sending when user hits rate limit
- **Twilio API errors**: Captures and reports Twilio service issues
- **User not found**: Handles missing user records

## Testing Checklist

- [ ] Phone number validation works correctly
- [ ] Twilio client initializes with credentials
- [ ] User SMS preferences can be updated
- [ ] Test SMS can be sent successfully  
- [ ] High-priority disruptions trigger SMS
- [ ] Rate limiting prevents spam
- [ ] Error conditions are handled gracefully

## Production Considerations

1. **Rate Limiting**: Replace in-memory rate limiting with Redis for scalability
2. **Database**: Use PostgreSQL instead of SQLite for production
3. **Monitoring**: Add logging and monitoring for SMS delivery
4. **Cost Control**: Implement spending alerts and SMS quotas
5. **Security**: Secure Twilio credentials using proper secret management
6. **Compliance**: Ensure SMS opt-out compliance and data privacy

## API Reference

### Core Functions

- `send_sms_notification(user_id, message)` - Send SMS to specific user
- `process_high_priority_disruptions()` - Process all high-priority disruptions  
- `update_user_sms_preferences(user_id, enabled, phone)` - Update user SMS settings
- `validate_phone_number(phone)` - Validate phone number format
- `format_phone_number(phone)` - Format to E.164 standard
- `test_sms_functionality(email, message)` - Send test SMS

### Database Functions

- `create_disruption_event()` - Create new disruption event
- `get_unnotified_high_priority_disruptions()` - Get disruptions needing SMS
- `mark_disruption_sms_sent()` - Mark disruption as SMS sent
- `get_users_with_sms_enabled()` - Get users with SMS enabled
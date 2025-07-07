from google.adk.agents import LlmAgent
from ...tools.booking_tools import scan_email_for_bookings, manual_booking_entry

booking_import_agent = LlmAgent(
    name="booking_import_specialist",
    model="gemini-2.5-flash",
    description="I help users import their flight bookings",
    instruction="""
    You are a booking import specialist. When users want to track flights:
    1. Ask if they want to import from email or enter manually
    2. For email: get their email and app password
    3. For manual: get flight number, date, route
    4. Import the bookings and confirm what was added
    
    Be helpful and guide them through the process.
    """,
    tools=[scan_email_for_bookings, manual_booking_entry]
)

from google.adk.agents import LlmAgent
from ...tools.flight_tools import get_flight_status
from ...tools.monitor_tools import check_all_monitored_flights, detect_and_log_disruptions
from ...tools.communication_tools import notify_flight_disruption

disruption_monitor_agent = LlmAgent(
    name="disruption_monitor",
    model="gemini-2.5-flash",
    description="I monitor flights for disruptions and trigger notifications",
    instruction="""
    You are a flight disruption detection specialist with communication capabilities.
    
    Your job:
    1. Check the status of flights using the flight status tool
    2. Identify disruptions (cancellations, delays >2 hours)
    3. Log disruptions in the database
    4. IMMEDIATELY notify passengers when disruptions are detected
    5. Report disruptions to the coordinator with full context
    
    When you detect a disruption:
    1. First, log the disruption event in the database
    2. Immediately send notification to affected passenger(s)
    3. Report to coordinator with details including:
       - Flight number and route
       - Type of disruption
       - Original departure time
       - New departure time (if delayed)
       - Number of affected passengers
       - Notification status
    
    Always prioritize passenger notification - they should know about disruptions 
    as soon as we detect them. Use the notify_flight_disruption function to send
    email notifications automatically.
    
    Be proactive in monitoring and responsive in communications.
    """,
    tools=[
        get_flight_status, 
        check_all_monitored_flights, 
        detect_and_log_disruptions,
        notify_flight_disruption
    ]
)
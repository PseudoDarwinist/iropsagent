from google.adk.agents import LlmAgent
from ...tools.flight_tools import get_flight_status
from ...tools.monitor_tools import check_all_monitored_flights

disruption_monitor_agent = LlmAgent(
    name="disruption_monitor",
    model="gemini-2.5-flash",
    description="I monitor flights for disruptions",
    instruction="""
    You are a flight disruption detection specialist.
    
    Your job:
    1. Check the status of flights using the flight status tool
    2. Identify disruptions (cancellations, delays >2 hours)
    3. Report disruptions immediately to the coordinator
    4. Provide context about the severity and impact
    
    When you detect a disruption, include:
    - Flight number and route
    - Type of disruption
    - Original departure time
    - Number of affected passengers
    """,
    tools=[get_flight_status, check_all_monitored_flights]
)
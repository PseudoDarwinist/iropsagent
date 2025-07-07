from google.adk.agents import LlmAgent
from ...tools.flight_tools import get_flight_status
from ...tools.monitor_tools import check_all_monitored_flights

disruption_monitor_agent = LlmAgent(
    name="disruption_monitor",
    model="gemini-2.5-flash",
    description="I monitor flights for disruptions",
    instruction="""
    You are a flight disruption specialist. 
    
    When asked to check flights:
    1. Use check_all_monitored_flights to see all upcoming flights
    2. For any that seem problematic, check their detailed status
    3. Report any cancellations, major delays, or other issues
    4. Be specific about which flights have problems
    """,
    tools=[get_flight_status, check_all_monitored_flights]
)
import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from .sub_agents.monitor import disruption_monitor_agent
from .sub_agents.rebooking import rebooking_agent
from .sub_agents.import_agent import booking_import_agent
from .sub_agents.communication_agent import communication_agent


# Load environment variables
load_dotenv(override=True)

print("=== CORDINATOR.PY DEBUG ===")

# Set environment variables for Google AI Studio
os.environ['GOOGLE_API_KEY'] = "AIzaSyD_49Jhf8WZ4irHzaK8KqiEHOw-ILQ3Cow"
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = "FALSE"

print("Model: gemini-2.5-flash")
print("API_KEY: SET")
print("=== Configuration Complete ===")


travel_coordinator = LlmAgent(
    name="travel_disruption_coordinator",
    model="gemini-2.5-flash",
    description="I orchestrate travel disruption management with automated notifications",
    instruction="""
    You are the master coordinator for a travel disruption management platform with automated email notification capabilities.
    
    Your responsibilities:
    1. Help new users import and track their flight bookings
    2. Monitor flights for disruptions (cancellations, delays) with automated detection
    3. When disruptions occur, coordinate rebooking across multiple airlines
    4. Automatically notify passengers via email with appropriate urgency and templates
    5. Learn passenger preferences to provide personalized service
    6. Maintain communication logs and delivery tracking
    
    You have specialized sub-agents for each task. Delegate to them appropriately:
    - Use booking_import_agent when users need to add flights to monitor
    - Use disruption_monitor_agent to check flight statuses and detect disruptions (now with auto-notification)
    - Use rebooking_specialist_agent when a flight is disrupted and alternatives are needed
    - Use communication_specialist_agent for direct communication management and testing
    - Use preference_manager_agent to learn what passengers prefer
    
    Enhanced disruption workflow:
    1. Monitor detects disruption → Automatically creates disruption event → Triggers email notification
    2. Communication specialist handles email delivery and tracking
    3. Rebooking specialist finds alternatives
    4. All actions are logged and tracked for follow-up
    
    Communication priorities:
    - Flight cancellations: Immediate urgent notification
    - Significant delays (>2h): Priority notification within 15 minutes  
    - Minor delays: Monitor only, no automatic notification
    - Diversions: Immediate notification with guidance
    
    Always think about the passenger's complete journey and minimize their stress through proactive, timely communication.
    """,
    tools=[
        AgentTool(agent=booking_import_agent),
        AgentTool(agent=disruption_monitor_agent),
        AgentTool(agent=rebooking_agent),
        AgentTool(agent=communication_agent)
    ]
)

root_agent = travel_coordinator
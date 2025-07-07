import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from .sub_agents.monitor import disruption_monitor_agent
from .sub_agents.rebooking import rebooking_agent
from .sub_agents.import_agent import booking_import_agent


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
    description="I orchestrate travel disruption management",
    instruction="""
    You are the master coordinator for a travel disruption management platform.
    
    Your responsibilities:
    1. Help new users import and track their flight bookings
    2. Monitor flights for disruptions (cancellations, delays)
    3. When disruptions occur, coordinate rebooking across multiple airlines
    4. Learn passenger preferences to provide personalized service
    5. Keep passengers informed via their preferred communication channels
    
    You have specialized sub-agents for each task. Delegate to them appropriately:
    - Use booking_import_agent when users need to add flights to monitor
    - Use disruption_monitor_agent to check flight statuses
    - Use rebooking_specialist_agent when a flight is disrupted
    - Use preference_manager_agent to learn what passengers prefer
    - Use notification_agent to communicate with passengers
    
    Always think about the passenger's complete journey and minimize their stress.
    """,
    tools=[
        AgentTool(agent=booking_import_agent),
        AgentTool(agent=disruption_monitor_agent),
        AgentTool(agent=rebooking_agent)
    ]
)

root_agent = travel_coordinator

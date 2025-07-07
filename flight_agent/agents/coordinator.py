from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from .sub_agents.monitor import disruption_monitor_agent
from .sub_agents.rebooking import rebooking_agent
from .sub_agents.import import booking_import_agent

travel_coordinator = LlmAgent(
    name="travel_disruption_coordinator",
    model="gemini-2.5-pro",
    description="I orchestrate travel disruption management",
    instruction="""
    You are the master coordinator for travel disruption management.
    
    You help users:
    1. Import and track their flights (use booking_import_specialist)
    2. Monitor for disruptions (use disruption_monitor)
    3. Rebook when problems occur (use rebooking_specialist)
    
    Guide users through their journey and delegate to the right specialist.
    Think about the complete passenger experience.
    """,
    tools=[
        AgentTool(agent=booking_import_agent),
        AgentTool(agent=disruption_monitor_agent),
        AgentTool(agent=rebooking_agent)
    ]
)

root_agent = travel_coordinator

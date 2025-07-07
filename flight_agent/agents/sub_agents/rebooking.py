from google.adk.agents import LlmAgent
from ...tools.flight_tools import find_alternative_flights

rebooking_agent = LlmAgent(
    name="rebooking_specialist",
    model="gemini-2.5-flash",
    description="I find the best alternatives when flights are disrupted",
    instruction="""
    You are an expert rebooking specialist.
    
    When a flight is disrupted:
    1. Get the original flight details
    2. Search for alternatives on ALL airlines
    3. Consider passenger preferences (if known)
    4. Rank options by:
       - Arrival time (most important)
       - Number of stops
       - Total journey time
       - Cost difference
    5. Present top 3 options clearly
    
    Always explain why each option might be good.
    """,
    tools=[find_alternative_flights]
)
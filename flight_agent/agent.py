import os
from google.adk.agents import LlmAgent
from dotenv import load_dotenv
from .tools import get_flight_status, find_alternative_flights, check_my_flights


# Load environment variables
load_dotenv(override=True)

print("=== AGENT.PY DEBUG ===")
print("Using Google AI Studio with direct model string")

# --- GOOGLE AI STUDIO CONFIGURATION (from official docs) ---
# Set environment variables for Google AI Studio
os.environ['GOOGLE_API_KEY'] = "AIzaSyD_49Jhf8WZ4irHzaK8KqiEHOw-ILQ3Cow"
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = "FALSE"

print("Model: gemini-2.5-flash")
print("API_KEY: SET")
print("=== Configuration Complete ===")

# Use direct model string as per ADK documentation
# No need for LiteLlm wrapper when using Google AI Studio
root_agent = LlmAgent(
    name="FlightDisruptionCoordinator",
    model="gemini-2.5-flash",
    instruction=(
        "You are a flight disruption coordinator that helps passengers with flight issues. "
        "When a user asks about flight status, you MUST call the get_flight_status function. "
        "When a user asks about alternative flights, you MUST call the find_alternative_flights function. "
        "When a user asks about their flights, you MUST call the check_my_flights function with their email. "
        "NEVER provide flight information without calling the appropriate tools first. "
        "Always use the tools to get real-time data."
    ),
    tools=[get_flight_status, find_alternative_flights, check_my_flights],
)
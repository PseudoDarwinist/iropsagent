import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Import the agent from the agent package
from flight_agent.agents.coordinator import root_agent
# Import the tools from the agent package


# Import ALL tools that agents might use
from flight_agent.tools.flight_tools import (
    get_flight_status, 
    find_alternative_flights,
    check_my_flights
)
from flight_agent.tools.booking_tools import (
    scan_email_for_bookings,
    manual_booking_entry
)
from flight_agent.tools.monitor_tools import (
    check_all_monitored_flights
)


# --- RUNNING THE SYSTEM PROGRAMMATICALLY ---
async def main():
    """
    Sets up the ADK Runner and executes a sample conversation with the agent.
    This script is for programmatic execution and testing.
    """
    # 1. Set up a session service
    session_service = InMemorySessionService()
    APP_NAME = "flight_disruption_app"
    USER_ID = "test_user_123"
    SESSION_ID = "flight_session_abc"

    session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )
    print("Session created for user and app.")

    # 2. Create a Runner for your root agent and provide the tool implementations
    # The runner needs to know the agent and which tools it can execute.
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service
    )
    print("Runner initialized.")

    # 3. Run the agent with an example prompt
    # Example 1: A flight that might be found
    user_message_text_1 = "Please check the status of flight BA249"
    user_message_1 = types.Content(role="user", parts=[types.Part(text=user_message_text_1)])

    print(f"\n--- Conversation 1 ---")
    print(f"User: {user_message_text_1}")

    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=user_message_1
        ):
            if event.is_final_response():
                print(f"Agent: {event.content.parts[0].text}")
            elif event.is_agent_action():
                print(f"Agent Action: {event.tool_code_log.tool_name}({event.tool_code_log.args})")
            elif event.is_observation():
                print(f"Observation: {event.tool_code_log.result}")

    except Exception as e:
        print(f"\nAn error occurred during agent execution: {e}")
        print("Please ensure your middleware LLM endpoint is running, accessible, and correctly configured.")

    # Example 2: A hypothetical canceled flight to trigger rebooking
    user_message_text_2 = "My flight AA100 was cancelled. Can you find alternatives?"
    user_message_2 = types.Content(role="user", parts=[types.Part(text=user_message_text_2)])

    print(f"\n--- Conversation 2 (Hypothetical Cancellation) ---")
    print(f"User: {user_message_text_2}")

    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=user_message_2
        ):
            if event.is_final_response():
                print(f"Agent: {event.content.parts[0].text}")
            elif event.is_agent_action():
                print(f"Agent Action: {event.tool_code_log.tool_name}({event.tool_code_log.args})")
            elif event.is_observation():
                print(f"Observation: {event.tool_code_log.result}")

    except Exception as e:
        print(f"\nAn error occurred during agent execution: {e}")
        print("Please ensure your middleware LLM endpoint is running, accessible, and correctly configured.")


if __name__ == "__main__":
    # To run this script:
    # 1. Ensure your .env file is set up correctly.
    # 2. Run 'pip3 install -r requirements.txt'
    # 3. Execute: python3 flight_agent_app.py
    asyncio.run(main())

    # To run with the ADK web UI (for interactive chat):
    # adk web

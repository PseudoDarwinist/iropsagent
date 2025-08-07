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
from flight_agent.tools.wallet_tools import (
    validate_wallet_balance,
    process_payment,
    rollback_payment,
    check_my_wallet,
    get_wallet_balance
)


def get_rebooking_ui_options(user_id: str, flight_options: list, original_booking: dict) -> dict:
    """
    Generate UI options for rebooking interface with wallet payment support
    
    Args:
        user_id: User ID for wallet balance check
        flight_options: List of alternative flight options
        original_booking: Original booking details
    
    Returns:
        Dictionary with UI components and payment options
    """
    
    # Get wallet balance for payment options
    wallet_info = get_wallet_balance(user_id)
    wallet_balance = wallet_info.get('balance', 0.0)
    
    ui_components = {
        'flight_options': [],
        'payment_options': {
            'wallet_available': wallet_balance > 0,
            'wallet_balance': wallet_balance,
            'currency': wallet_info.get('currency', 'USD')
        },
        'original_booking': original_booking
    }
    
    # Process flight options and add payment viability
    for i, option in enumerate(flight_options):
        flight_ui = {
            'option_id': i + 1,
            'flight_details': option,
            'payment_options': {
                'wallet_payment': {
                    'available': False,
                    'sufficient_funds': False,
                    'shortage': 0
                }
            }
        }
        
        # Extract price from flight option (simplified - real implementation would parse actual flight data)
        estimated_price = option.get('price', 0)
        if isinstance(estimated_price, str):
            # Try to extract numeric price from string like "500 USD"
            try:
                estimated_price = float(''.join(filter(lambda x: x.isdigit() or x == '.', estimated_price)))
            except:
                estimated_price = 0
        
        if estimated_price > 0:
            # Check if wallet has sufficient funds
            has_sufficient_funds = wallet_balance >= estimated_price
            shortage = max(0, estimated_price - wallet_balance)
            
            flight_ui['payment_options']['wallet_payment'] = {
                'available': wallet_balance > 0,
                'sufficient_funds': has_sufficient_funds,
                'required_amount': estimated_price,
                'shortage': shortage,
                'can_pay_with_wallet': has_sufficient_funds
            }
        
        ui_components['flight_options'].append(flight_ui)
    
    return ui_components


def create_wallet_payment_button(flight_option: dict, wallet_balance: float) -> dict:
    """
    Create a wallet payment button component
    
    Args:
        flight_option: Flight option details
        wallet_balance: Current wallet balance
    
    Returns:
        Button component configuration
    """
    
    price = flight_option.get('price', 0)
    if isinstance(price, str):
        try:
            price = float(''.join(filter(lambda x: x.isdigit() or x == '.', price)))
        except:
            price = 0
    
    has_sufficient_funds = wallet_balance >= price
    
    button_config = {
        'button_id': f"pay_wallet_{flight_option.get('option_id', 1)}",
        'label': f"Pay with Wallet (${price:.2f})" if has_sufficient_funds else f"Insufficient Funds (Need ${price - wallet_balance:.2f} more)",
        'enabled': has_sufficient_funds,
        'style': 'primary' if has_sufficient_funds else 'disabled',
        'click_action': {
            'type': 'wallet_payment',
            'flight_option': flight_option,
            'amount': price
        },
        'tooltip': f"Current balance: ${wallet_balance:.2f}" if has_sufficient_funds else f"Need ${price - wallet_balance:.2f} more funds"
    }
    
    return button_config


async def handle_wallet_payment_request(user_id: str, flight_option: dict, booking_id: str) -> dict:
    """
    Handle wallet payment request for rebooking
    
    Args:
        user_id: User ID
        flight_option: Selected flight option
        booking_id: New booking ID
    
    Returns:
        Payment processing result
    """
    
    price = flight_option.get('price', 0)
    if isinstance(price, str):
        try:
            price = float(''.join(filter(lambda x: x.isdigit() or x == '.', price)))
        except:
            price = 0
    
    # Validate wallet balance first
    validation = validate_wallet_balance(user_id, price)
    
    if not validation.get('valid', False):
        return {
            'success': False,
            'message': validation.get('message', 'Insufficient wallet balance'),
            'validation_result': validation
        }
    
    # Process payment
    payment_result = process_payment(
        user_id=user_id,
        amount=price,
        booking_id=booking_id,
        flight_details=flight_option,
        payment_metadata={
            'payment_method': 'wallet',
            'flight_option_id': flight_option.get('option_id'),
            'rebooking_request': True
        }
    )
    
    if not payment_result.get('success', False):
        # If payment failed and we have rollback info, attempt rollback
        rollback_info = payment_result.get('rollback_info')
        if rollback_info:
            rollback_result = rollback_payment(rollback_info)
            payment_result['rollback_attempted'] = True
            payment_result['rollback_result'] = rollback_result
    
    return payment_result


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

    # Example 2: A hypothetical canceled flight to trigger rebooking with wallet payment
    user_message_text_2 = "My flight AA100 was cancelled. Can you find alternatives and I want to pay with my wallet if I have enough credits?"
    user_message_2 = types.Content(role="user", parts=[types.Part(text=user_message_text_2)])

    print(f"\n--- Conversation 2 (Cancellation + Wallet Payment Request) ---")
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

    # Example 3: Demonstrate wallet payment functionality
    print(f"\n--- Example 3: Wallet Payment Demo ---")
    
    # Mock flight options for demonstration
    mock_flight_options = [
        {
            'option_id': 1,
            'airline': 'AA',
            'flight_number': 'AA101',
            'price': 250.00,
            'departure_time': '14:30',
            'arrival_time': '17:45'
        },
        {
            'option_id': 2, 
            'airline': 'UA',
            'flight_number': 'UA202',
            'price': 300.00,
            'departure_time': '16:00',
            'arrival_time': '19:15'
        }
    ]
    
    # Generate UI components
    ui_components = get_rebooking_ui_options(USER_ID, mock_flight_options, {'original_flight': 'AA100'})
    print("Generated UI components with wallet payment options:")
    print(f"Wallet balance: ${ui_components['payment_options']['wallet_balance']:.2f}")
    
    for flight_ui in ui_components['flight_options']:
        print(f"\nFlight Option {flight_ui['option_id']}:")
        print(f"  Details: {flight_ui['flight_details']}")
        payment_opt = flight_ui['payment_options']['wallet_payment']
        print(f"  Wallet payment available: {payment_opt['available']}")
        print(f"  Can pay with wallet: {payment_opt.get('can_pay_with_wallet', False)}")
        
        if payment_opt.get('shortage', 0) > 0:
            print(f"  Shortage: ${payment_opt['shortage']:.2f}")


if __name__ == "__main__":
    # To run this script:
    # 1. Ensure your .env file is set up correctly.
    # 2. Run 'pip3 install -r requirements.txt'
    # 3. Execute: python3 flight_agent_app.py
    asyncio.run(main())

    # To run with the ADK web UI (for interactive chat):
    # adk web
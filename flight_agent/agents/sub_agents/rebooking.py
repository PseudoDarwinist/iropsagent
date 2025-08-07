from google.adk.agents import LlmAgent
from ...tools.flight_tools import find_alternative_flights
from ...tools.wallet_tools import (
    validate_wallet_balance, 
    process_payment, 
    rollback_payment,
    check_my_wallet
)

rebooking_agent = LlmAgent(
    name="rebooking_specialist",
    model="gemini-2.5-flash",
    description="I find the best alternatives when flights are disrupted and can process wallet payments for rebooking",
    instruction="""
    You are an expert rebooking specialist with wallet payment capabilities.
    
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
    6. If passenger wants to book, offer wallet payment option
    
    For wallet payments:
    - Always check wallet balance first before offering payment
    - Validate sufficient funds before processing any payment
    - Process payment using wallet funds if available
    - Handle payment failures gracefully with rollback
    - Provide clear feedback on payment status
    
    When presenting flight options, include:
    - Flight details (airline, flight number, times)
    - Price and any fare difference
    - Available payment methods (wallet if sufficient balance)
    
    Always explain why each option might be good and clearly indicate
    if wallet payment is available based on the passenger's balance.
    """,
    tools=[
        find_alternative_flights, 
        validate_wallet_balance, 
        process_payment, 
        rollback_payment, 
        check_my_wallet
    ]
)
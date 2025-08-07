#!/usr/bin/env python3
"""
IROPS Agent - Streamlit Web Application

Main dashboard for flight disruption management with wallet tracking functionality.
Allows frequent travelers to track wallet balance, transaction history, and manage
travel finances through an intuitive web interface.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from flight_agent.models import (
    create_user, get_user_by_email, get_upcoming_bookings,
    User, SessionLocal
)
from flight_agent.ui.wallet_components import (
    display_wallet_balance,
    display_wallet_summary, 
    display_transaction_history,
    display_sidebar_wallet_info,
    display_quick_wallet_actions
)
from flight_agent.tools.wallet_tools import get_wallet_summary
from flight_agent.tools.flight_tools import get_flight_status, check_my_flights
from flight_agent.tools.booking_tools import manual_booking_entry
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


def init_session_state():
    """Initialize session state variables"""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'Dashboard'
    if 'show_wallet_details' not in st.session_state:
        st.session_state.show_wallet_details = False


def user_authentication():
    """Simple user authentication/selection"""
    st.sidebar.markdown("## 👤 User Login")
    
    # For demo purposes, we'll use a simple email-based authentication
    email = st.sidebar.text_input(
        "Enter your email", 
        value=st.session_state.user_email or "",
        placeholder="user@example.com"
    )
    
    if st.sidebar.button("Login/Register"):
        if email:
            # Try to get existing user or create new one
            user = get_user_by_email(email)
            if not user:
                try:
                    user = create_user(email)
                    st.sidebar.success(f"New account created for {email}")
                except Exception as e:
                    st.sidebar.error(f"Error creating user: {str(e)}")
                    return False
            
            st.session_state.user_id = user.user_id
            st.session_state.user_email = user.email
            st.sidebar.success(f"Logged in as {email}")
            st.rerun()
        else:
            st.sidebar.error("Please enter a valid email")
    
    if st.session_state.user_id:
        st.sidebar.success(f"✅ Logged in: {st.session_state.user_email}")
        if st.sidebar.button("Logout"):
            st.session_state.user_id = None
            st.session_state.user_email = None
            st.rerun()
        return True
    
    return False


def sidebar_navigation():
    """Sidebar navigation menu"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🧭 Navigation")
    
    pages = {
        "🏠 Dashboard": "Dashboard",
        "💳 Wallet": "Wallet", 
        "✈️ My Flights": "Flights",
        "📊 Analytics": "Analytics"
    }
    
    for label, page in pages.items():
        if st.sidebar.button(label, use_container_width=True):
            st.session_state.current_page = page
            st.rerun()
    
    # Display current page indicator
    st.sidebar.markdown(f"**Current: {st.session_state.current_page}**")
    
    # Show wallet info in sidebar if user is logged in
    if st.session_state.user_id:
        display_sidebar_wallet_info(st.session_state.user_id)


def dashboard_page():
    """Main dashboard page"""
    st.title("🛫 IROPS Agent Dashboard")
    st.markdown("Welcome to your flight disruption management system")
    
    if not st.session_state.user_id:
        st.info("👈 Please login using the sidebar to access your dashboard")
        return
    
    # Quick stats row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Active Flights", "0", help="Currently monitored flights")
    
    with col2:
        st.metric("Disruptions", "0", help="Recent disruptions detected")
        
    with col3:
        # Get wallet balance for quick display
        try:
            wallet_info = get_wallet_summary(st.session_state.user_id)
            balance = wallet_info['wallet']['balance']
            st.metric("Wallet Balance", f"${balance:.2f}", help="Available travel credits")
        except:
            st.metric("Wallet Balance", "$0.00", help="Available travel credits")
    
    st.markdown("---")
    
    # Wallet summary section
    st.markdown("## 💳 Wallet Overview")
    display_wallet_balance(st.session_state.user_id, show_header=False)
    
    # Quick actions
    display_quick_wallet_actions(st.session_state.user_id)
    
    st.markdown("---")
    
    # Recent activity
    st.markdown("## 📋 Recent Activity")
    
    # Show recent transactions (limited)
    display_transaction_history(
        st.session_state.user_id, 
        page_size=5,
        show_filters=False
    )


def wallet_page():
    """Dedicated wallet management page"""
    st.title("💳 Travel Wallet Management")
    st.markdown("Track your wallet balance and transaction history")
    
    if not st.session_state.user_id:
        st.info("👈 Please login using the sidebar to access your wallet")
        return
    
    # Comprehensive wallet summary
    display_wallet_summary(st.session_state.user_id)
    
    st.markdown("---")
    
    # Full transaction history with all features
    display_transaction_history(
        st.session_state.user_id,
        page_size=20,
        show_filters=True
    )


def flights_page():
    """Flight management page"""
    st.title("✈️ My Flights")
    st.markdown("View and manage your flight bookings")
    
    if not st.session_state.user_id:
        st.info("👈 Please login using the sidebar to access your flights")
        return
    
    # Tabs for different flight views
    tab1, tab2, tab3 = st.tabs(["📅 Upcoming", "➕ Add Flight", "🔍 Check Status"])
    
    with tab1:
        st.markdown("### Upcoming Flights")
        try:
            bookings = get_upcoming_bookings(st.session_state.user_id)
            if bookings:
                # Display bookings in a nice format
                for booking in bookings:
                    with st.expander(f"{booking.flight_number} - {booking.origin} → {booking.destination}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**PNR:** {booking.pnr}")
                            st.write(f"**Airline:** {booking.airline}")
                            st.write(f"**Class:** {booking.booking_class}")
                        with col2:
                            st.write(f"**Departure:** {booking.departure_date.strftime('%Y-%m-%d %H:%M')}")
                            st.write(f"**Status:** {booking.status}")
            else:
                st.info("No upcoming flights found. Add a flight to get started!")
        except Exception as e:
            st.error(f"Error loading flights: {str(e)}")
    
    with tab2:
        st.markdown("### Add New Flight")
        with st.form("add_flight_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                pnr = st.text_input("Confirmation/PNR", placeholder="ABC123")
                airline = st.text_input("Airline", placeholder="American Airlines")
                flight_number = st.text_input("Flight Number", placeholder="AA1234")
                
            with col2:
                departure_date = st.datetime_input("Departure Date/Time")
                origin = st.text_input("Origin Airport", placeholder="JFK")
                destination = st.text_input("Destination Airport", placeholder="LAX")
            
            booking_class = st.selectbox("Class", ["Economy", "Business", "First"])
            
            if st.form_submit_button("Add Flight"):
                if all([pnr, airline, flight_number, origin, destination]):
                    try:
                        booking_data = {
                            'pnr': pnr,
                            'airline': airline,
                            'flight_number': flight_number,
                            'departure_date': departure_date,
                            'origin': origin.upper(),
                            'destination': destination.upper(),
                            'class': booking_class
                        }
                        
                        booking = manual_booking_entry(st.session_state.user_id, booking_data)
                        if booking:
                            st.success(f"✅ Flight {flight_number} added successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to add flight")
                    except Exception as e:
                        st.error(f"Error adding flight: {str(e)}")
                else:
                    st.error("Please fill in all required fields")
    
    with tab3:
        st.markdown("### Check Flight Status")
        flight_id = st.text_input("Flight Number or ID", placeholder="AA1234")
        
        if st.button("Check Status"):
            if flight_id:
                try:
                    with st.spinner("Checking flight status..."):
                        status = get_flight_status(flight_id)
                    if status:
                        st.json(status)
                    else:
                        st.warning("Flight not found or status unavailable")
                except Exception as e:
                    st.error(f"Error checking flight status: {str(e)}")
            else:
                st.error("Please enter a flight number")

    # Example 2: A hypothetical canceled flight to trigger rebooking with wallet payment
    user_message_text_2 = "My flight AA100 was cancelled. Can you find alternatives and I want to pay with my wallet if I have enough credits?"
    user_message_2 = types.Content(role="user", parts=[types.Part(text=user_message_text_2)])

    print(f"\n--- Conversation 2 (Cancellation + Wallet Payment Request) ---")
    print(f"User: {user_message_text_2}")


def analytics_page():
    """Analytics and insights page"""
    st.title("📊 Travel Analytics")
    st.markdown("Insights into your travel patterns and wallet usage")
    
    if not st.session_state.user_id:
        st.info("👈 Please login using the sidebar to access analytics")
        return
    
    # Placeholder for analytics features
    st.info("🚧 Analytics features coming soon!")
    
    # Show some basic wallet analytics
    try:
        summary = get_wallet_summary(st.session_state.user_id)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 💰 Financial Overview")
            st.write(f"**Total Compensation Received:** ${summary['summary']['total_compensation_received']:.2f}")
            st.write(f"**Total Amount Spent:** ${summary['summary']['total_amount_spent']:.2f}")
            st.write(f"**Net Balance:** ${summary['wallet']['balance']:.2f}")
        
        with col2:
            st.markdown("### 📈 Transaction Trends")
            st.info("Transaction trend charts would be displayed here")
            
    except Exception as e:
        st.error(f"Error loading analytics: {str(e)}")


def main():
    """Main application function"""
    # Page configuration
    st.set_page_config(
        page_title="IROPS Agent - Travel Wallet",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    init_session_state()
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main .block-container {
        padding-top: 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # User authentication
    is_authenticated = user_authentication()
    
    # Sidebar navigation
    sidebar_navigation()
    
    # Main content based on current page
    if st.session_state.current_page == "Dashboard":
        dashboard_page()
    elif st.session_state.current_page == "Wallet":
        wallet_page()
    elif st.session_state.current_page == "Flights":
        flights_page()
    elif st.session_state.current_page == "Analytics":
        analytics_page()
    else:
        dashboard_page()  # Default to dashboard
    
    # Footer
    st.markdown("---")
    st.markdown("*IROPS Agent - Intelligent Travel Disruption Management*")

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
    main()

    # To run this script:
    # 1. Ensure your .env file is set up correctly.
    # 2. Run 'pip3 install -r requirements.txt'
    # 3. Execute: python3 flight_agent_app.py
    asyncio.run(main())

    # To run with the ADK web UI (for interactive chat):
    # adk web

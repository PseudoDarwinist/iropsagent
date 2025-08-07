# flight_agent/ui/wallet_components.py
"""
Streamlit UI Components for Wallet Functionality

This module provides reusable Streamlit components for displaying and managing 
wallet information, transaction history, and related financial data for travelers.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from ..tools.wallet_tools import (
    get_wallet_summary, 
    get_wallet_balance, 
    get_wallet_transactions
)


def display_wallet_balance(user_id: str, show_header: bool = True) -> Dict:
    """
    Display wallet balance in a clean, prominent widget
    
    Args:
        user_id: User ID to fetch wallet data for
        show_header: Whether to show the section header
        
    Returns:
        Dictionary with wallet information
    """
    try:
        wallet_info = get_wallet_balance(user_id)
        
        if show_header:
            st.subheader("💳 Wallet Balance")
        
        # Create columns for better layout
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # Main balance display with larger text
            st.markdown(f"### ${wallet_info['balance']:.2f} USD")
            st.caption("Available Balance")
        
        with col2:
            # Status indicator
            if wallet_info['balance'] > 0:
                st.success("💰 Credits Available")
            else:
                st.info("💸 No Credits")
        
        with col3:
            # Last updated info
            updated_at = datetime.fromisoformat(wallet_info['updated_at'])
            st.caption(f"Updated: {updated_at.strftime('%m/%d/%Y')}")
        
        return wallet_info
        
    except Exception as e:
        st.error(f"Error loading wallet balance: {str(e)}")
        return {}


def display_wallet_summary(user_id: str) -> Dict:
    """
    Display comprehensive wallet summary with key statistics
    
    Args:
        user_id: User ID to fetch wallet data for
        
    Returns:
        Dictionary with wallet summary data
    """
    try:
        summary = get_wallet_summary(user_id)
        
        st.subheader("📊 Wallet Overview")
        
        # Key metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Current Balance",
                value=f"${summary['wallet']['balance']:.2f}",
                delta=None
            )
        
        with col2:
            st.metric(
                label="Total Received",
                value=f"${summary['summary']['total_compensation_received']:.2f}",
                delta=None
            )
        
        with col3:
            st.metric(
                label="Total Spent", 
                value=f"${summary['summary']['total_amount_spent']:.2f}",
                delta=None
            )
            
        with col4:
            st.metric(
                label="Transactions",
                value=summary['summary']['transaction_count'],
                delta=None
            )
        
        # Status message
        if summary['summary']['has_pending_credits']:
            st.success("✅ You have credits available for booking alternative flights!")
        else:
            st.info("💡 Compensation credits will appear here automatically when flight disruptions occur.")
            
        return summary
        
    except Exception as e:
        st.error(f"Error loading wallet summary: {str(e)}")
        return {}


def display_transaction_history(
    user_id: str, 
    page_size: int = 10,
    show_filters: bool = True
) -> pd.DataFrame:
    """
    Display transaction history with pagination and filtering
    
    Args:
        user_id: User ID to fetch transactions for
        page_size: Number of transactions per page
        show_filters: Whether to show filtering options
        
    Returns:
        DataFrame with filtered transactions
    """
    try:
        st.subheader("📋 Transaction History")
        
        # Initialize session state for pagination
        if 'transaction_page' not in st.session_state:
            st.session_state.transaction_page = 0
        
        # Filtering options
        transaction_type_filter = None
        date_filter = None
        
        if show_filters:
            filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1])
            
            with filter_col1:
                transaction_types = ['All', 'COMPENSATION', 'PURCHASE', 'REFUND']
                selected_type = st.selectbox(
                    "Filter by Type", 
                    transaction_types,
                    key="txn_type_filter"
                )
                if selected_type != 'All':
                    transaction_type_filter = selected_type
            
            with filter_col2:
                date_options = ['All Time', 'Last 30 Days', 'Last 90 Days', 'Last Year']
                selected_date = st.selectbox(
                    "Filter by Date",
                    date_options,
                    key="txn_date_filter"
                )
                
                if selected_date != 'All Time':
                    if selected_date == 'Last 30 Days':
                        date_filter = datetime.now() - timedelta(days=30)
                    elif selected_date == 'Last 90 Days':
                        date_filter = datetime.now() - timedelta(days=90)
                    elif selected_date == 'Last Year':
                        date_filter = datetime.now() - timedelta(days=365)
            
            with filter_col3:
                # Search functionality
                search_term = st.text_input(
                    "Search Descriptions",
                    placeholder="Enter search term...",
                    key="txn_search"
                )
        
        # Get transactions with a higher limit for client-side filtering
        all_transactions = get_wallet_transactions(
            user_id, 
            transaction_type=transaction_type_filter,
            limit=1000
        )
        
        if not all_transactions:
            st.info("No transactions found.")
            return pd.DataFrame()
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(all_transactions)
        df['created_at'] = pd.to_datetime(df['created_at'])
        
        # Apply date filter
        if date_filter:
            df = df[df['created_at'] >= date_filter]
        
        # Apply search filter
        if show_filters and search_term:
            df = df[df['description'].str.contains(search_term, case=False, na=False)]
        
        # Sort by date (newest first)
        df = df.sort_values('created_at', ascending=False)
        
        if df.empty:
            st.info("No transactions match the current filters.")
            return df
        
        # Pagination
        total_records = len(df)
        total_pages = (total_records - 1) // page_size + 1
        
        # Pagination controls
        if total_pages > 1:
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                if st.button("← Previous", disabled=(st.session_state.transaction_page <= 0)):
                    st.session_state.transaction_page -= 1
                    st.rerun()
            
            with col2:
                st.write(f"Page {st.session_state.transaction_page + 1} of {total_pages}")
                st.write(f"Showing {total_records} transactions")
            
            with col3:
                if st.button("Next →", disabled=(st.session_state.transaction_page >= total_pages - 1)):
                    st.session_state.transaction_page += 1
                    st.rerun()
        
        # Get current page data
        start_idx = st.session_state.transaction_page * page_size
        end_idx = start_idx + page_size
        page_df = df.iloc[start_idx:end_idx].copy()
        
        # Format data for display
        display_df = page_df.copy()
        display_df['Amount'] = display_df['amount'].apply(
            lambda x: f"${x:+.2f}" if x != 0 else "$0.00"
        )
        display_df['Date'] = display_df['created_at'].dt.strftime('%Y-%m-%d %H:%M')
        display_df['Type'] = display_df['transaction_type']
        display_df['Description'] = display_df['description']
        
        # Display the table
        st.dataframe(
            display_df[['Date', 'Type', 'Amount', 'Description']],
            use_container_width=True,
            hide_index=True,
            column_config={
                'Date': st.column_config.TextColumn('Date', width='medium'),
                'Type': st.column_config.TextColumn('Type', width='small'),
                'Amount': st.column_config.TextColumn('Amount', width='small'),
                'Description': st.column_config.TextColumn('Description', width='large'),
            }
        )
        
        return df
        
    except Exception as e:
        st.error(f"Error loading transaction history: {str(e)}")
        return pd.DataFrame()


def display_sidebar_wallet_info(user_id: str) -> None:
    """
    Display wallet balance in the sidebar navigation
    
    Args:
        user_id: User ID to fetch wallet data for
    """
    try:
        wallet_info = get_wallet_balance(user_id)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 💳 Wallet")
        
        balance = wallet_info['balance']
        if balance > 0:
            st.sidebar.success(f"**${balance:.2f} USD**")
            st.sidebar.caption("Available for bookings")
        else:
            st.sidebar.info("**$0.00 USD**")
            st.sidebar.caption("No credits available")
        
        # Quick action button
        if st.sidebar.button("View Wallet Details", use_container_width=True):
            # This would typically navigate to wallet page
            # For now, we'll use session state to trigger display
            st.session_state.show_wallet_details = True
        
    except Exception as e:
        st.sidebar.error("Error loading wallet")


def display_quick_wallet_actions(user_id: str) -> None:
    """
    Display quick wallet actions and information
    
    Args:
        user_id: User ID for wallet operations
    """
    st.subheader("⚡ Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Refresh Balance", use_container_width=True):
            st.rerun()
    
    with col2:
        if st.button("View All Transactions", use_container_width=True):
            st.session_state.show_all_transactions = True
    
    with col3:
        if st.button("Download History", use_container_width=True):
            # This would typically trigger a download
            st.info("Download feature would be implemented here")


def create_transaction_filter_component() -> Tuple[Optional[str], Optional[datetime], Optional[str]]:
    """
    Create a reusable transaction filter component
    
    Returns:
        Tuple of (transaction_type, date_filter, search_term)
    """
    st.markdown("### 🔍 Filter Transactions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        transaction_type = st.selectbox(
            "Transaction Type",
            ["All", "COMPENSATION", "PURCHASE", "REFUND", "TRANSFER"],
            help="Filter transactions by type"
        )
        transaction_type = None if transaction_type == "All" else transaction_type
    
    with col2:
        date_range = st.selectbox(
            "Date Range", 
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Last Year"]
        )
        
        date_filter = None
        if date_range != "All Time":
            days_map = {
                "Last 7 Days": 7,
                "Last 30 Days": 30, 
                "Last 90 Days": 90,
                "Last Year": 365
            }
            date_filter = datetime.now() - timedelta(days=days_map[date_range])
    
    search_term = st.text_input(
        "Search in descriptions",
        placeholder="Enter keywords to search...",
        help="Search transaction descriptions"
    )
    search_term = search_term.strip() if search_term else None
    
    return transaction_type, date_filter, search_term


def format_currency(amount: float) -> str:
    """
    Format currency amount with appropriate color coding
    
    Args:
        amount: Amount to format
        
    Returns:
        Formatted currency string
    """
    if amount > 0:
        return f"+ ${amount:.2f}"
    elif amount < 0:
        return f"- ${abs(amount):.2f}"
    else:
        return "$0.00"


def get_transaction_type_icon(transaction_type: str) -> str:
    """
    Get emoji icon for transaction type
    
    Args:
        transaction_type: Type of transaction
        
    Returns:
        Emoji icon
    """
    icons = {
        'COMPENSATION': '💰',
        'PURCHASE': '🛒',
        'REFUND': '↩️',
        'TRANSFER': '🔄',
        'ADJUSTMENT': '⚖️'
    }
    return icons.get(transaction_type, '💳')
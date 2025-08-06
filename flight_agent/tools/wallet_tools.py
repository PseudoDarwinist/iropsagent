# flight_agent/tools/wallet_tools.py
"""
Wallet Tools for Managing Passenger Compensation Credits

This module provides functionality to manage passenger wallets, process compensation
credits, and handle wallet transactions for flight disruptions.
"""

from datetime import datetime
from typing import Dict, Optional, List
from uuid import uuid4

from ..models import (
    SessionLocal, Wallet, WalletTransaction, User, Booking, 
    DisruptionEvent, get_or_create_wallet
)
from .compensation_engine import calculate_compensation, get_compensation_summary


def process_compensation(
    user_id: str,
    booking_id: str,
    disruption_event_id: str,
    disruption_data: Dict
) -> Dict:
    """
    Process automatic compensation for a flight disruption
    
    Args:
        user_id: User ID for the affected passenger
        booking_id: Booking ID for the disrupted flight
        disruption_event_id: Disruption event ID
        disruption_data: Dictionary containing disruption details
    
    Returns:
        Dictionary containing compensation processing results
    """
    
    db = SessionLocal()
    try:
        # Get or create wallet for the user
        wallet = get_or_create_wallet(user_id)
        
        # Calculate compensation amount
        compensation_result = calculate_compensation(**disruption_data)
        
        if not compensation_result['eligible'] or compensation_result['amount'] <= 0:
            return {
                'success': False,
                'message': 'No compensation eligible for this disruption',
                'compensation_result': compensation_result,
                'wallet_balance': wallet.balance
            }
        
        # Create wallet transaction
        transaction = create_wallet_transaction(
            wallet_id=wallet.wallet_id,
            amount=compensation_result['amount'],
            transaction_type='COMPENSATION',
            description=f"Automatic compensation for {disruption_data.get('disruption_type', 'disruption')}",
            reference_id=disruption_event_id,
            transaction_metadata={
                'booking_id': booking_id,
                'disruption_event_id': disruption_event_id,
                'compensation_rule': compensation_result['rule_applied'],
                'disruption_type': disruption_data.get('disruption_type'),
                'automatic_processing': True
            }
        )
        
        if transaction:
            # Update wallet balance
            wallet = db.query(Wallet).filter(Wallet.wallet_id == wallet.wallet_id).first()
            new_balance = wallet.balance + compensation_result['amount']
            wallet.balance = new_balance
            wallet.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                'success': True,
                'message': f"Compensation of ${compensation_result['amount']:.2f} credited successfully",
                'transaction_id': transaction.transaction_id,
                'amount_credited': compensation_result['amount'],
                'new_wallet_balance': new_balance,
                'compensation_result': compensation_result
            }
        else:
            return {
                'success': False,
                'message': 'Failed to create wallet transaction',
                'compensation_result': compensation_result
            }
    
    except Exception as e:
        db.rollback()
        return {
            'success': False,
            'message': f'Error processing compensation: {str(e)}',
            'error': str(e)
        }
    finally:
        db.close()


def create_wallet_transaction(
    wallet_id: str,
    amount: float,
    transaction_type: str,
    description: str = None,
    reference_id: str = None,
    transaction_metadata: Dict = None
) -> Optional[WalletTransaction]:
    """
    Create a new wallet transaction
    
    Args:
        wallet_id: Wallet ID
        amount: Transaction amount (positive for credits, negative for debits)
        transaction_type: Type of transaction (COMPENSATION, PURCHASE, REFUND, etc.)
        description: Transaction description
        reference_id: Reference to related entity (booking, disruption, etc.)
        transaction_metadata: Additional transaction metadata
    
    Returns:
        WalletTransaction object if successful, None otherwise
    """
    
    db = SessionLocal()
    try:
        transaction = WalletTransaction(
            transaction_id=f"txn_{uuid4().hex[:12]}_{int(datetime.now().timestamp())}",
            wallet_id=wallet_id,
            amount=amount,
            transaction_type=transaction_type,
            description=description or f"{transaction_type.title()} transaction",
            reference_id=reference_id,
            transaction_metadata=transaction_metadata or {}
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        return transaction
    
    except Exception as e:
        db.rollback()
        print(f"Error creating wallet transaction: {e}")
        return None
    finally:
        db.close()


def get_wallet_balance(user_id: str) -> Dict:
    """
    Get wallet balance for a user
    
    Args:
        user_id: User ID
    
    Returns:
        Dictionary containing wallet information
    """
    
    wallet = get_or_create_wallet(user_id)
    
    return {
        'wallet_id': wallet.wallet_id,
        'balance': wallet.balance,
        'currency': wallet.currency,
        'created_at': wallet.created_at.isoformat(),
        'updated_at': wallet.updated_at.isoformat()
    }


def get_wallet_transactions(
    user_id: str,
    transaction_type: str = None,
    limit: int = 50
) -> List[Dict]:
    """
    Get wallet transaction history for a user
    
    Args:
        user_id: User ID
        transaction_type: Filter by transaction type (optional)
        limit: Maximum number of transactions to return
    
    Returns:
        List of transaction dictionaries
    """
    
    db = SessionLocal()
    try:
        wallet = get_or_create_wallet(user_id)
        
        query = db.query(WalletTransaction).filter(
            WalletTransaction.wallet_id == wallet.wallet_id
        )
        
        if transaction_type:
            query = query.filter(WalletTransaction.transaction_type == transaction_type)
        
        transactions = query.order_by(
            WalletTransaction.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                'transaction_id': txn.transaction_id,
                'amount': txn.amount,
                'transaction_type': txn.transaction_type,
                'description': txn.description,
                'reference_id': txn.reference_id,
                'created_at': txn.created_at.isoformat(),
                'metadata': txn.transaction_metadata
            }
            for txn in transactions
        ]
    
    finally:
        db.close()


def use_wallet_credits(
    user_id: str,
    amount: float,
    purpose: str,
    reference_id: str = None
) -> Dict:
    """
    Use wallet credits for a purchase or booking
    
    Args:
        user_id: User ID
        amount: Amount to debit from wallet
        purpose: Purpose of the transaction
        reference_id: Reference ID for the transaction
    
    Returns:
        Dictionary containing transaction results
    """
    
    db = SessionLocal()
    try:
        wallet = get_or_create_wallet(user_id)
        
        if wallet.balance < amount:
            return {
                'success': False,
                'message': f'Insufficient wallet balance. Available: ${wallet.balance:.2f}, Required: ${amount:.2f}',
                'current_balance': wallet.balance
            }
        
        # Create debit transaction
        transaction = create_wallet_transaction(
            wallet_id=wallet.wallet_id,
            amount=-amount,  # Negative for debit
            transaction_type='PURCHASE',
            description=f"Used credits for {purpose}",
            reference_id=reference_id,
            transaction_metadata={'purpose': purpose}
        )
        
        if transaction:
            # Update wallet balance
            wallet = db.query(Wallet).filter(Wallet.wallet_id == wallet.wallet_id).first()
            new_balance = wallet.balance - amount
            wallet.balance = new_balance
            wallet.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                'success': True,
                'message': f"${amount:.2f} debited successfully",
                'transaction_id': transaction.transaction_id,
                'amount_debited': amount,
                'new_wallet_balance': new_balance
            }
        else:
            return {
                'success': False,
                'message': 'Failed to create wallet transaction'
            }
    
    except Exception as e:
        db.rollback()
        return {
            'success': False,
            'message': f'Error processing wallet transaction: {str(e)}',
            'error': str(e)
        }
    finally:
        db.close()


def process_payment(
    user_id: str,
    amount: float,
    booking_id: str,
    flight_details: Dict,
    payment_metadata: Dict = None
) -> Dict:
    """
    Process payment for rebooking using wallet funds with rollback capability
    
    Args:
        user_id: User ID for the passenger
        amount: Payment amount required
        booking_id: New booking ID for reference
        flight_details: Details of the new flight booking
        payment_metadata: Additional payment metadata
    
    Returns:
        Dictionary containing payment processing results with rollback info
    """
    
    db = SessionLocal()
    transaction_id = None
    rollback_info = None
    
    try:
        # Get wallet and validate balance
        wallet = get_or_create_wallet(user_id)
        
        if wallet.balance < amount:
            return {
                'success': False,
                'message': f'Insufficient wallet balance. Available: ${wallet.balance:.2f}, Required: ${amount:.2f}',
                'current_balance': wallet.balance,
                'insufficient_funds': True
            }
        
        # Store original balance for rollback
        original_balance = wallet.balance
        rollback_info = {
            'original_balance': original_balance,
            'wallet_id': wallet.wallet_id
        }
        
        # Create debit transaction for rebooking
        transaction = create_wallet_transaction(
            wallet_id=wallet.wallet_id,
            amount=-amount,  # Negative for debit
            transaction_type='REBOOKING_PAYMENT',
            description=f"Payment for flight rebooking to {flight_details.get('destination', 'unknown destination')}",
            reference_id=booking_id,
            transaction_metadata={
                'booking_id': booking_id,
                'flight_details': flight_details,
                'payment_metadata': payment_metadata or {},
                'original_balance': original_balance,
                'rebooking_payment': True
            }
        )
        
        if not transaction:
            return {
                'success': False,
                'message': 'Failed to create payment transaction',
                'rollback_info': rollback_info
            }
        
        transaction_id = transaction.transaction_id
        
        # Update wallet balance
        wallet = db.query(Wallet).filter(Wallet.wallet_id == wallet.wallet_id).first()
        new_balance = wallet.balance - amount
        wallet.balance = new_balance
        wallet.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            'success': True,
            'message': f"Payment of ${amount:.2f} processed successfully for rebooking",
            'transaction_id': transaction_id,
            'amount_paid': amount,
            'new_wallet_balance': new_balance,
            'rollback_info': {
                'transaction_id': transaction_id,
                'original_balance': original_balance,
                'wallet_id': wallet.wallet_id
            }
        }
    
    except Exception as e:
        db.rollback()
        return {
            'success': False,
            'message': f'Error processing payment: {str(e)}',
            'error': str(e),
            'rollback_info': rollback_info,
            'transaction_id': transaction_id
        }
    finally:
        db.close()


def rollback_payment(rollback_info: Dict) -> Dict:
    """
    Rollback a failed payment transaction
    
    Args:
        rollback_info: Rollback information from process_payment()
    
    Returns:
        Dictionary containing rollback results
    """
    
    if not rollback_info:
        return {
            'success': False,
            'message': 'No rollback information provided'
        }
    
    db = SessionLocal()
    try:
        wallet_id = rollback_info.get('wallet_id')
        transaction_id = rollback_info.get('transaction_id')
        original_balance = rollback_info.get('original_balance')
        
        if not wallet_id or original_balance is None:
            return {
                'success': False,
                'message': 'Insufficient rollback information'
            }
        
        # Restore original wallet balance
        wallet = db.query(Wallet).filter(Wallet.wallet_id == wallet_id).first()
        if wallet:
            wallet.balance = original_balance
            wallet.updated_at = datetime.utcnow()
            
            # Create rollback transaction if we have transaction_id
            if transaction_id:
                rollback_transaction = create_wallet_transaction(
                    wallet_id=wallet_id,
                    amount=0,  # No amount change, just for record keeping
                    transaction_type='ROLLBACK',
                    description=f"Rollback for failed rebooking payment {transaction_id}",
                    reference_id=transaction_id,
                    transaction_metadata={
                        'rollback_for': transaction_id,
                        'restored_balance': original_balance,
                        'rollback_reason': 'rebooking_failed'
                    }
                )
            
            db.commit()
            
            return {
                'success': True,
                'message': f"Payment rolled back successfully. Wallet balance restored to ${original_balance:.2f}",
                'restored_balance': original_balance
            }
        else:
            return {
                'success': False,
                'message': 'Wallet not found for rollback'
            }
    
    except Exception as e:
        db.rollback()
        return {
            'success': False,
            'message': f'Error during rollback: {str(e)}',
            'error': str(e)
        }
    finally:
        db.close()


def validate_wallet_balance(user_id: str, required_amount: float) -> Dict:
    """
    Validate if wallet has sufficient balance for a transaction
    
    Args:
        user_id: User ID
        required_amount: Amount required for transaction
    
    Returns:
        Dictionary containing validation results
    """
    
    try:
        wallet = get_or_create_wallet(user_id)
        
        has_sufficient_balance = wallet.balance >= required_amount
        shortage = max(0, required_amount - wallet.balance)
        
        return {
            'valid': has_sufficient_balance,
            'current_balance': wallet.balance,
            'required_amount': required_amount,
            'shortage': shortage,
            'message': 'Sufficient balance available' if has_sufficient_balance 
                      else f'Insufficient balance. Need ${shortage:.2f} more.'
        }
    
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'message': f'Error validating wallet balance: {str(e)}'
        }


def get_wallet_summary(user_id: str) -> Dict:
    """
    Get comprehensive wallet summary for a user
    
    Args:
        user_id: User ID
    
    Returns:
        Dictionary containing wallet summary
    """
    
    # Get wallet balance
    wallet_info = get_wallet_balance(user_id)
    
    # Get recent transactions
    recent_transactions = get_wallet_transactions(user_id, limit=10)
    
    # Calculate totals by transaction type
    compensation_total = sum(
        txn['amount'] for txn in recent_transactions 
        if txn['transaction_type'] == 'COMPENSATION' and txn['amount'] > 0
    )
    
    purchases_total = sum(
        abs(txn['amount']) for txn in recent_transactions 
        if txn['transaction_type'] == 'PURCHASE' and txn['amount'] < 0
    )
    
    return {
        'wallet': wallet_info,
        'recent_transactions': recent_transactions,
        'summary': {
            'total_compensation_received': compensation_total,
            'total_amount_spent': purchases_total,
            'transaction_count': len(recent_transactions),
            'has_pending_credits': wallet_info['balance'] > 0
        }
    }


def check_my_wallet(user_id: str) -> str:
    """
    Get wallet information for display in agent conversations
    
    Args:
        user_id: User ID
    
    Returns:
        Formatted string with wallet information
    """
    
    try:
        summary = get_wallet_summary(user_id)
        wallet = summary['wallet']
        transactions = summary['recent_transactions']
        stats = summary['summary']
        
        result = f"💳 **Wallet Summary**\n\n"
        result += f"**Current Balance:** ${wallet['balance']:.2f} USD\n\n"
        
        if stats['total_compensation_received'] > 0:
            result += f"**Total Compensation Received:** ${stats['total_compensation_received']:.2f}\n"
        
        if stats['total_amount_spent'] > 0:
            result += f"**Total Amount Used:** ${stats['total_amount_spent']:.2f}\n"
        
        result += f"**Total Transactions:** {stats['transaction_count']}\n\n"
        
        if transactions:
            result += "**Recent Transactions:**\n"
            for txn in transactions[:5]:  # Show only last 5
                amount_str = f"${txn['amount']:.2f}" if txn['amount'] > 0 else f"-${abs(txn['amount']):.2f}"
                date_str = datetime.fromisoformat(txn['created_at']).strftime('%Y-%m-%d')
                result += f"• {date_str}: {amount_str} - {txn['description']}\n"
        else:
            result += "No recent transactions found.\n"
        
        if wallet['balance'] > 0:
            result += f"\n✅ You have ${wallet['balance']:.2f} available for booking alternative flights!"
        
        return result
    
    except Exception as e:
        return f"Error retrieving wallet information: {str(e)}"


def notify_compensation_processed(user_id: str, compensation_data: Dict) -> str:
    """
    Generate notification message for processed compensation
    
    Args:
        user_id: User ID
        compensation_data: Compensation processing results
    
    Returns:
        Formatted notification message
    """
    
    if not compensation_data.get('success'):
        return f"❌ Compensation processing failed: {compensation_data.get('message', 'Unknown error')}"
    
    amount = compensation_data.get('amount_credited', 0)
    balance = compensation_data.get('new_wallet_balance', 0)
    
    message = f"✅ **Automatic Compensation Processed**\n\n"
    message += f"💰 **Amount Credited:** ${amount:.2f}\n"
    message += f"💳 **New Wallet Balance:** ${balance:.2f}\n\n"
    message += f"🎫 These credits can be used immediately to book alternative flights.\n"
    message += f"📱 Use the 'check my wallet' command to view your transaction history."
    
    return message
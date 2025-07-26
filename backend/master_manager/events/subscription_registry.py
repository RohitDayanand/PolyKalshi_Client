"""
Subscription Registry - Centralized state management for market subscriptions

Maintains the authoritative state of all client subscriptions and provides
atomic updates for add/remove operations with transaction logging.
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ClientSubscription:
    """Individual client subscription details"""
    client_id: str
    token_ids: Set[str]
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubscriptionTransaction:
    """Transaction record for subscription changes"""
    transaction_id: str
    client_id: str
    operation_type: str  # 'add', 'remove', 'replace'
    token_ids: List[str]
    previous_state: Set[str]
    new_state: Set[str]
    timestamp: float = field(default_factory=time.time)
    status: str = "pending"  # pending, committed, rolled_back
    metadata: Dict[str, Any] = field(default_factory=dict)


class SubscriptionRegistry:
    """
    Centralized registry for managing client subscriptions with atomic operations.
    
    Features:
    - Atomic add/remove/replace operations
    - Transaction logging for rollback
    - Subscription state queries
    - Conflict detection
    - Audit trail
    """
    
    def __init__(self):
        self.subscriptions: Dict[str, ClientSubscription] = {}
        self.transactions: Dict[str, SubscriptionTransaction] = {}
        self.transaction_history: List[SubscriptionTransaction] = []
        self._lock = asyncio.Lock()
        self._max_history = 1000
    
    async def get_client_subscription(self, client_id: str) -> Optional[ClientSubscription]:
        """Get current subscription for a client"""
        async with self._lock:
            return self.subscriptions.get(client_id)
    
    async def get_client_token_ids(self, client_id: str) -> Set[str]:
        """Get token IDs for a client"""
        async with self._lock:
            subscription = self.subscriptions.get(client_id)
            return subscription.token_ids.copy() if subscription else set()
    
    async def get_all_subscriptions(self) -> Dict[str, Set[str]]:
        """Get all client subscriptions"""
        async with self._lock:
            return {
                client_id: sub.token_ids.copy()
                for client_id, sub in self.subscriptions.items()
            }
    
    async def get_token_subscribers(self, token_id: str) -> Set[str]:
        """Get all clients subscribed to a specific token"""
        async with self._lock:
            subscribers = set()
            for client_id, subscription in self.subscriptions.items():
                if token_id in subscription.token_ids:
                    subscribers.add(client_id)
            return subscribers
    
    async def prepare_add_tokens(self, client_id: str, token_ids: List[str],
                                transaction_id: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Prepare to add tokens to a client's subscription (Phase 1 of 2PC).
        
        Returns:
            (success, transaction_id, metadata)
        """
        if transaction_id is None:
            transaction_id = str(uuid4())
        
        async with self._lock:
            try:
                # Get current state
                current_subscription = self.subscriptions.get(client_id)
                current_tokens = current_subscription.token_ids.copy() if current_subscription else set()
                
                # Calculate new state
                new_tokens = current_tokens.union(set(token_ids))
                
                # Create transaction record
                transaction = SubscriptionTransaction(
                    transaction_id=transaction_id,
                    client_id=client_id,
                    operation_type="add",
                    token_ids=token_ids,
                    previous_state=current_tokens,
                    new_state=new_tokens,
                    status="prepared"
                )
                
                self.transactions[transaction_id] = transaction
                
                logger.debug(f"Prepared add operation {transaction_id} for client {client_id}: {token_ids}")
                
                return True, transaction_id, {
                    "previous_count": len(current_tokens),
                    "new_count": len(new_tokens),
                    "added_tokens": list(set(token_ids) - current_tokens)
                }
                
            except Exception as e:
                logger.error(f"Failed to prepare add tokens for {client_id}: {e}")
                return False, transaction_id, {"error": str(e)}
    
    async def commit_add_tokens(self, transaction_id: str) -> bool:
        """
        Commit the add tokens operation (Phase 2 of 2PC).
        
        Returns:
            bool: Success status
        """
        async with self._lock:
            try:
                if transaction_id not in self.transactions:
                    logger.error(f"Transaction {transaction_id} not found for commit")
                    return False
                
                transaction = self.transactions[transaction_id]
                
                if transaction.status != "prepared":
                    logger.error(f"Transaction {transaction_id} not in prepared state: {transaction.status}")
                    return False
                
                # Apply the change
                if transaction.client_id not in self.subscriptions:
                    self.subscriptions[transaction.client_id] = ClientSubscription(
                        client_id=transaction.client_id,
                        token_ids=set()
                    )
                
                subscription = self.subscriptions[transaction.client_id]
                subscription.token_ids = transaction.new_state.copy()
                subscription.updated_at = time.time()
                
                # Update transaction status
                transaction.status = "committed"
                
                # Move to history
                self._archive_transaction(transaction)
                
                logger.info(f"Committed add operation {transaction_id} for client {transaction.client_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to commit add tokens transaction {transaction_id}: {e}")
                return False
    
    async def prepare_remove_tokens(self, client_id: str, token_ids: List[str],
                                   transaction_id: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Prepare to remove tokens from a client's subscription (Phase 1 of 2PC).
        
        Returns:
            (success, transaction_id, metadata)
        """
        if transaction_id is None:
            transaction_id = str(uuid4())
        
        async with self._lock:
            try:
                # Get current state
                current_subscription = self.subscriptions.get(client_id)
                if not current_subscription:
                    return False, transaction_id, {"error": "Client not found"}
                
                current_tokens = current_subscription.token_ids.copy()
                
                # Calculate new state
                new_tokens = current_tokens - set(token_ids)
                
                # Create transaction record
                transaction = SubscriptionTransaction(
                    transaction_id=transaction_id,
                    client_id=client_id,
                    operation_type="remove",
                    token_ids=token_ids,
                    previous_state=current_tokens,
                    new_state=new_tokens,
                    status="prepared"
                )
                
                self.transactions[transaction_id] = transaction
                
                logger.debug(f"Prepared remove operation {transaction_id} for client {client_id}: {token_ids}")
                
                return True, transaction_id, {
                    "previous_count": len(current_tokens),
                    "new_count": len(new_tokens),
                    "removed_tokens": list(set(token_ids) & current_tokens),
                    "not_found_tokens": list(set(token_ids) - current_tokens)
                }
                
            except Exception as e:
                logger.error(f"Failed to prepare remove tokens for {client_id}: {e}")
                return False, transaction_id, {"error": str(e)}
    
    async def commit_remove_tokens(self, transaction_id: str) -> bool:
        """
        Commit the remove tokens operation (Phase 2 of 2PC).
        
        Returns:
            bool: Success status
        """
        async with self._lock:
            try:
                if transaction_id not in self.transactions:
                    logger.error(f"Transaction {transaction_id} not found for commit")
                    return False
                
                transaction = self.transactions[transaction_id]
                
                if transaction.status != "prepared":
                    logger.error(f"Transaction {transaction_id} not in prepared state: {transaction.status}")
                    return False
                
                # Apply the change
                if transaction.client_id in self.subscriptions:
                    subscription = self.subscriptions[transaction.client_id]
                    subscription.token_ids = transaction.new_state.copy()
                    subscription.updated_at = time.time()
                    
                    # Remove client if no tokens left
                    if not subscription.token_ids:
                        del self.subscriptions[transaction.client_id]
                
                # Update transaction status
                transaction.status = "committed"
                
                # Move to history
                self._archive_transaction(transaction)
                
                logger.info(f"Committed remove operation {transaction_id} for client {transaction.client_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to commit remove tokens transaction {transaction_id}: {e}")
                return False
    
    async def rollback_transaction(self, transaction_id: str) -> bool:
        """
        Rollback a prepared transaction.
        
        Returns:
            bool: Success status
        """
        async with self._lock:
            try:
                if transaction_id not in self.transactions:
                    logger.warning(f"Transaction {transaction_id} not found for rollback")
                    return True  # Already cleaned up
                
                transaction = self.transactions[transaction_id]
                transaction.status = "rolled_back"
                
                # Move to history
                self._archive_transaction(transaction)
                
                logger.info(f"Rolled back transaction {transaction_id} for client {transaction.client_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to rollback transaction {transaction_id}: {e}")
                return False
    
    def _archive_transaction(self, transaction: SubscriptionTransaction):
        """Archive transaction to history and clean up"""
        self.transaction_history.append(transaction)
        
        # Remove from active transactions
        if transaction.transaction_id in self.transactions:
            del self.transactions[transaction.transaction_id]
        
        # Keep history size manageable
        if len(self.transaction_history) > self._max_history:
            self.transaction_history = self.transaction_history[-self._max_history:]
    
    async def get_pending_transactions(self) -> Dict[str, Dict[str, Any]]:
        """Get all pending transactions"""
        async with self._lock:
            return {
                txn_id: {
                    "client_id": txn.client_id,
                    "operation_type": txn.operation_type,
                    "token_ids": txn.token_ids,
                    "status": txn.status,
                    "age": time.time() - txn.timestamp
                }
                for txn_id, txn in self.transactions.items()
            }
    
    async def cleanup_stale_transactions(self, max_age: float = 300.0):
        """Clean up transactions older than max_age seconds"""
        async with self._lock:
            current_time = time.time()
            stale_transactions = []
            
            for txn_id, transaction in self.transactions.items():
                if current_time - transaction.timestamp > max_age:
                    stale_transactions.append(txn_id)
            
            for txn_id in stale_transactions:
                transaction = self.transactions[txn_id]
                transaction.status = "expired"
                self._archive_transaction(transaction)
                logger.warning(f"Cleaned up stale transaction: {txn_id}")
            
            return len(stale_transactions)
    
    async def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        async with self._lock:
            total_tokens = set()
            for subscription in self.subscriptions.values():
                total_tokens.update(subscription.token_ids)
            
            return {
                "total_clients": len(self.subscriptions),
                "total_unique_tokens": len(total_tokens),
                "pending_transactions": len(self.transactions),
                "transaction_history_size": len(self.transaction_history),
                "clients_by_token_count": self._get_client_distribution()
            }
    
    def _get_client_distribution(self) -> Dict[str, int]:
        """Get distribution of clients by number of tokens"""
        distribution = defaultdict(int)
        for subscription in self.subscriptions.values():
            token_count = len(subscription.token_ids)
            distribution[f"{token_count}_tokens"] += 1
        return dict(distribution)


# Global registry instance
_subscription_registry_instance = None

def get_subscription_registry() -> SubscriptionRegistry:
    """Get global subscription registry instance"""
    global _subscription_registry_instance
    if _subscription_registry_instance is None:
        _subscription_registry_instance = SubscriptionRegistry()
    return _subscription_registry_instance
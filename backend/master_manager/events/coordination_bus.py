"""
Coordination Bus - Extension of EventBus for 2-phase commit coordination

Builds on the existing EventBus to add acknowledgment tracking, 2-phase commit,
and rollback capabilities for distributed state management.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4
import json

from .event_bus import global_event_bus

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of operations that require coordination"""
    MARKET_SUBSCRIBE = "market_subscribe"
    MARKET_UNSUBSCRIBE = "market_unsubscribe"


class PhaseType(Enum):
    """2-phase commit phases"""
    PREPARE = "prepare"
    COMMIT = "commit"
    ROLLBACK = "rollback"


@dataclass
class CoordinationEvent:
    """Extended event with coordination metadata"""
    operation_id: str
    operation_type: OperationType
    phase: PhaseType
    client_id: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    expected_components: Optional[Set[str]] = None


@dataclass
class ComponentResponse:
    """Response from a component"""
    component_id: str
    operation_id: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class PendingCoordination:
    """Tracks pending coordination operations"""
    operation_id: str
    operation_type: OperationType
    phase: PhaseType
    expected_components: Set[str]
    responses: Dict[str, ComponentResponse] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    timeout: float = 30.0
    callback: Optional[Callable] = None
    event_data: Dict[str, Any] = field(default_factory=dict)


class CoordinationBus:
    """
    Coordination layer built on top of the existing EventBus.
    
    Provides:
    - 2-phase commit coordination
    - Component acknowledgment tracking
    - Automatic rollback on failures
    - Timeout handling
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus or global_event_bus
        self.pending_operations: Dict[str, PendingCoordination] = {}
        self.registered_components: Set[str] = set()
        self._cleanup_interval = 5.0
        self._cleanup_task = None
        
        # Subscribe to response events
        self.event_bus.subscribe("coordination.response", self._handle_component_response)
        self.event_bus.subscribe("coordination.timeout", self._handle_timeout)
        
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background cleanup task"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_operations())
    
    async def _cleanup_expired_operations(self):
        """Clean up expired operations"""
        while True:
            try:
                current_time = time.time()
                expired_ops = []
                
                for op_id, pending in self.pending_operations.items():
                    if current_time - pending.start_time > pending.timeout:
                        expired_ops.append(op_id)
                
                for op_id in expired_ops:
                    await self._handle_operation_timeout(op_id)
                
                await asyncio.sleep(self._cleanup_interval)
                
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
                await asyncio.sleep(5)
    
    async def _handle_operation_timeout(self, operation_id: str):
        """Handle timed-out operations"""
        if operation_id not in self.pending_operations:
            return
            
        pending = self.pending_operations[operation_id]
        responded_components = set(pending.responses.keys())
        missing_components = pending.expected_components - responded_components
        
        logger.warning(f"Operation {operation_id} timed out. Missing: {missing_components}")
        
        # Publish timeout event
        await self.event_bus.publish("coordination.timeout", {
            "operation_id": operation_id,
            "operation_type": pending.operation_type.value,
            "phase": pending.phase.value,
            "missing_components": list(missing_components),
            "responded_components": list(responded_components)
        })
        
        # Trigger rollback if this was prepare/commit phase
        if pending.phase in [PhaseType.PREPARE, PhaseType.COMMIT]:
            await self._trigger_rollback(pending)
        
        # Call callback with failure
        if pending.callback:
            try:
                await pending.callback(False, {
                    "error": "timeout",
                    "missing_components": list(missing_components),
                    "operation_id": operation_id
                })
            except Exception as e:
                logger.error(f"Error calling timeout callback: {e}")
        
        # Clean up
        del self.pending_operations[operation_id]
    
    async def _trigger_rollback(self, pending: PendingCoordination):
        """Trigger rollback for failed operation"""
        logger.info(f"Triggering rollback for operation {pending.operation_id}")
        
        rollback_event = CoordinationEvent(
            operation_id=pending.operation_id,
            operation_type=pending.operation_type,
            phase=PhaseType.ROLLBACK,
            client_id=pending.event_data.get("client_id", "system"),
            data=pending.event_data,
            expected_components=pending.expected_components
        )
        
        # Don't wait for rollback responses - fire and forget
        await self._broadcast_coordination_event(rollback_event, wait_for_responses=False)
    
    def register_component(self, component_id: str):
        """Register a component for coordination"""
        self.registered_components.add(component_id)
        logger.info(f"Component registered for coordination: {component_id}")
    
    def unregister_component(self, component_id: str):
        """Unregister a component"""
        self.registered_components.discard(component_id)
        logger.info(f"Component unregistered from coordination: {component_id}")
    
    async def coordinate_operation(self, operation_type: OperationType, client_id: str, 
                                 data: Dict[str, Any], expected_components: List[str],
                                 timeout: float = 30.0) -> Dict[str, Any]:
        """
        Coordinate a 2-phase commit operation.
        
        Args:
            operation_type: Type of operation (subscribe/unsubscribe)
            client_id: Client requesting the operation
            data: Operation data (token_ids, etc.)
            expected_components: List of components that must participate
            timeout: Maximum time to wait for each phase
            
        Returns:
            Dict with operation result
        """
        operation_id = str(uuid4())
        
        logger.info(f"Starting coordinated operation {operation_id}: {operation_type.value} for client {client_id}")
        
        try:
            # Phase 1: PREPARE
            prepare_result = await self._execute_phase(
                operation_id, operation_type, PhaseType.PREPARE,
                client_id, data, expected_components, timeout
            )
            
            if not prepare_result["success"]:
                logger.warning(f"Prepare phase failed for operation {operation_id}")
                return prepare_result
            
            # Phase 2: COMMIT
            commit_result = await self._execute_phase(
                operation_id, operation_type, PhaseType.COMMIT,
                client_id, data, expected_components, timeout
            )
            
            if not commit_result["success"]:
                logger.error(f"Commit phase failed for operation {operation_id} - triggering rollback")
                # Trigger rollback for partial commit failure
                rollback_event = CoordinationEvent(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    phase=PhaseType.ROLLBACK,
                    client_id=client_id,
                    data=data,
                    expected_components=set(expected_components)
                )
                await self._broadcast_coordination_event(rollback_event, wait_for_responses=False)
                return commit_result
            
            logger.info(f"Operation {operation_id} completed successfully")
            return commit_result
            
        except Exception as e:
            logger.error(f"Error in coordinated operation {operation_id}: {e}")
            return {
                "success": False,
                "operation_id": operation_id,
                "error": str(e),
                "phase": "exception"
            }
    
    async def _execute_phase(self, operation_id: str, operation_type: OperationType,
                           phase: PhaseType, client_id: str, data: Dict[str, Any],
                           expected_components: List[str], timeout: float) -> Dict[str, Any]:
        """Execute a single phase of the 2-phase commit"""
        
        event = CoordinationEvent(
            operation_id=operation_id,
            operation_type=operation_type,
            phase=phase,
            client_id=client_id,
            data=data,
            expected_components=set(expected_components)
        )
        
        return await self._broadcast_coordination_event(event, timeout)
    
    async def _broadcast_coordination_event(self, event: CoordinationEvent, 
                                          timeout: float = 30.0,
                                          wait_for_responses: bool = True) -> Dict[str, Any]:
        """Broadcast coordination event and optionally wait for responses"""
        
        if not wait_for_responses:
            # Fire and forget (for rollbacks)
            event_type = f"coordination.{event.operation_type.value}.{event.phase.value}"
            await self.event_bus.publish(event_type, {
                "operation_id": event.operation_id,
                "client_id": event.client_id,
                "data": event.data,
                "timestamp": event.timestamp
            })
            return {"success": True, "operation_id": event.operation_id}
        
        # Create pending operation for response tracking
        pending = PendingCoordination(
            operation_id=event.operation_id,
            operation_type=event.operation_type,
            phase=event.phase,
            expected_components=event.expected_components,
            timeout=timeout,
            event_data=event.data
        )
        
        self.pending_operations[event.operation_id] = pending
        
        # Broadcast event
        event_type = f"coordination.{event.operation_type.value}.{event.phase.value}"
        await self.event_bus.publish(event_type, {
            "operation_id": event.operation_id,
            "client_id": event.client_id,
            "data": event.data,
            "timestamp": event.timestamp,
            "expected_components": list(event.expected_components)
        })
        
        # Wait for all responses or timeout
        start_time = time.time()
        while event.operation_id in self.pending_operations:
            current_pending = self.pending_operations[event.operation_id]
            
            # Check if all components have responded
            if len(current_pending.responses) >= len(current_pending.expected_components):
                # All responses received
                success_count = sum(1 for resp in current_pending.responses.values() if resp.success)
                total_responses = len(current_pending.responses)
                
                success = success_count == total_responses
                
                result = {
                    "success": success,
                    "operation_id": event.operation_id,
                    "phase": event.phase.value,
                    "responses": {
                        comp_id: {"success": resp.success, "data": resp.data}
                        for comp_id, resp in current_pending.responses.items()
                    },
                    "success_count": success_count,
                    "total_expected": total_responses
                }
                
                # Clean up
                del self.pending_operations[event.operation_id]
                return result
            
            # Check timeout
            if time.time() - start_time > timeout:
                break
            
            await asyncio.sleep(0.1)
        
        # Timeout occurred - cleanup task will handle it
        return {
            "success": False,
            "operation_id": event.operation_id,
            "error": "timeout",
            "phase": event.phase.value
        }
    
    async def _handle_component_response(self, response_data: Dict[str, Any]):
        """Handle response from a component"""
        operation_id = response_data.get("operation_id")
        component_id = response_data.get("component_id")
        success = response_data.get("success", False)
        data = response_data.get("data", {})
        
        if operation_id not in self.pending_operations:
            logger.debug(f"Received response for unknown operation: {operation_id}")
            return
        
        pending = self.pending_operations[operation_id]
        
        # Record response
        response = ComponentResponse(
            component_id=component_id,
            operation_id=operation_id,
            success=success,
            data=data
        )
        
        pending.responses[component_id] = response
        
        logger.debug(f"Received {('ACK' if success else 'NACK')} from {component_id} for operation {operation_id}")
    
    async def _handle_timeout(self, timeout_data: Dict[str, Any]):
        """Handle timeout events"""
        operation_id = timeout_data.get("operation_id")
        logger.warning(f"Received timeout event for operation: {operation_id}")
    
    def get_pending_operations(self) -> Dict[str, Dict]:
        """Get current pending operations for debugging"""
        return {
            op_id: {
                "operation_type": pending.operation_type.value,
                "phase": pending.phase.value,
                "expected_components": list(pending.expected_components),
                "received_responses": list(pending.responses.keys()),
                "elapsed_time": time.time() - pending.start_time,
                "timeout": pending.timeout
            }
            for op_id, pending in self.pending_operations.items()
        }
    
    async def shutdown(self):
        """Shutdown the coordination bus"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clean up all pending operations
        for operation_id in list(self.pending_operations.keys()):
            await self._handle_operation_timeout(operation_id)
        
        logger.info("Coordination bus shutdown complete")


# Global coordination bus instance
_coordination_bus_instance = None

def get_coordination_bus() -> CoordinationBus:
    """Get global coordination bus instance"""
    global _coordination_bus_instance
    if _coordination_bus_instance is None:
        _coordination_bus_instance = CoordinationBus()
    return _coordination_bus_instance
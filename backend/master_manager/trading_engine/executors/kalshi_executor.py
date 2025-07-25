"""
Kalshi Order Executor

Handles order placement on Kalshi platform using existing authenticated client.
"""

import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class KalshiExecutor:
    """
    Handles order execution on Kalshi platform.
    
    Uses the existing authenticated KalshiClient for REST API order placement.
    """
    
    def __init__(self, kalshi_client=None):
        """
        Initialize Kalshi executor.
        
        Args:
            kalshi_client: Existing authenticated KalshiClient instance
        """
        self.kalshi_client = kalshi_client
        self.is_available = kalshi_client is not None and hasattr(kalshi_client, 'config')
        self.api_base_url = "https://api.elections.kalshi.com/trade-api/v2"
        
        if not self.is_available:
            logger.warning("KalshiExecutor initialized without proper client - orders will fail")
        else:
            logger.info("KalshiExecutor initialized with authenticated client")
    
    async def place_order(self, 
                         market_id: str,
                         side: str,  # "yes" or "no"
                         action: str,  # "buy" or "sell"
                         quantity: int,
                         price_cents: int,
                         max_slippage: float = 0.01) -> Dict[str, Any]:
        """
        Place an order on Kalshi using the correct API format.
        
        Args:
            market_id: Kalshi market identifier (ticker)
            side: "yes" or "no" contract side
            action: "buy" or "sell"
            quantity: Number of contracts
            price_cents: Price in cents (1-99)
            max_slippage: Maximum allowed slippage
        
        Returns:
            Dict containing execution result
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Kalshi client not available",
                "platform": "kalshi"
            }
        
        try:
            logger.info(f"🔵 KALSHI ORDER | ticker={market_id} | {action} {quantity} {side} @ {price_cents}¢")
            
            # Prepare order payload according to Kalshi API spec
            order_payload = {
                "ticker": market_id,
                "client_order_id": self._generate_order_id(),
                "side": side.lower(),  # "yes" or "no"
                "action": action.lower(),  # "buy" or "sell"
                "count": quantity,
                "type": "limit",  # Use limit orders for better control
            }
            
            # Add price based on side (Kalshi requires exactly one of yes_price or no_price)
            if side.lower() == "yes":
                order_payload["yes_price"] = price_cents
            else:
                order_payload["no_price"] = price_cents
            
            # Execute order via REST API
            order_result = await self._place_order_via_rest(order_payload)
            
            if order_result.get("success", False):
                logger.info(f"✅ KALSHI ORDER SUCCESS | order_id={order_result.get('order_id')} | "
                           f"status={order_result.get('status', 'unknown')}")
                
                return {
                    "success": True,
                    "platform": "kalshi",
                    "order_id": order_result.get("order_id"),
                    "filled_quantity": order_result.get("filled_quantity", 0),
                    "filled_price": order_result.get("filled_price"),
                    "status": order_result.get("status"),
                    "timestamp": datetime.now().isoformat(),
                    "details": order_result
                }
            else:
                error_msg = order_result.get("error", "Unknown Kalshi order error")
                logger.error(f"❌ KALSHI ORDER FAILED | error={error_msg}")
                
                return {
                    "success": False,
                    "platform": "kalshi",
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
        
        except Exception as e:
            logger.error(f"❌ KALSHI ORDER EXCEPTION | error={e}", exc_info=True)
            return {
                "success": False,
                "platform": "kalshi",
                "error": f"Exception: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    async def _place_order_via_rest(self, order_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place order via Kalshi REST API using existing client authentication.
        
        Args:
            order_payload: Order parameters dictionary
        
        Returns:
            Order execution result
        """
        try:
            # Create authenticated headers using the existing client's method
            auth_headers = self.kalshi_client._create_auth_headers("POST", "/trade-api/v2/portfolio/orders")
            
            # Add content type
            headers = {
                **auth_headers,
                "Content-Type": "application/json"
            }
            
            url = f"{self.api_base_url}/portfolio/orders"
            
            logger.debug(f"Placing Kalshi order: {order_payload}")
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=order_payload, headers=headers) as response:
                    response_data = await response.json()
                    
                    if response.status == 200 or response.status == 201:
                        # Parse successful response
                        order_data = response_data.get("order", {})
                        
                        return {
                            "success": True,
                            "order_id": order_data.get("order_id"),
                            "status": order_data.get("status", "pending"),
                            "filled_quantity": order_data.get("queue_position", 0),  # Kalshi-specific field
                            "filled_price": order_data.get("yes_price") or order_data.get("no_price"),
                            "raw_response": response_data
                        }
                    else:
                        # Handle API error response
                        error_detail = response_data.get("detail", f"HTTP {response.status}")
                        logger.error(f"Kalshi API error: {response.status} - {error_detail}")
                        
                        return {
                            "success": False,
                            "error": f"Kalshi API error: {error_detail}",
                            "status_code": response.status,
                            "raw_response": response_data
                        }
        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Kalshi API request timeout"
            }
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error": f"Kalshi API connection error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in Kalshi order placement: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Kalshi order failed: {str(e)}"
            }
    
    def _generate_order_id(self) -> str:
        """Generate unique client order ID."""
        timestamp = int(datetime.now().timestamp() * 1000)
        return f"arb_{timestamp}"
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of a placed order via Kalshi API.
        
        Args:
            order_id: Order identifier
        
        Returns:
            Order status information
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Kalshi client not available"
            }
        
        try:
            # Create authenticated headers
            auth_headers = self.kalshi_client._create_auth_headers("GET", f"/trade-api/v2/portfolio/orders/{order_id}")
            url = f"{self.api_base_url}/portfolio/orders/{order_id}"
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=auth_headers) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        order_data = response_data.get("order", {})
                        
                        return {
                            "success": True,
                            "order_id": order_id,
                            "status": order_data.get("status", "unknown"),
                            "filled_quantity": order_data.get("queue_position", 0),
                            "details": order_data
                        }
                    else:
                        error_data = await response.json()
                        return {
                            "success": False,
                            "error": f"Kalshi API error: {error_data.get('detail', 'Unknown error')}"
                        }
        
        except Exception as e:
            logger.error(f"Error checking Kalshi order status: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a placed order via Kalshi API.
        
        Args:
            order_id: Order identifier
        
        Returns:
            Cancellation result
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Kalshi client not available"
            }
        
        try:
            # Create authenticated headers
            auth_headers = self.kalshi_client._create_auth_headers("DELETE", f"/trade-api/v2/portfolio/orders/{order_id}")
            url = f"{self.api_base_url}/portfolio/orders/{order_id}"
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.delete(url, headers=auth_headers) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        return {
                            "success": True,
                            "order_id": order_id,
                            "message": "Order cancelled successfully",
                            "details": response_data
                        }
                    else:
                        error_data = await response.json()
                        return {
                            "success": False,
                            "error": f"Kalshi cancellation failed: {error_data.get('detail', 'Unknown error')}"
                        }
        
        except Exception as e:
            logger.error(f"Error cancelling Kalshi order: {e}")
            return {
                "success": False,
                "error": str(e)
            }
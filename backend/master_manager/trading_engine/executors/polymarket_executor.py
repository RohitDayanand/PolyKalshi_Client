"""
Polymarket Order Executor

Handles order placement on Polymarket platform via proxy forwarding.
"""

import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PolymarketExecutor:
    """
    Handles order execution on Polymarket platform via proxy.
    
    Forwards orders to a proxy service that handles CLOB API interaction.
    """
    
    def __init__(self, proxy_config: Optional[Dict[str, Any]] = None):
        """
        Initialize Polymarket executor.
        
        Args:
            proxy_config: Configuration for proxy service including:
                - url: Proxy service URL
                - headers: Required headers for authentication
                - timeout: Request timeout in seconds
        """
        self.proxy_config = proxy_config or {}
        self.proxy_url = self.proxy_config.get("url")
        self.headers = self.proxy_config.get("headers", {})
        self.timeout = self.proxy_config.get("timeout", 30)
        
        self.is_available = self.proxy_url is not None
        
        if not self.is_available:
            logger.warning("PolymarketExecutor initialized without proxy config - orders will fail")
        else:
            logger.info(f"PolymarketExecutor initialized with proxy: {self.proxy_url}")
    
    async def place_order(self,
                         asset_id: str,
                         side: str,  # "buy" or "sell"
                         quantity: float,
                         price: float,
                         max_slippage: float = 0.01) -> Dict[str, Any]:
        """
        Place an order on Polymarket via proxy.
        
        Args:
            asset_id: Polymarket asset identifier (token_id)
            side: "buy" or "sell"
            quantity: Order quantity in tokens
            price: Price per token (0.0-1.0)
            max_slippage: Maximum allowed slippage
        
        Returns:
            Dict containing execution result
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Polymarket proxy not configured",
                "platform": "polymarket"
            }
        
        try:
            logger.info(f"🟢 POLYMARKET ORDER | asset={asset_id} | {side} {quantity:.2f} @ {price:.4f}")
            
            # Prepare order payload for proxy
            order_payload = {
                "asset_id": asset_id,
                "side": side.lower(),
                "quantity": quantity,
                "price": price,
                "max_slippage": max_slippage,
                "order_type": "market",  # Start with market orders
                "client_order_id": self._generate_order_id(),
                "timestamp": datetime.now().isoformat()
            }
            
            # Forward order to proxy
            proxy_result = await self._forward_to_proxy(order_payload)
            
            if proxy_result.get("success", False):
                logger.info(f"✅ POLYMARKET ORDER SUCCESS | order_id={proxy_result.get('order_id')} | "
                           f"filled={proxy_result.get('filled_quantity', 0)}")
                
                return {
                    "success": True,
                    "platform": "polymarket",
                    "order_id": proxy_result.get("order_id"),
                    "filled_quantity": proxy_result.get("filled_quantity", 0),
                    "filled_price": proxy_result.get("filled_price"),
                    "timestamp": datetime.now().isoformat(),
                    "details": proxy_result
                }
            else:
                error_msg = proxy_result.get("error", "Unknown Polymarket proxy error")
                logger.error(f"❌ POLYMARKET ORDER FAILED | error={error_msg}")
                
                return {
                    "success": False,
                    "platform": "polymarket",
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
        
        except Exception as e:
            logger.error(f"❌ POLYMARKET ORDER EXCEPTION | error={e}", exc_info=True)
            return {
                "success": False,
                "platform": "polymarket",
                "error": f"Exception: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    async def _forward_to_proxy(self, order_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Forward order to proxy service.
        
        Args:
            order_payload: Order details to forward
        
        Returns:
            Proxy response
        """
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Merge custom headers with default headers
                request_headers = {
                    "Content-Type": "application/json",
                    **self.headers
                }
                
                logger.debug(f"Forwarding order to proxy: {self.proxy_url}")
                
                async with session.post(
                    f"{self.proxy_url}/api/orders",
                    json=order_payload,
                    headers=request_headers
                ) as response:
                    
                    response_data = await response.json()
                    
                    if response.status == 200:
                        return {
                            "success": True,
                            "order_id": response_data.get("order_id"),
                            "filled_quantity": response_data.get("filled_quantity", 0),
                            "filled_price": response_data.get("filled_price"),
                            "raw_response": response_data
                        }
                    else:
                        error_msg = response_data.get("error", f"HTTP {response.status}")
                        return {
                            "success": False,
                            "error": f"Proxy error: {error_msg}",
                            "status_code": response.status
                        }
        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Proxy request timeout after {self.timeout}s"
            }
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error": f"Proxy connection error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Proxy request failed: {str(e)}"
            }
    
    def _generate_order_id(self) -> str:
        """Generate unique client order ID."""
        timestamp = int(datetime.now().timestamp() * 1000)
        return f"poly_arb_{timestamp}"
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of a placed order via proxy.
        
        Args:
            order_id: Order identifier
        
        Returns:
            Order status information
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Polymarket proxy not configured"
            }
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                request_headers = {
                    "Content-Type": "application/json",
                    **self.headers
                }
                
                async with session.get(
                    f"{self.proxy_url}/api/orders/{order_id}",
                    headers=request_headers
                ) as response:
                    
                    if response.status == 200:
                        response_data = await response.json()
                        return {
                            "success": True,
                            "order_id": order_id,
                            "status": response_data.get("status", "unknown"),
                            "details": response_data
                        }
                    else:
                        error_data = await response.json()
                        return {
                            "success": False,
                            "error": f"Proxy status check failed: {error_data.get('error', 'Unknown error')}"
                        }
        
        except Exception as e:
            logger.error(f"Error checking Polymarket order status: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a placed order via proxy.
        
        Args:
            order_id: Order identifier
        
        Returns:
            Cancellation result
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Polymarket proxy not configured"
            }
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                request_headers = {
                    "Content-Type": "application/json",
                    **self.headers
                }
                
                async with session.delete(
                    f"{self.proxy_url}/api/orders/{order_id}",
                    headers=request_headers
                ) as response:
                    
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
                            "error": f"Proxy cancellation failed: {error_data.get('error', 'Unknown error')}"
                        }
        
        except Exception as e:
            logger.error(f"Error cancelling Polymarket order: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def update_proxy_config(self, proxy_config: Dict[str, Any]):
        """Update proxy configuration."""
        self.proxy_config = proxy_config
        self.proxy_url = proxy_config.get("url")
        self.headers = proxy_config.get("headers", {})
        self.timeout = proxy_config.get("timeout", 30)
        self.is_available = self.proxy_url is not None
        
        logger.info(f"Updated Polymarket proxy config: {self.proxy_url}")
    
    async def test_proxy_connection(self) -> Dict[str, Any]:
        """
        Test connection to proxy service.
        
        Returns:
            Connection test result
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Proxy not configured"
            }
        
        try:
            timeout = aiohttp.ClientTimeout(total=5)  # Short timeout for test
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.proxy_url}/health",
                    headers=self.headers
                ) as response:
                    
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "Proxy connection successful",
                            "proxy_url": self.proxy_url
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Proxy returned HTTP {response.status}"
                        }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Proxy connection failed: {str(e)}"
            }
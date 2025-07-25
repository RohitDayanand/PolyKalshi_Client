"""
Core Trading Engine

Subscribes to arbitrage alerts and manages automated order execution
with modular settings and risk controls.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from backend.master_manager.event_bus import EventBus
from backend.master_manager.arbitrage_detector import ArbitrageOpportunity
from .order_executor import OrderExecutor

logger = logging.getLogger(__name__)

@dataclass
class TradingSettings:
    """Global trading engine configuration."""
    enable_trading: bool = False
    cooldown_seconds: float = 30.0
    max_position_size: float = 1000.0
    min_profit_threshold: float = 0.02
    max_slippage: float = 0.01
    platform_enabled: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.platform_enabled is None:
            self.platform_enabled = {"kalshi": True, "polymarket": True}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradingSettings':
        return cls(**data)


class CooldownManager:
    """Manages trading cooldowns to prevent excessive order frequency."""
    
    def __init__(self, cooldown_seconds: float = 30.0):
        self.cooldown_seconds = cooldown_seconds
        self.last_trade_times: Dict[str, datetime] = {}
    
    def can_trade(self, market_pair: str) -> bool:
        """Check if enough time has passed since last trade for this market pair."""
        if market_pair not in self.last_trade_times:
            return True
        
        time_since_last = datetime.now() - self.last_trade_times[market_pair]
        return time_since_last.total_seconds() >= self.cooldown_seconds
    
    def record_trade(self, market_pair: str):
        """Record a trade execution timestamp."""
        self.last_trade_times[market_pair] = datetime.now()
    
    def update_cooldown(self, cooldown_seconds: float):
        """Update cooldown duration."""
        self.cooldown_seconds = cooldown_seconds
        logger.info(f"Updated trading cooldown to {cooldown_seconds} seconds")


class TradingEngine:
    """
    Core trading engine that subscribes to arbitrage alerts and executes orders.
    
    Features:
    - Event-driven arbitrage alert subscription
    - Modular platform-specific execution
    - Cooldown management
    - Real-time settings updates
    - Execution tracking and logging
    """
    
    def __init__(self, 
                 event_bus: EventBus,
                 kalshi_client=None,
                 polymarket_proxy_config: Optional[Dict[str, Any]] = None,
                 settings: Optional[TradingSettings] = None):
        """
        Initialize the trading engine.
        
        Args:
            event_bus: EventBus instance for subscribing to arbitrage alerts
            kalshi_client: Existing Kalshi client for order execution
            polymarket_proxy_config: Configuration for Polymarket proxy forwarding
            settings: Trading configuration settings
        """
        self.event_bus = event_bus
        self.settings = settings or TradingSettings()
        
        # Initialize cooldown manager
        self.cooldown_manager = CooldownManager(self.settings.cooldown_seconds)
        
        # Initialize order executor
        self.order_executor = OrderExecutor(
            kalshi_client=kalshi_client,
            polymarket_proxy_config=polymarket_proxy_config
        )
        
        # Track execution statistics
        self.stats = {
            "alerts_received": 0,
            "orders_attempted": 0,
            "orders_successful": 0,
            "orders_failed": 0,
            "cooldown_blocks": 0,
            "disabled_blocks": 0
        }
        
        # Subscribe to arbitrage alerts
        self._subscribe_to_events()
        
        logger.info(f"TradingEngine initialized with settings: {self.settings.to_dict()}")
    
    def _subscribe_to_events(self):
        """Subscribe to relevant EventBus events."""
        # Subscribe to arbitrage alerts
        self.event_bus.subscribe("arbitrage.alert", self._handle_arbitrage_alert)
        
        # Subscribe to settings updates
        self.event_bus.subscribe("trading.settings_update", self._handle_settings_update)
        
        logger.info("TradingEngine subscribed to arbitrage.alert and trading.settings_update events")
    
    async def _handle_arbitrage_alert(self, opportunity: ArbitrageOpportunity):
        """
        Handle incoming arbitrage alerts and decide whether to execute trades.
        
        Args:
            opportunity: ArbitrageOpportunity from the arbitrage detector
        """
        self.stats["alerts_received"] += 1
        
        try:
            # Check if trading is globally enabled
            if not self.settings.enable_trading:
                self.stats["disabled_blocks"] += 1
                logger.debug(f"Trading disabled - skipping opportunity: {opportunity.market_pair}")
                return
            
            # Check profit threshold
            if opportunity.spread < self.settings.min_profit_threshold:
                logger.debug(f"Spread {opportunity.spread:.3f} below threshold {self.settings.min_profit_threshold:.3f} - skipping")
                return
            
            # Check cooldown
            if not self.cooldown_manager.can_trade(opportunity.market_pair):
                self.stats["cooldown_blocks"] += 1
                logger.debug(f"Cooldown active for {opportunity.market_pair} - skipping")
                return
            
            # Check platform availability
            platforms_needed = self._get_required_platforms(opportunity)
            for platform in platforms_needed:
                if not self.settings.platform_enabled.get(platform, False):
                    logger.debug(f"Platform {platform} disabled - skipping opportunity")
                    return
            
            # Execute the arbitrage trade
            await self._execute_arbitrage_trade(opportunity)
            
        except Exception as e:
            logger.error(f"Error handling arbitrage alert: {e}", exc_info=True)
            self.stats["orders_failed"] += 1
    
    def _get_required_platforms(self, opportunity: ArbitrageOpportunity) -> list[str]:
        """Determine which platforms are needed for this opportunity."""
        # All arbitrage opportunities require both Kalshi and Polymarket
        return ["kalshi", "polymarket"]
    
    async def _execute_arbitrage_trade(self, opportunity: ArbitrageOpportunity):
        """
        Execute the arbitrage trade across both platforms.
        
        Args:
            opportunity: The arbitrage opportunity to execute
        """
        self.stats["orders_attempted"] += 1
        
        try:
            logger.info(f"🚀 EXECUTING ARBITRAGE | pair={opportunity.market_pair} | "
                       f"spread={opportunity.spread:.3f} | size=${opportunity.execution_size:.1f}")
            
            # Record trade attempt for cooldown
            self.cooldown_manager.record_trade(opportunity.market_pair)
            
            # Execute the trade using the order executor
            execution_result = await self.order_executor.execute_arbitrage(
                opportunity=opportunity,
                max_slippage=self.settings.max_slippage,
                max_position_size=self.settings.max_position_size
            )
            
            if execution_result["success"]:
                self.stats["orders_successful"] += 1
                logger.info(f"✅ ARBITRAGE EXECUTED | pair={opportunity.market_pair} | "
                           f"result={execution_result}")
                
                # Publish execution event
                self.event_bus.publish("trading.execution_success", {
                    "opportunity": opportunity,
                    "result": execution_result,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                self.stats["orders_failed"] += 1
                logger.error(f"❌ ARBITRAGE FAILED | pair={opportunity.market_pair} | "
                            f"error={execution_result.get('error', 'Unknown error')}")
                
                # Publish failure event
                self.event_bus.publish("trading.execution_failure", {
                    "opportunity": opportunity,
                    "result": execution_result,
                    "timestamp": datetime.now().isoformat()
                })
        
        except Exception as e:
            self.stats["orders_failed"] += 1
            logger.error(f"❌ ARBITRAGE EXECUTION ERROR | pair={opportunity.market_pair} | error={e}", exc_info=True)
            
            # Publish error event
            self.event_bus.publish("trading.execution_error", {
                "opportunity": opportunity,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    async def _handle_settings_update(self, updated_settings: Dict[str, Any]):
        """
        Handle real-time settings updates from EventBus.
        
        Args:
            updated_settings: Dictionary containing updated settings
        """
        try:
            old_settings = self.settings.to_dict()
            
            # Update settings
            self.settings = TradingSettings.from_dict(updated_settings)
            
            # Update cooldown manager if cooldown changed
            if old_settings["cooldown_seconds"] != self.settings.cooldown_seconds:
                self.cooldown_manager.update_cooldown(self.settings.cooldown_seconds)
            
            logger.info(f"✅ Trading engine settings updated")
            logger.info(f"   Old: {old_settings}")
            logger.info(f"   New: {self.settings.to_dict()}")
            
            # Publish confirmation
            self.event_bus.publish("trading.settings_updated", {
                "old_settings": old_settings,
                "new_settings": self.settings.to_dict(),
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error updating trading settings: {e}", exc_info=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get trading engine statistics."""
        return {
            **self.stats,
            "settings": self.settings.to_dict(),
            "cooldown_status": {
                market_pair: {
                    "last_trade": last_trade.isoformat(),
                    "can_trade": self.cooldown_manager.can_trade(market_pair)
                }
                for market_pair, last_trade in self.cooldown_manager.last_trade_times.items()
            }
        }
    
    def update_settings(self, **kwargs):
        """Update trading settings programmatically."""
        updated_dict = self.settings.to_dict()
        updated_dict.update(kwargs)
        
        # Publish settings update event (will trigger _handle_settings_update)
        self.event_bus.publish("trading.settings_update", updated_dict)
    
    def enable_trading(self):
        """Enable trading."""
        self.update_settings(enable_trading=True)
    
    def disable_trading(self):
        """Disable trading."""
        self.update_settings(enable_trading=False)
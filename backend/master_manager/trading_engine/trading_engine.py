"""
Trading Engine - Core arbitrage execution engine with configurable settings.

This module provides:
- TradingSettings: Configuration for trading parameters and risk management
- TradingEngine: Main trading engine that executes arbitrage opportunities
- Integration with Kalshi and Polymarket APIs
- Real-time setting updates and emergency controls
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, asdict

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.master_manager.arbitrage_detector import ArbitrageOpportunity
    from backend.master_manager.events.event_bus import EventBus
else:
    # For runtime, use Any to avoid import issues during testing
    ArbitrageOpportunity = Any
    EventBus = Any

logger = logging.getLogger(__name__)


@dataclass
class TradingSettings:
    """
    Trading engine configuration and risk management settings.
    
    All settings can be updated at runtime for live risk management.
    """
    # Core controls
    enable_trading: bool = False  # Global trading enable/disable
    
    # Risk management
    cooldown_seconds: float = 30.0  # Minimum time between trades on same market
    max_position_size: float = 1000.0  # Maximum position size in USD
    min_profit_threshold: float = 0.02  # Minimum profit threshold (2%)
    max_slippage: float = 0.01  # Maximum allowed slippage (1%)
    
    # Platform controls
    platform_enabled: Dict[str, bool] = None  # Per-platform enable/disable
    
    # Advanced settings
    max_concurrent_orders: int = 5  # Maximum simultaneous orders
    order_timeout_seconds: float = 30.0  # Order execution timeout
    retry_attempts: int = 3  # Number of retry attempts for failed orders
    
    def __post_init__(self):
        """Initialize default platform settings if not provided."""
        if self.platform_enabled is None:
            self.platform_enabled = {
                "kalshi": True,
                "polymarket": True
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradingSettings':
        """Create settings from dictionary."""
        return cls(**data)
    
    def update(self, **kwargs) -> None:
        """
        Update settings with validation.
        
        Args:
            **kwargs: Settings to update
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                # Validation
                if key == "min_profit_threshold" and (value < 0 or value > 1):
                    raise ValueError("min_profit_threshold must be between 0.0 and 1.0")
                if key == "max_slippage" and (value < 0 or value > 1):
                    raise ValueError("max_slippage must be between 0.0 and 1.0")
                if key == "cooldown_seconds" and value < 0:
                    raise ValueError("cooldown_seconds must be non-negative")
                if key == "max_position_size" and value <= 0:
                    raise ValueError("max_position_size must be positive")
                
                setattr(self, key, value)
                logger.info(f"Updated trading setting: {key} = {value}")
            else:
                logger.warning(f"Unknown trading setting: {key}")


class TradingEngine:
    """
    Core arbitrage execution engine.
    
    Features:
    - Real-time arbitrage opportunity processing
    - Risk management and position sizing
    - Multi-platform order execution (Kalshi, Polymarket)
    - Cooldown management to prevent over-trading
    - Emergency shutdown and live setting updates
    - Comprehensive statistics and monitoring
    """
    
    def __init__(self, 
                 event_bus,  # EventBus type hint removed to avoid import issues
                 kalshi_client=None,  # TODO: Type this properly when Kalshi client is available
                 polymarket_proxy_config=None,  # TODO: Type this properly
                 settings: Optional[TradingSettings] = None):
        """
        Initialize trading engine.
        
        Args:
            event_bus: EventBus for communication
            kalshi_client: Kalshi API client instance
            polymarket_proxy_config: Polymarket proxy configuration
            settings: Trading settings (uses defaults if not provided)
        """
        self.event_bus = event_bus
        self.kalshi_client = kalshi_client  
        self.polymarket_proxy_config = polymarket_proxy_config
        self.settings = settings or TradingSettings()
        
        # State management
        self.active_orders: Dict[str, Dict[str, Any]] = {}  # order_id -> order_info
        self.market_cooldowns: Dict[str, float] = {}  # market_pair -> last_trade_time
        self.emergency_shutdown = False
        
        # Statistics
        self.stats = {
            "initialized_at": datetime.now().isoformat(),
            "opportunities_received": 0,
            "opportunities_processed": 0,
            "opportunities_filtered": 0,
            "orders_attempted": 0,
            "orders_successful": 0,
            "orders_failed": 0,
            "total_volume_usd": 0.0,
            "total_profit_usd": 0.0,
            "emergency_shutdowns": 0,
            "settings_updates": 0
        }
        
        logger.info("✅ Trading engine initialized")
        logger.info(f"⚙️ Settings: {self.settings.to_dict()}")
    
    def enable_trading(self) -> None:
        """Enable trading globally."""
        self.settings.enable_trading = True
        self.emergency_shutdown = False
        logger.info("🟢 TRADING ENABLED")
    
    def disable_trading(self) -> None:
        """Disable trading globally.""" 
        self.settings.enable_trading = False
        logger.info("🔴 TRADING DISABLED")
    
    def emergency_shutdown_trading(self) -> None:
        """Emergency shutdown - disable trading and cancel all active orders."""
        self.settings.enable_trading = False
        self.emergency_shutdown = True
        self.stats["emergency_shutdowns"] += 1
        
        logger.critical("🚨 EMERGENCY SHUTDOWN ACTIVATED")
        
        # TODO: Cancel all active orders when order management is implemented
        # asyncio.create_task(self._cancel_all_orders())
    
    def update_settings(self, **kwargs) -> None:
        """
        Update trading settings at runtime.
        
        Args:
            **kwargs: Settings to update
        """
        try:
            old_settings = self.settings.to_dict()
            self.settings.update(**kwargs)
            self.stats["settings_updates"] += 1
            
            logger.info(f"⚙️ Settings updated: {kwargs}")
            
            # Log significant changes
            if "enable_trading" in kwargs:
                if kwargs["enable_trading"]:
                    logger.info("🟢 Trading enabled via settings update")
                else:
                    logger.info("🔴 Trading disabled via settings update")
                    
        except ValueError as e:
            logger.error(f"❌ Invalid setting update: {e}")
            raise
    
    def _is_market_in_cooldown(self, market_pair: str) -> bool:
        """
        Check if market is in cooldown period.
        
        Args:
            market_pair: Market identifier
            
        Returns:
            bool: True if market is in cooldown
        """
        last_trade_time = self.market_cooldowns.get(market_pair, 0)
        cooldown_until = last_trade_time + self.settings.cooldown_seconds
        current_time = time.time()
        
        if current_time < cooldown_until:
            remaining = cooldown_until - current_time
            logger.debug(f"⏳ Market {market_pair} in cooldown for {remaining:.1f}s")
            return True
        
        return False
    
    def _set_market_cooldown(self, market_pair: str) -> None:
        """Set cooldown timer for market after trade execution."""
        self.market_cooldowns[market_pair] = time.time()
        logger.debug(f"⏱️ Set cooldown for {market_pair} ({self.settings.cooldown_seconds}s)")
    
    def _should_process_opportunity(self, opportunity) -> tuple[bool, str]:
        """
        Determine if opportunity should be processed based on current settings.
        
        Args:
            opportunity: ArbitrageOpportunity to evaluate
            
        Returns:
            tuple[bool, str]: (should_process, reason)
        """
        # Check emergency shutdown
        if self.emergency_shutdown:
            return False, "emergency_shutdown_active"
        
        # Check if trading is enabled
        if not self.settings.enable_trading:
            return False, "trading_disabled"
        
        # Check minimum profit threshold
        if opportunity.spread < self.settings.min_profit_threshold:
            return False, f"spread_too_low_{opportunity.spread:.3f}<{self.settings.min_profit_threshold:.3f}"
        
        # Check market cooldown
        if self._is_market_in_cooldown(opportunity.market_pair):
            return False, "market_in_cooldown"
        
        # Check position size limits
        if opportunity.execution_size > self.settings.max_position_size:
            return False, f"position_too_large_{opportunity.execution_size}>{self.settings.max_position_size}"
        
        # Check platform availability
        required_platforms = self._get_required_platforms(opportunity)
        for platform in required_platforms:
            if not self.settings.platform_enabled.get(platform, False):
                return False, f"platform_disabled_{platform}"
        
        # Check concurrent order limits
        if len(self.active_orders) >= self.settings.max_concurrent_orders:
            return False, "max_concurrent_orders_reached"
        
        return True, "passed_all_filters"
    
    def _get_required_platforms(self, opportunity) -> Set[str]:
        """Get list of platforms required for this opportunity."""
        platforms = set()
        
        # Determine platforms based on opportunity structure
        if hasattr(opportunity, 'kalshi_market_id') and opportunity.kalshi_market_id:
            platforms.add("kalshi")
        if hasattr(opportunity, 'polymarket_asset_id') and opportunity.polymarket_asset_id:
            platforms.add("polymarket")
            
        return platforms
    
    async def _handle_arbitrage_alert(self, opportunity) -> None:
        """
        Process arbitrage opportunity and potentially execute trades.
        
        Args:
            opportunity: ArbitrageOpportunity to process
        """
        self.stats["opportunities_received"] += 1
        
        try:
            logger.debug(f"📊 Processing opportunity | market={opportunity.market_pair} | "
                        f"spread={opportunity.spread:.3f} | size=${opportunity.execution_size:.1f}")
            
            # Check if we should process this opportunity
            should_process, reason = self._should_process_opportunity(opportunity)
            
            if not should_process:
                self.stats["opportunities_filtered"] += 1
                logger.debug(f"🚫 Filtered opportunity: {reason} | market={opportunity.market_pair}")
                return
            
            self.stats["opportunities_processed"] += 1
            
            logger.info(f"🎯 Executing arbitrage | market={opportunity.market_pair} | "
                       f"spread={opportunity.spread:.3f} | size=${opportunity.execution_size:.1f}")
            
            # Execute the arbitrage trade
            success = await self._execute_arbitrage_trade(opportunity)
            
            if success:
                self.stats["orders_successful"] += 1
                self.stats["total_volume_usd"] += opportunity.execution_size
                self.stats["total_profit_usd"] += opportunity.execution_size * opportunity.spread
                
                # Set cooldown for this market
                self._set_market_cooldown(opportunity.market_pair)
                
                logger.info(f"✅ Arbitrage executed successfully | market={opportunity.market_pair} | "
                           f"profit=${opportunity.execution_size * opportunity.spread:.2f}")
            else:
                self.stats["orders_failed"] += 1
                logger.warning(f"❌ Arbitrage execution failed | market={opportunity.market_pair}")
                
        except Exception as e:
            self.stats["orders_failed"] += 1
            logger.error(f"💥 Error processing arbitrage opportunity: {e}", exc_info=True)
    
    async def _execute_arbitrage_trade(self, opportunity) -> bool:
        """
        Execute the actual arbitrage trade across platforms.
        
        Args:
            opportunity: ArbitrageOpportunity to execute
            
        Returns:
            bool: True if execution was successful
        """
        self.stats["orders_attempted"] += 1
        
        try:
            # TODO: Implement actual order execution
            # This is a placeholder until the order execution system is built
            
            logger.info(f"🔄 Executing arbitrage trade (MOCK) | market={opportunity.market_pair}")
            
            # Simulate execution time
            await asyncio.sleep(0.1)
            
            # For now, always return success (this should be replaced with real execution logic)
            logger.info(f"✅ Mock arbitrage execution completed | market={opportunity.market_pair}")
            
            return True
            
        except Exception as e:
            logger.error(f"💥 Error executing arbitrage trade: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive trading engine statistics.
        
        Returns:
            Dict containing all statistics and current state
        """
        current_time = datetime.now()
        
        return {
            **self.stats,
            "current_time": current_time.isoformat(),
            "settings": self.settings.to_dict(),
            "active_orders_count": len(self.active_orders),
            "markets_in_cooldown": len([
                market for market, last_trade in self.market_cooldowns.items()
                if time.time() < (last_trade + self.settings.cooldown_seconds)
            ]),
            "emergency_shutdown": self.emergency_shutdown,
            "trading_enabled": self.settings.enable_trading
        }
    
    def get_market_cooldown_status(self) -> Dict[str, float]:
        """
        Get cooldown status for all markets.
        
        Returns:
            Dict mapping market_pair to remaining cooldown time (0 if not in cooldown)
        """
        current_time = time.time()
        cooldown_status = {}
        
        for market_pair, last_trade in self.market_cooldowns.items():
            cooldown_until = last_trade + self.settings.cooldown_seconds
            remaining = max(0, cooldown_until - current_time)
            cooldown_status[market_pair] = remaining
            
        return cooldown_status
import logging
from datetime import datetime
from typing import Dict, Any
from pyee.asyncio import AsyncIOEventEmitter

logger = logging.getLogger(__name__)

class MessageProcessor:
    """
    Message processor subclass using composition pattern.
    Processes tagged messages from different platforms and emits events
    through pyee event emitter with rate limiting and testing capabilities.
    """
    def __init__(self, manager):
        self.manager = manager
        self.event_emitter = AsyncIOEventEmitter()
        # Rate limiting tracking for testing
        self.rate_limit_stats = {
            "total_messages": 0,
            "rate_limited_messages": 0,
            "platform_stats": {},
            "last_reset": datetime.now()
        }
        # Message type handlers for different event types
        self.message_handlers = {
            "book": self._handle_orderbook,
            "orderbook_snapshot": self._handle_orderbook,
            "orderbook_delta": self._handle_orderbook,
            "trade": self._handle_trade,
            "ticker": self._handle_ticker,
            "ticker_v2": self._handle_ticker,
            "price": self._handle_price,
            "fill": self._handle_fill
        }
        logger.info("MessageProcessor initialized with pyee event emitter")

    def process_message(self, message: Dict[str, Any]) -> None:
        try:
            platform = message.get("_platform")
            subscription_id = message.get("_subscription_id")
            event_type = message.get("event_type", message.get("type", "unknown"))
            rate_limit = message.get("_rate_limit", 10)
            self.rate_limit_stats["total_messages"] += 1
            platform_key = f"{platform}:{subscription_id}"
            if platform_key not in self.rate_limit_stats["platform_stats"]:
                self.rate_limit_stats["platform_stats"][platform_key] = {
                    "messages": 0,
                    "rate_limited": 0,
                    "last_message": None
                }
            platform_stats = self.rate_limit_stats["platform_stats"][platform_key]
            platform_stats["messages"] += 1
            platform_stats["last_message"] = datetime.now().isoformat()
            logger.debug(f"Processing {platform}:{subscription_id} message type: {event_type}")
            if event_type in self.message_handlers:
                self.message_handlers[event_type](message)
            else:
                self._emit_raw_message(message)
            self._emit_to_pyee(message)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            logger.debug(f"Failed message: {message}")

    def _handle_orderbook(self, message: Dict[str, Any]) -> None:
        platform = message.get("_platform")
        subscription_id = message.get("_subscription_id")
        logger.info(f"\U0001F4CA ORDERBOOK: {platform}:{subscription_id}")
        self._emit_to_channel("orderbook", message)

    def _handle_trade(self, message: Dict[str, Any]) -> None:
        platform = message.get("_platform")
        subscription_id = message.get("_subscription_id")
        logger.info(f"\U0001F4B0 TRADE: {platform}:{subscription_id}")
        self._emit_to_channel("trade", message)

    def _handle_ticker(self, message: Dict[str, Any]) -> None:
        platform = message.get("_platform")
        subscription_id = message.get("_subscription_id")
        logger.info(f"\U0001F4C8 TICKER: {platform}:{subscription_id}")
        self._emit_to_channel("ticker", message)

    def _handle_price(self, message: Dict[str, Any]) -> None:
        platform = message.get("_platform")
        subscription_id = message.get("_subscription_id")
        logger.info(f"\U0001F4B2 PRICE: {platform}:{subscription_id}")
        self._emit_to_channel("price", message)

    def _handle_fill(self, message: Dict[str, Any]) -> None:
        platform = message.get("_platform")
        subscription_id = message.get("_subscription_id")
        logger.info(f"\u2705 FILL: {platform}:{subscription_id}")
        self._emit_to_channel("fill", message)

    def _emit_raw_message(self, message: Dict[str, Any]) -> None:
        platform = message.get("_platform", "unknown")
        subscription_id = message.get("_subscription_id", "unknown")
        event_type = message.get("event_type", message.get("type", "raw"))
        logger.info(f"\U0001F517 RAW: {platform}:{subscription_id} - {event_type}")
        self._emit_to_channel("raw", message)

    def _emit_to_channel(self, event_type: str, message: Dict[str, Any]) -> None:
        platform = message.get("_platform", "unknown")
        subscription_id = message.get("_subscription_id", "unknown")
        channel = f"{platform}.{subscription_id}.{event_type}"
        logger.debug(f"Emitting to channel '{channel}'")
        # For now, just log the emission

    def _emit_to_pyee(self, message: Dict[str, Any]) -> None:
        try:
            platform = message.get("_platform")
            subscription_id = message.get("_subscription_id")
            event_type = message.get("event_type", message.get("type", "unknown"))
            event_name = f"{platform}_{subscription_id}_{event_type}"
            self.event_emitter.emit(event_name, message)
            self.event_emitter.emit("message_processed", {
                "platform": platform,
                "subscription_id": subscription_id,
                "event_type": event_type,
                "timestamp": message.get("_timestamp"),
                "rate_limit": message.get("_rate_limit")
            })
        except Exception as e:
            logger.error(f"Error emitting to pyee: {e}")

    def add_message_handler(self, message_type: str, handler_func: callable) -> None:
        self.message_handlers[message_type] = handler_func
        logger.info(f"Added handler for message type: {message_type}")

    def get_event_emitter(self) -> AsyncIOEventEmitter:
        return self.event_emitter

    def get_rate_limit_stats(self) -> Dict[str, Any]:
        return self.rate_limit_stats.copy()

    def reset_rate_limit_stats(self) -> None:
        self.rate_limit_stats = {
            "total_messages": 0,
            "rate_limited_messages": 0,
            "platform_stats": {},
            "last_reset": datetime.now()
        }
        logger.info("Rate limit statistics reset")

import os
from typing import Optional
from config.paths import KALSHI_KEY_PATH
from .kalshi_environment import Environment
from cryptography.hazmat.primitives import serialization
import logging

logger = logging.getLogger(__name__)

class KalshiClientConfig:
    """Configuration class for Kalshi client."""
    def __init__(
        self,
        ticker: str,
        channel: str = "orderbook_delta",
        key_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        environment: Environment = Environment.DEMO,
        ping_interval: int = 30,
        reconnect_interval: int = 5,
        log_level: str = "INFO"
    ):
        self.ticker = ticker
        self.channel = channel
        self.key_id = key_id or os.getenv('PROD_KEYID')
        self.private_key_path = KALSHI_KEY_PATH
        self.environment = environment
        self.ping_interval = ping_interval
        self.reconnect_interval = reconnect_interval
        self.log_level = log_level
        self.private_key = self._load_private_key()

    def _get_default_key_path(self) -> str:
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(script_dir, '..', 'kalshi-starter-code-python', 'kalshi_key_file.txt')

    def _load_private_key(self):
        try:
            with open(self.private_key_path, "rb") as key_file:
                from cryptography.hazmat.primitives import serialization
                return serialization.load_pem_private_key(
                    key_file.read(),
                    password=None
                )
        except FileNotFoundError:
            logger.error(f"Private key file not found at {self.private_key_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading private key: {e}")
            raise

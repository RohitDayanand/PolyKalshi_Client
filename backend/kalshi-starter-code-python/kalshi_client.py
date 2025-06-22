import requests
import base64
import time
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from enum import Enum
import json
import asyncio
import websockets

from requests.exceptions import HTTPError
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature

class Environment(Enum):
    DEMO = "demo"
    PROD = "prod"

class KalshiBaseClient:
    """Base client class for interacting with the Kalshi API."""
    def __init__(
        self,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        environment: Environment = Environment.DEMO,
    ):
        self.key_id = key_id
        self.private_key = private_key
        self.environment = environment
        self.last_api_call = datetime.now()

        if self.environment == Environment.DEMO:
            self.HTTP_BASE_URL = "https://demo-api.kalshi.co"
            self.WS_BASE_URL = "wss://demo-api.kalshi.co"
        elif self.environment == Environment.PROD:
            self.HTTP_BASE_URL = "https://api.elections.kalshi.com"
            self.WS_BASE_URL = "wss://api.elections.kalshi.com"
        else:
            raise ValueError("Invalid environment")

    def request_headers(self, method: str, path: str) -> Dict[str, Any]:
        current_time_milliseconds = int(time.time() * 1000)
        timestamp_str = str(current_time_milliseconds)
        path_parts = path.split('?')
        msg_string = timestamp_str + method + path_parts[0]
        signature = self.sign_pss_text(msg_string)

        headers = {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_str,
        }
        return headers

    def sign_pss_text(self, text: str) -> str:
        message = text.encode('utf-8')
        try:
            signature = self.private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )
            return base64.b64encode(signature).decode('utf-8')
        except InvalidSignature as e:
            raise ValueError("RSA sign PSS failed") from e

class KalshiHttpClient(KalshiBaseClient):
    """Client for handling HTTP connections to the Kalshi API."""
    def __init__(
        self,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        environment: Environment = Environment.PROD,
    ):
        super().__init__(key_id, private_key, environment)
        self.host = self.HTTP_BASE_URL
        self.exchange_url = "/trade-api/v2/exchange"
        self.markets_url = "/trade-api/v2/markets"
        self.portfolio_url = "/trade-api/v2/portfolio"

    def rate_limit(self) -> None:
        THRESHOLD_IN_MILLISECONDS = 100
        now = datetime.now()
        threshold_in_microseconds = 1000 * THRESHOLD_IN_MILLISECONDS
        threshold_in_seconds = THRESHOLD_IN_MILLISECONDS / 1000
        if now - self.last_api_call < timedelta(microseconds=threshold_in_microseconds):
            time.sleep(threshold_in_seconds)
        self.last_api_call = datetime.now()

    def raise_if_bad_response(self, response: requests.Response) -> None:
        if response.status_code not in range(200, 299):
            response.raise_for_status()

    def get_balance(self) -> Dict[str, Any]:
        return self.get(self.portfolio_url + '/balance')

    def get_exchange_status(self) -> Dict[str, Any]:
        return self.get(self.exchange_url + "/status")

    def get_trades(
        self,
        ticker: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        max_ts: Optional[int] = None,
        min_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        params = {
            'ticker': ticker,
            'limit': limit,
            'cursor': cursor,
            'max_ts': max_ts,
            'min_ts': min_ts,
        }
        params = {k: v for k, v in params.items() if v is not None}
        return self.get(self.markets_url + '/trades', params=params)

    def get(self, path: str, params: Dict[str, Any] = {}) -> Any:
        self.rate_limit()
        response = requests.get(
            self.host + path,
            headers=self.request_headers("GET", path),
            params=params
        )
        self.raise_if_bad_response(response)
        return response.json()

class KalshiWebSocketClient(KalshiBaseClient):
    """Client for handling WebSocket connections to the Kalshi API."""
    def __init__(
        self,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        environment: Environment = Environment.PROD,
    ):
        super().__init__(key_id, private_key, environment)
        self.ws = None
        self.url_suffix = "/trade-api/ws/v2"
        self.message_id = 1
        self.is_connected = False
        self.subscription_confirmed = False
        self.last_message_time = None
        self.last_pong_time = None
        self.should_reconnect = True
        self.subscriptions = set()  # Track (channel, market_ticker)
        self.subscribe_events = {}  # Map (channel, market_ticker) to asyncio.Event
        from orderbook_processor import OrderbookProcessor
        self.orderbook_processor = OrderbookProcessor()

    async def connect(self, channel, market_ticker):
        """Establishes a WebSocket connection using authentication."""
        max_retries = 3
        retries = 0
        while self.should_reconnect and retries < max_retries:
            try:
                if self.is_connected:
                    print("Already connected to WebSocket")
                    return

                host = self.WS_BASE_URL + self.url_suffix
                print("Connection url", host)
                
                auth_headers = self.request_headers("GET", self.url_suffix)

                print("Auth_headers", auth_headers)
                
                async with websockets.connect(
                    host, 
                    additional_headers=auth_headers
                ) as websocket:
                    self.ws = websocket
                    self.is_connected = True
                    self.last_message_time = time.time()
                    self.last_pong_time = time.time()
                    print("WebSocket connection established successfully")
                    await self.on_open(channel, market_ticker)
                    await self.handler()
                    # If handler exits normally, break out of retry loop
                    break
            except websockets.ConnectionClosed as e:
                print(f"Connection closed: {e.code} {e.reason}")
                self.is_connected = False
                retries += 1
                if retries < max_retries:
                    print(f"Reconnecting in 5 seconds... (attempt {retries+1} of {max_retries})")
                    await asyncio.sleep(5)
            except Exception as e:
                print(f"Connection error: {e}")
                self.is_connected = False
                retries += 1
                if retries < max_retries:
                    print(f"Reconnecting in 5 seconds... (attempt {retries+1} of {max_retries})")
                    await asyncio.sleep(5)
        if retries >= max_retries:
            print("Max reconnection attempts reached. Stopping further attempts.")

    async def on_open(self, channel, market_ticker):
        print("WebSocket connection opened.")
        await self.subscribe(channel, market_ticker)

    async def subscribe(self, channel, market_ticker):
        subscribe_param = {
            "id": self.message_id,
            "cmd": "subscribe",
            "params": {
                "channels": channel,
                "market_tickers": market_ticker
            }
        }
        print(f"Sending subscription message: {subscribe_param}")
        await self.ws.send(json.dumps(subscribe_param))
        self.message_id += 1

    async def handler(self):
        """Handle incoming messages."""
        try:
            async for message in self.ws:
                # Log EVERY message received from Kalshi
                print("\n" + "="*50)
                print(f"RECEIVED MESSAGE at {datetime.now().isoformat()}")
                print(f"Message: {message}")
                print("="*50 + "\n")
                self.last_message_time = time.time()
                try:
                    data = json.loads(message)
                    if data.get('type') == 'ping':
                        pong_message = {"type": "pong"}
                        await self.ws.send(json.dumps(pong_message))
                        print("SENT Kalshi PONG in response to ping.")
                        self.last_pong_time = time.time()
                        continue
                except json.JSONDecodeError:
                    pass
                self.last_pong_time = time.time()
                await self.on_message(message)
                time_since_last_pong = time.time() - self.last_pong_time
                if time_since_last_pong > 10:
                    print(f"CONNECTION DROPPED: No PONG received for {time_since_last_pong:.1f} seconds")
                    print("Connection appears to be dead. Initiating reconnection...")
                    await self.disconnect()
                    return
        except websockets.ConnectionClosed as e:
            print(f"Connection lost: {e.code} {e.reason}")
            self.is_connected = False
        except Exception as e:
            print(f"Handler error: {e}")
            self.is_connected = False

    async def on_message(self, message):
        """Callback for handling incoming messages."""
        try:
            data = json.loads(message)
            msg_type = data.get('type', '')
            
            if msg_type == 'subscribed':
                print(f"Subscription confirmed: {data}")
                self.subscription_confirmed = True
            elif msg_type == 'orderbook_snapshot':
                await self.orderbook_processor.process_snapshot(data)
            elif msg_type == 'orderbook_delta':
                await self.orderbook_processor.process_delta(data)
            elif msg_type == 'trade':
                await self.orderbook_processor.process_trade(data)
            elif msg_type == 'fill':
                await self.orderbook_processor.process_fill(data)
            elif msg_type == 'ticker_v2':
                await self.orderbook_processor.process_ticker_v2(data)
            elif msg_type == 'error':
                print(f"Server error: {data.get('msg', 'Unknown error')}")
            elif msg_type == 'unsubscribed':
                print(f"Unsubscribed: {data}")
                self.subscription_confirmed = False
            
        except json.JSONDecodeError:
            print(f"Received non-JSON message: {message}")
        except Exception as e:
            print(f"Error processing message: {e}")
            print(f"Failed message content: {message}")

    async def on_error(self, error):
        """Callback for handling errors."""
        print("WebSocket error:", error)

    async def on_close(self, close_status_code, close_msg):
        """Callback when WebSocket connection is closed."""
        print("WebSocket connection closed with code:", close_status_code, "and message:", close_msg)
        self.is_connected = False
        self.subscription_confirmed = False

    async def disconnect(self):
        """Explicitly disconnect from the WebSocket."""
        self.should_reconnect = False
        if self.ws:
            await self.ws.close()
            self.ws = None
            self.is_connected = False
            self.subscription_confirmed = False
            print("WebSocket disconnected") 
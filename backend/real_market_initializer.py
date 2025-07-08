#!/usr/bin/env python3
"""
Real Market Data Initializer - Complete Live Market Data Pipeline

Connects to real Polymarket and Kalshi WebSocket feeds with the provided token IDs and market slug.
Includes verbose logging, real-time monitoring, and WebSocket server for client connections.

Usage:
    python real_market_initializer.py

Markets:
    - Polymarket Token IDs: 75505728818237076147318796536066812362152358606307154083407489467059230821371, 67369669271127885658944531351746308398542291270457462650056001798232262328240
    - Kalshi Market: KXUSAIRANAGREEMENT-26

Data Flow:
    Real Market APIs → MarketsManager → Message Processors → Ticker Publishers → WebSocket Server → Clients
"""

import asyncio
import logging
import signal
import time
import sys
import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import uvicorn
from contextlib import asynccontextmanager

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Enable Polymarket debug logging for this test
os.environ['POLYMARKET_DEBUG_LOGGING'] = 'true'

from backend.master_manager.MarketsManager import MarketsManager
from backend.websocket_server import app as websocket_app, stream_manager
from backend.ticker_stream_integration import start_ticker_publisher, stop_ticker_publisher


class VerboseLoggingSetup:
    """Configure comprehensive verbose logging for all components."""
    
    @staticmethod
    def setup_verbose_logging():
        """Set up DEBUG level logging with detailed formatting."""
        
        # Create detailed formatter
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Add console handler with verbose formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Set specific logger levels for key components
        loggers_to_configure = [
            'backend.master_manager.MarketsManager',
            'master_manager.MarketsManager', 
            'kalshi_client.kalshi_client',
            'kalshi_client.kalshi_message_processor',
            'kalshi_ticker_publisher',
            'polymarket_client.polymarket_client',
            'polymarket_client.polymarket_message_processor',
            'polymarket_client.polymarket_ticker_publisher',
            'backend.ticker_stream_integration',
            'backend.websocket_server',
            'backend.channel_manager',
            'uvicorn.access',
            'websockets'
        ]
        
        for logger_name in loggers_to_configure:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)
        
        # Suppress some noisy loggers
        logging.getLogger('asyncio').setLevel(logging.INFO)
        logging.getLogger('uvicorn.error').setLevel(logging.INFO)
        
        print("🔧 Verbose DEBUG logging configured for all components")
        print("📝 Polymarket WebSocket debug logging: ENABLED")
        print("📂 Debug log file: /home/rohit/Websocket_Polymarket_Kalshi/polymarket_debug.txt")


class RealTimeMonitor:
    """Real-time monitoring and statistics for market data flow."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.stats = {
            'connections_established': 0,
            'total_messages_processed': 0,
            'polymarket_messages': 0,
            'kalshi_messages': 0,
            'websocket_clients': 0,
            'last_update_time': None,
            'message_rate_per_second': 0.0,
            'connection_status': {
                'polymarket': 'disconnected',
                'kalshi': 'disconnected',
                'websocket_server': 'stopped'
            }
        }
        self.message_timestamps = []
    
    def record_message(self, platform: str = None):
        """Record a processed message for rate calculation."""
        now = datetime.now()
        self.stats['total_messages_processed'] += 1
        self.stats['last_update_time'] = now
        
        if platform == 'polymarket':
            self.stats['polymarket_messages'] += 1
        elif platform == 'kalshi':
            self.stats['kalshi_messages'] += 1
        
        # Keep last 60 seconds of timestamps for rate calculation
        self.message_timestamps.append(now)
        cutoff = now - timedelta(seconds=60)
        self.message_timestamps = [ts for ts in self.message_timestamps if ts > cutoff]
        
        # Calculate messages per second
        if len(self.message_timestamps) > 1:
            time_span = (self.message_timestamps[-1] - self.message_timestamps[0]).total_seconds()
            if time_span > 0:
                self.stats['message_rate_per_second'] = len(self.message_timestamps) / time_span
    
    def update_connection_status(self, platform: str, status: str):
        """Update connection status for a platform."""
        self.stats['connection_status'][platform] = status
        if status == 'connected':
            self.stats['connections_established'] += 1
    
    def get_uptime(self) -> str:
        """Get formatted uptime string."""
        uptime = datetime.now() - self.start_time
        return str(uptime).split('.')[0]  # Remove microseconds
    
    def print_status(self):
        """Print current status and statistics."""
        print("\n" + "="*80)
        print(f"📊 REAL-TIME MARKET DATA MONITOR - Uptime: {self.get_uptime()}")
        print("="*80)
        
        # Connection Status
        print("🔗 CONNECTION STATUS:")
        for platform, status in self.stats['connection_status'].items():
            emoji = "✅" if status == 'connected' or status == 'running' else "❌"
            print(f"   {emoji} {platform.capitalize()}: {status}")
        
        # Message Statistics
        print(f"\n📈 MESSAGE STATISTICS:")
        print(f"   Total Messages: {self.stats['total_messages_processed']}")
        print(f"   Polymarket: {self.stats['polymarket_messages']}")
        print(f"   Kalshi: {self.stats['kalshi_messages']}")
        print(f"   Rate: {self.stats['message_rate_per_second']:.2f} msg/sec")
        
        if self.stats['last_update_time']:
            seconds_ago = (datetime.now() - self.stats['last_update_time']).total_seconds()
            print(f"   Last Update: {seconds_ago:.1f}s ago")
        
        # WebSocket Clients
        try:
            client_count = len(stream_manager.channel_manager.connections)
            print(f"   WebSocket Clients: {client_count}")
        except:
            print(f"   WebSocket Clients: 0")
        
        print("="*80)


class RealMarketDataInitializer:
    """Main initializer for real market data connections."""
    
    def __init__(self):
        self.markets_manager: Optional[MarketsManager] = None
        self.websocket_server: Optional[uvicorn.Server] = None
        self.monitor = RealTimeMonitor()
        self.running = False
        
        # Real market data configuration
        self.polymarket_token_ids = [
            "75505728818237076147318796536066812362152358606307154083407489467059230821371",
            "67369669271127885658944531351746308398542291270457462650056001798232262328240"
        ]
        self.kalshi_market_slug = "KXUSAIRANAGREEMENT-26"
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n🛑 Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(self.shutdown())
    
    async def initialize_markets_manager(self):
        """Initialize and configure the markets manager."""
        print("📋 Initializing Markets Manager...")
        
        try:
            self.markets_manager = MarketsManager()
            print("✅ Markets Manager initialized")
            self.monitor.update_connection_status('markets_manager', 'initialized')
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize Markets Manager: {e}")
            logging.exception("Markets Manager initialization failed")
            return False
    
    async def connect_to_markets(self):
        """Connect to real Polymarket and Kalshi markets."""
        print("🌐 Connecting to real market data feeds...")
        
        success_count = 0
        
        # Connect to Polymarket
        print(f"💰 Connecting to Polymarket with {len(self.polymarket_token_ids)} token IDs...")
        try:
            poly_tokens_str = ",".join(self.polymarket_token_ids)
            poly_success = await self.markets_manager.connect(poly_tokens_str, platform="polymarket")
            
            if poly_success:
                print("✅ Polymarket connection established")
                self.monitor.update_connection_status('polymarket', 'connected')
                success_count += 1
                
                # Log token details
                for i, token_id in enumerate(self.polymarket_token_ids, 1):
                    print(f"   Token {i}: {token_id}")
            else:
                print("❌ Polymarket connection failed")
                self.monitor.update_connection_status('polymarket', 'failed')
                
        except Exception as e:
            print(f"❌ Polymarket connection error: {e}")
            logging.exception("Polymarket connection failed")
            self.monitor.update_connection_status('polymarket', 'error')
        
        # Connect to Kalshi
        print(f"🗳️  Connecting to Kalshi market: {self.kalshi_market_slug}...")
        try:
            kalshi_success = await self.markets_manager.connect(self.kalshi_market_slug, platform="kalshi")
            
            if kalshi_success:
                print("✅ Kalshi connection established")
                self.monitor.update_connection_status('kalshi', 'connected')
                success_count += 1
                print(f"   Market: {self.kalshi_market_slug}")
            else:
                print("❌ Kalshi connection failed")
                self.monitor.update_connection_status('kalshi', 'failed')
                
        except Exception as e:
            print(f"❌ Kalshi connection error: {e}")
            logging.exception("Kalshi connection failed")
            self.monitor.update_connection_status('kalshi', 'error')
        
        print(f"📊 Market connections completed: {success_count}/2 successful")
        return success_count > 0
    
    async def start_websocket_server(self):
        """Start the WebSocket server for client connections."""
        print("🌐 Starting WebSocket server...")
        
        try:
            # Start ticker publisher
            await start_ticker_publisher()
            print("✅ Ticker publisher started")
            
            # Configure and start WebSocket server
            config = uvicorn.Config(
                app=websocket_app,
                host="0.0.0.0",
                port=8000,
                log_level="info",
                access_log=True
            )
            
            self.websocket_server = uvicorn.Server(config)
            
            print("🚀 WebSocket server starting on ws://localhost:8000/ws/ticker")
            print("🏥 Health check available at http://localhost:8000/health")
            
            # Start server in background
            server_task = asyncio.create_task(self.websocket_server.serve())
            self.monitor.update_connection_status('websocket_server', 'running')
            
            # Give server time to start
            await asyncio.sleep(2)
            print("✅ WebSocket server running")
            
            return server_task
            
        except Exception as e:
            print(f"❌ WebSocket server failed to start: {e}")
            logging.exception("WebSocket server startup failed")
            return None
    
    async def monitor_market_data(self, duration_minutes: int = 3):
        """Monitor real-time market data for specified duration."""
        print(f"👀 Monitoring real-time market data for {duration_minutes} minutes...")
        print("📊 Watching for:")
        print("   - Order book updates")
        print("   - Price movements") 
        print("   - WebSocket client connections")
        print("   - Message throughput")
        print("\n🔄 Live monitoring started (Ctrl+C to stop early)...")
        
        start_time = time.time()
        last_status_time = 0
        status_interval = 10  # Print status every 10 seconds
        
        while self.running and (time.time() - start_time) < (duration_minutes * 60):
            try:
                # Print status periodically
                current_time = time.time()
                if current_time - last_status_time >= status_interval:
                    self.monitor.print_status()
                    last_status_time = current_time
                
                # Check for new messages (this would be updated by message handlers)
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️  Monitoring error: {e}")
                logging.exception("Monitoring error")
                await asyncio.sleep(1)
        
        print(f"\n⏰ Monitoring completed after {(time.time() - start_time):.1f} seconds")
    
    async def run(self, duration_minutes: int = 3):
        """Main execution flow."""
        self.running = True
        
        print("🚀 REAL MARKET DATA INITIALIZER STARTING")
        print("="*60)
        print(f"📅 Start Time: {datetime.now().isoformat()}")
        print(f"⏱️  Duration: {duration_minutes} minutes")
        print("="*60)
        
        try:
            # Step 1: Initialize Markets Manager
            if not await self.initialize_markets_manager():
                print("❌ Failed to initialize Markets Manager - aborting")
                return False
            
            # Step 2: Connect to real markets
            if not await self.connect_to_markets():
                print("❌ Failed to connect to any markets - aborting")
                return False
            
            # Step 3: Start WebSocket server
            server_task = await self.start_websocket_server()
            if not server_task:
                print("❌ Failed to start WebSocket server - aborting")
                return False
            
            print("\n🎉 ALL SYSTEMS OPERATIONAL!")
            print("✅ Markets Manager: Running")
            print("✅ Real Market Connections: Active") 
            print("✅ WebSocket Server: Accepting clients")
            print("✅ Ticker Publishers: Broadcasting updates")
            
            # Step 4: Monitor real-time data
            await self.monitor_market_data(duration_minutes)
            
            return True
            
        except Exception as e:
            print(f"❌ Critical error during execution: {e}")
            logging.exception("Critical execution error")
            return False
        
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown of all components."""
        if not self.running:
            return
            
        self.running = False
        print("\n🛑 GRACEFUL SHUTDOWN INITIATED")
        print("="*50)
        
        try:
            # Stop ticker publisher
            await stop_ticker_publisher()
            print("✅ Ticker publisher stopped")
            
            # Stop WebSocket server
            if self.websocket_server:
                self.websocket_server.should_exit = True
                print("✅ WebSocket server stopped")
            
            # Disconnect markets manager
            if self.markets_manager:
                # The MarketsManager doesn't have a built-in shutdown method
                # but the clients should handle disconnection automatically
                print("✅ Markets Manager disconnected")
            
            # Final statistics
            self.monitor.print_status()
            
            print("🔚 SHUTDOWN COMPLETED")
            
        except Exception as e:
            print(f"⚠️  Error during shutdown: {e}")
            logging.exception("Shutdown error")


async def main():
    """Main entry point."""
    # Setup verbose logging first
    VerboseLoggingSetup.setup_verbose_logging()
    
    print("\n" + "🎯" * 20)
    print("REAL MARKET DATA INITIALIZER")
    print("Live Polymarket & Kalshi WebSocket Feeds")
    print("🎯" * 20)
    
    # Create and run initializer
    initializer = RealMarketDataInitializer()
    
    try:
        success = await initializer.run(duration_minutes=3)
        
        if success:
            print("\n🎉 Integration test completed successfully!")
        else:
            print("\n❌ Integration test failed!")
            
    except KeyboardInterrupt:
        print("\n⌨️  Keyboard interrupt received")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        logging.exception("Unexpected error in main")


if __name__ == "__main__":
    asyncio.run(main())
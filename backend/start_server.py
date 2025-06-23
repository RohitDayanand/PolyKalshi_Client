#!/usr/bin/env python3
"""
Startup script for the WebSocket ticker streaming server
"""
import asyncio
import sys
import signal
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.websocket_server import app
from backend.ticker_stream_integration import start_ticker_publisher, stop_ticker_publisher
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServerManager:
    """Manages the WebSocket server lifecycle"""
    
    def __init__(self):
        self.server = None
        self.running = False
    
    async def start_server(self, host="0.0.0.0", port=8000):
        """Start the WebSocket server"""
        logger.info("Starting ticker stream publisher...")
        start_ticker_publisher()
        
        logger.info(f"Starting WebSocket server on {host}:{port}")
        
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        
        self.server = uvicorn.Server(config)
        self.running = True
        
        try:
            await self.server.serve()
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.running = False
    
    async def stop_server(self):
        """Stop the WebSocket server"""
        if self.server and self.running:
            logger.info("Stopping WebSocket server...")
            self.server.should_exit = True
            stop_ticker_publisher()
            self.running = False

# Global server manager
server_manager = ServerManager()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    asyncio.create_task(server_manager.stop_server())

async def main():
    """Main entry point"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=== WebSocket Ticker Streaming Server ===")
    logger.info("Server provides real-time ticker updates for Polymarket and Kalshi markets")
    logger.info("WebSocket endpoint: ws://localhost:8000/ws/ticker")
    logger.info("Health check: http://localhost:8000/health")
    logger.info("Press Ctrl+C to stop the server")
    
    try:
        await server_manager.start_server()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await server_manager.stop_server()
        logger.info("Server stopped")

if __name__ == "__main__":
    asyncio.run(main())
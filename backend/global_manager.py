"""
Global singleton instances for WebSocket management
"""
from backend.channel_manager import ChannelManager

# Single global instance shared across all modules
global_channel_manager = ChannelManager()
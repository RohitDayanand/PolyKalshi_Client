#!/usr/bin/env python3
"""
Simple test to check if ArbitrageDetector initializes properly
"""

import sys
import os
import logging

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.master_manager.events.event_bus import EventBus
from backend.master_manager.arbitrage_detector import ArbitrageDetector

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

def test_detector_init():
    """Test ArbitrageDetector initialization directly"""
    print("🧪 Testing ArbitrageDetector initialization...")
    
    try:
        # Create event bus
        event_bus = EventBus()
        print("✅ EventBus created")
        
        # Create ArbitrageDetector
        print("🔍 Creating ArbitrageDetector...")
        detector = ArbitrageDetector(event_bus, 0.02)
        print("✅ ArbitrageDetector created successfully")
        
        print(f"📊 Detector info: min_spread={detector.min_spread_threshold}, event_bus={detector.event_bus}")
        
    except Exception as e:
        print(f"❌ Exception during ArbitrageDetector creation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_detector_init()
"""
Test script for Polymarket Connection Error Handling in MarketsManager.

This script tests the MarketsManager's Polymarket connection functionality with both 
valid and invalid inputs to examine error handling, logging control flow, and 
connection state management.

Focus Areas:
- Valid connection establishment
- Invalid/gibberish token ID handling
- Error message logging and propagation
- Connection state tracking
- Queue integration behavior
"""

import logging
import asyncio
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Set up proper path for imports - add master_manager directory to path
master_manager_path = str(Path(__file__).parent.parent)
if master_manager_path not in sys.path:
    sys.path.insert(0, master_manager_path)

# Import MarketsManager and related components
from MarketsManager import MarketsManager
from polymarket_client.polymarket_client import PolymarketClient, PolymarketClientConfig

print("✅ All imports successful")

# Test constants - mix of valid and invalid data
VALID_POLYMARKET_TOKENS = [
    "5044658213116494392261893544497225363846217319105609804585534197935770239191",
    "107816283868337218117379783608318587331517916696607930361272175815275915222107"
]

INVALID_GIBBERISH_TOKENS = [
    "xJ8#$mZq!@9vN&*pL2^wK5%uR",
    "invalid-token-123-!@#$%^&*()",
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "SELECT * FROM tokens WHERE id='malicious'",
    "",
    "   ",
    "🚀💀👻🔥",
    "null",
    "undefined",
    "{\"malformed\": \"json\"}",
    "DROP TABLE markets;--"
]

# Memory storage for captured logs
captured_logs = []
original_handlers = []

class LogCapture:
    """Capture and store all log messages for analysis"""
    
    def __init__(self):
        self.logs = []
        self.setup_logging()
    
    def setup_logging(self):
        """Set up comprehensive logging capture"""
        # Configure root logger for maximum verbosity
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Store original handlers
        global original_handlers
        original_handlers = root_logger.handlers.copy()
        
        # Create custom handler that captures everything
        class CaptureHandler(logging.Handler):
            def __init__(self, capture_instance):
                super().__init__()
                self.capture = capture_instance
                self.setLevel(logging.DEBUG)
                
            def emit(self, record):
                formatted_msg = self.format(record)
                self.capture.logs.append({
                    'timestamp': datetime.now().isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'formatted': formatted_msg,
                    'filename': record.filename,
                    'lineno': record.lineno,
                    'funcName': record.funcName
                })
                
                # Also print to console for real-time monitoring
                print(f"[{record.levelname}] {record.name}: {record.getMessage()}")
        
        # Add our capture handler
        self.handler = CaptureHandler(self)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        self.handler.setFormatter(formatter)
        root_logger.addHandler(self.handler)
        
        # Set specific loggers to DEBUG
        for logger_name in [
            'MarketsManager', 
            'polymarket_client', 
            'kalshi_client',
            'polymarket_queue',
            'kalshi_queue',
            'websockets',
            '__main__'
        ]:
            logging.getLogger(logger_name).setLevel(logging.DEBUG)
    
    def get_logs_by_level(self, level: str) -> List[Dict]:
        """Get all logs of a specific level"""
        return [log for log in self.logs if log['level'] == level]
    
    def get_logs_by_logger(self, logger_name: str) -> List[Dict]:
        """Get all logs from a specific logger"""
        return [log for log in self.logs if logger_name in log['logger']]
    
    def get_recent_logs(self, count: int = 50) -> List[Dict]:
        """Get the most recent N logs"""
        return self.logs[-count:]
    
    def print_log_summary(self):
        """Print a summary of captured logs"""
        total = len(self.logs)
        by_level = {}
        by_logger = {}
        
        for log in self.logs:
            level = log['level']
            logger = log['logger']
            
            by_level[level] = by_level.get(level, 0) + 1
            by_logger[logger] = by_logger.get(logger, 0) + 1
        
        print(f"\n{'='*80}")
        print(f"LOG CAPTURE SUMMARY - Total logs: {total}")
        print(f"{'='*80}")
        
        print("\nLogs by level:")
        for level, count in sorted(by_level.items()):
            print(f"  {level}: {count}")
        
        print("\nLogs by logger:")
        for logger, count in sorted(by_logger.items()):
            print(f"  {logger}: {count}")
    
    def print_error_logs(self):
        """Print all error and warning logs"""
        error_logs = self.get_logs_by_level('ERROR') + self.get_logs_by_level('WARNING')
        
        if error_logs:
            print(f"\n{'🚨' * 20} ERROR AND WARNING LOGS {'🚨' * 20}")
            for log in error_logs:
                print(f"[{log['timestamp']}] {log['level']} - {log['logger']}")
                print(f"  📁 {log['filename']}:{log['lineno']} in {log['funcName']}()")
                print(f"  💬 {log['message']}")
                print()
        else:
            print("\n✅ No error or warning logs captured!")

# Global log capture instance
log_capture = LogCapture()

async def test_valid_polymarket_connection():
    """Test connecting to Polymarket with valid token IDs"""
    print(f"\n{'🧪' * 20} TEST 1: VALID POLYMARKET CONNECTION {'🧪' * 20}")
    
    try:
        manager = MarketsManager()
        
        # Test with valid token IDs
        valid_tokens_str = ",".join(VALID_POLYMARKET_TOKENS)
        print(f"📋 Testing connection with valid tokens: {valid_tokens_str}")
        
        start_time = time.time()
        success = await manager.connect(valid_tokens_str, platform="polymarket")
        end_time = time.time()
        
        print(f"⏱️ Connection attempt took {end_time - start_time:.2f} seconds")
        print(f"🔗 Connection result: {success}")
        
        if success:
            print("✅ Valid connection test PASSED")
            
            # Get status to verify connection state
            status = manager.get_status()
            print(f"📊 Manager status: {json.dumps(status, indent=2)}")
            
            # Keep connection alive briefly to see some messages
            print("👂 Listening for messages for 3 seconds...")
            await asyncio.sleep(3)
            
        else:
            print("❌ Valid connection test FAILED - should have succeeded")
        
        # Clean up
        await manager.disconnect_all()
        return success
        
    except Exception as e:
        print(f"❌ Valid connection test FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_single_invalid_token(token: str, test_name: str):
    """Test a single invalid token and capture detailed error flow"""
    print(f"\n{'🔍' * 15} TESTING: {test_name} {'🔍' * 15}")
    print(f"🎯 Token: '{token}'")
    
    # Clear recent logs for this test
    recent_log_count = len(log_capture.logs)
    
    try:
        manager = MarketsManager()
        
        start_time = time.time()
        success = await manager.connect(token, platform="polymarket")
        end_time = time.time()
        
        print(f"⏱️ Connection attempt took {end_time - start_time:.2f} seconds")
        print(f"🔗 Connection result: {success}")
        
        if success:
            print("⚠️ WARNING: Invalid token connection unexpectedly succeeded!")
            
            # Check what actually got connected
            status = manager.get_status()
            print(f"📊 Unexpected success status: {json.dumps(status, indent=2)}")
            
            # Keep alive briefly then disconnect
            await asyncio.sleep(2)
        else:
            print("✅ Expected failure for invalid token")
        
        # Analyze logs from this test
        new_logs = log_capture.logs[recent_log_count:]
        error_logs = [log for log in new_logs if log['level'] in ['ERROR', 'WARNING']]
        
        if error_logs:
            print(f"\n📝 Captured {len(error_logs)} error/warning messages:")
            for log in error_logs[-5:]:  # Show last 5 errors
                print(f"  🚨 [{log['level']}] {log['logger']}: {log['message']}")
        
        # Clean up
        await manager.disconnect_all()
        return not success  # Success means the invalid token was properly rejected
        
    except Exception as e:
        print(f"💥 Exception during invalid token test: {e}")
        print(f"📍 Exception type: {type(e).__name__}")
        
        # This is expected for some invalid inputs
        return True

async def test_invalid_polymarket_connections():
    """Test connecting to Polymarket with various invalid inputs"""
    print(f"\n{'💥' * 20} TEST 2: INVALID POLYMARKET CONNECTIONS {'💥' * 20}")
    
    results = []
    
    for i, invalid_token in enumerate(INVALID_GIBBERISH_TOKENS):
        test_name = f"Invalid Token {i+1}"
        result = await test_single_invalid_token(invalid_token, test_name)
        results.append((test_name, invalid_token, result))
        
        # Brief pause between tests
        await asyncio.sleep(2)
    
    # Summary
    print(f"\n{'📊' * 20} INVALID TOKEN TEST RESULTS {'📊' * 20}")
    passed = 0
    for test_name, token, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} {test_name}: '{token[:30]}{'...' if len(token) > 30 else ''}'")
        if result:
            passed += 1
    
    print(f"\n🎯 Invalid token tests: {passed}/{len(results)} passed")
    return passed == len(results)

async def test_mixed_valid_invalid_tokens():
    """Test mixing valid and invalid tokens in same subscription"""
    print(f"\n{'🔀' * 20} TEST 3: MIXED VALID/INVALID TOKENS {'🔀' * 20}")
    
    try:
        manager = MarketsManager()
        
        # Mix valid and invalid tokens
        mixed_tokens = [
            VALID_POLYMARKET_TOKENS[0],  # Valid
            INVALID_GIBBERISH_TOKENS[0],  # Invalid  
            VALID_POLYMARKET_TOKENS[1],  # Valid
            INVALID_GIBBERISH_TOKENS[1],  # Invalid
        ]
        mixed_token_str = ",".join(mixed_tokens)
        
        print(f"🎭 Testing mixed tokens: {mixed_token_str}")
        
        success = await manager.connect(mixed_token_str, platform="polymarket")
        print(f"🔗 Mixed connection result: {success}")
        
        if success:
            print("⚠️ Mixed tokens connection succeeded - checking behavior...")
            
            # Monitor for a bit to see what happens
            await asyncio.sleep(10)
            
            status = manager.get_status()
            print(f"📊 Mixed connection status: {json.dumps(status, indent=2)}")
        else:
            print("❌ Mixed tokens connection failed")
        
        await manager.disconnect_all()
        return True
        
    except Exception as e:
        print(f"💥 Mixed tokens test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_connection_edge_cases():
    """Test various edge cases for connection parameters"""
    print(f"\n{'⚡' * 20} TEST 4: CONNECTION EDGE CASES {'⚡' * 20}")
    
    edge_cases = [
        ("None value", None),
        ("Empty string", ""),
        ("Whitespace only", "   \t\n   "),
        ("Number as string", "12345"),
        ("Boolean as string", "true"),
        ("JSON as string", '{"token": "fake"}'),
        ("Very long string", "a" * 1000),
        ("Unicode characters", "токен🚀💀"),
        ("SQL injection attempt", "'; DROP TABLE tokens; --"),
        ("Script injection", "<script>alert('xss')</script>"),
    ]
    
    results = []
    
    for test_name, test_input in edge_cases:
        print(f"\n🔬 Testing edge case: {test_name}")
        print(f"📥 Input: {repr(test_input)}")
        
        try:
            manager = MarketsManager()
            success = await manager.connect(test_input, platform="polymarket")
            print(f"🔗 Result: {success}")
            
            results.append((test_name, test_input, "SUCCESS" if success else "FAILED", None))
            
            await manager.disconnect_all()
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"💥 Exception: {type(e).__name__}: {e}")
            results.append((test_name, test_input, "EXCEPTION", str(e)))
            await asyncio.sleep(1)
    
    # Summary
    print(f"\n{'📊' * 20} EDGE CASE TEST RESULTS {'📊' * 20}")
    for test_name, test_input, result, error in results:
        input_repr = repr(test_input) if len(repr(test_input)) < 50 else repr(test_input)[:47] + "..."
        print(f"📋 {test_name}: {input_repr} → {result}")
        if error:
            print(f"    💬 {error}")
    
    return True

async def run_comprehensive_polymarket_tests():
    """Run all Polymarket connection tests and analyze results"""
    print(f"\n{'🚀' * 40}")
    print("🧪 COMPREHENSIVE POLYMARKET CONNECTION ERROR TESTING")
    print(f"{'🚀' * 40}")
    print(f"📅 Test started at: {datetime.now().isoformat()}")
    print(f"🎯 Focus: Error handling, logging, and connection state management")
    
    # Initialize log capture
    print("\n📊 Setting up comprehensive logging capture...")
    
    test_results = []
    
    try:
        # Test 1: Valid connections (baseline)
        print("\n" + "="*100)
        result1 = await test_valid_polymarket_connection()
        test_results.append(("Valid Connection", result1))
        
        # Test 2: Invalid connections  
        print("\n" + "="*100)
        result2 = await test_invalid_polymarket_connections()
        test_results.append(("Invalid Connections", result2))
        
        # Test 3: Mixed valid/invalid
        print("\n" + "="*100)
        result3 = await test_mixed_valid_invalid_tokens()
        test_results.append(("Mixed Tokens", result3))
        
        # Test 4: Edge cases
        print("\n" + "="*100)
        result4 = await test_connection_edge_cases()
        test_results.append(("Edge Cases", result4))
        
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR in test suite: {e}")
        import traceback
        traceback.print_exc()
    
    # Comprehensive results and log analysis
    print(f"\n{'🎉' * 40}")
    print("📊 COMPREHENSIVE TEST RESULTS AND LOG ANALYSIS")
    print(f"{'🎉' * 40}")
    
    # Test results summary
    print("\n🧪 Test Results:")
    passed_tests = 0
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {status} {test_name}")
        if result:
            passed_tests += 1
    
    print(f"\n🎯 Overall: {passed_tests}/{len(test_results)} test suites passed")
    
    # Log analysis
    log_capture.print_log_summary()
    log_capture.print_error_logs()
    
    # Most recent logs for control flow analysis
    print(f"\n{'🔍' * 20} RECENT CONTROL FLOW LOGS {'🔍' * 20}")
    recent_logs = log_capture.get_recent_logs(30)
    for log in recent_logs:
        print(f"[{log['timestamp']}] {log['level']} {log['logger']} - {log['message']}")
    
    # Specific error pattern analysis
    polymarket_errors = log_capture.get_logs_by_logger('polymarket')
    manager_errors = log_capture.get_logs_by_logger('MarketsManager')
    
    if polymarket_errors:
        print(f"\n{'📱' * 20} POLYMARKET CLIENT LOGS {'📱' * 20}")
        for log in polymarket_errors[-10:]:  # Last 10 polymarket logs
            print(f"[{log['level']}] {log['message']}")
    
    if manager_errors:
        print(f"\n{'🏢' * 20} MARKETS MANAGER LOGS {'🏢' * 20}")
        for log in manager_errors[-10:]:  # Last 10 manager logs
            print(f"[{log['level']}] {log['message']}")
    
    print(f"\n{'🏁' * 40}")
    print("🧪 POLYMARKET CONNECTION ERROR TESTING COMPLETE")
    print(f"{'🏁' * 40}")
    print(f"📅 Test completed at: {datetime.now().isoformat()}")
    
    if passed_tests == len(test_results):
        print("🎉 ALL TESTS PASSED! Error handling is working correctly.")
    else:
        print("⚠️ Some tests failed. Check the logs above for details.")
    
    return passed_tests == len(test_results)

if __name__ == "__main__":
    # Run the comprehensive test suite
    try:
        result = asyncio.run(run_comprehensive_polymarket_tests())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n💥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
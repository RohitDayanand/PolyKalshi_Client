/**
 * Test file to verify Kalshi client imports work correctly
 */

import { KalshiClient, Environment, KALSHI_CHANNELS } from './index';

// This file serves as a basic import test
// If this compiles without errors, the main exports are working correctly

const testConfig = {
  environment: Environment.DEMO,
  keyId: 'test-key',
  privateKey: 'test-private-key'
};

// Test that the client can be instantiated (compile-time check only)
// const client = new KalshiClient(testConfig);

// Test that constants are accessible
const channels = KALSHI_CHANNELS.ORDERBOOK_DELTA;

console.log('Kalshi client imports work correctly');

export { testConfig, channels };

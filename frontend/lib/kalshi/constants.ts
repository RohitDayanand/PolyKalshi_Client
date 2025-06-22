/**
 * Constants and configuration for Kalshi API
 */

import { Environment } from './types';

// API Keys and Authentication - Define these at the top for easy access
export const KALSHI_API_CONFIG = {
  // TODO: Move these to environment variables in production
  DEMO: {
    KEY_ID: 'your-demo-key-id-here',
    PRIVATE_KEY_PATH: './rsa_kalshi_key.txt', // Path to private key file
  },
  PROD: {
    KEY_ID: 'your-prod-key-id-here', 
    PRIVATE_KEY_PATH: './rsa_kalshi_key.txt', // Path to private key file
  }
} as const;

// API Endpoints
export const KALSHI_ENDPOINTS = {
  [Environment.DEMO]: {
    HTTP_BASE_URL: 'https://demo-api.kalshi.co',
    WS_BASE_URL: 'wss://demo-api.kalshi.co',
  },
  [Environment.PROD]: {
    HTTP_BASE_URL: 'https://api.elections.kalshi.com',
    WS_BASE_URL: 'wss://api.elections.kalshi.com',
  },
} as const;

// API Paths
export const KALSHI_PATHS = {
  EXCHANGE: '/trade-api/v2/exchange',
  MARKETS: '/trade-api/v2/markets',
  PORTFOLIO: '/trade-api/v2/portfolio',
  WEBSOCKET: '/trade-api/ws/v2',
} as const;

// WebSocket Channels
export const KALSHI_CHANNELS = {
  ORDERBOOK_DELTA: 'orderbook_delta',
  TICKER: 'ticker',
  TRADE: 'trade',
  FILL: 'fill',
} as const;

// Rate Limiting
export const KALSHI_RATE_LIMITS = {
  DEFAULT_RATE_LIMIT_MS: 100,
  MAX_REQUESTS_PER_SECOND: 10,
  BURST_LIMIT: 20,
} as const;

// WebSocket Configuration
export const KALSHI_WEBSOCKET_CONFIG = {
  DEFAULT_RECONNECT_ATTEMPTS: 3,
  DEFAULT_RECONNECT_DELAY_MS: 5000,
  DEFAULT_PING_TIMEOUT_MS: 10000,
  MESSAGE_TIMEOUT_MS: 30000,
  HEARTBEAT_INTERVAL_MS: 30000,
} as const;

// Crypto Configuration
export const KALSHI_CRYPTO_CONFIG = {
  SIGNATURE_ALGORITHM: 'RSASSA-PSS',
  HASH_ALGORITHM: 'SHA-256',
  SALT_LENGTH: -1, // PSS.DIGEST_LENGTH equivalent
} as const;

// Default Headers
export const KALSHI_DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  'User-Agent': 'Kalshi-TypeScript-Client/1.0.0',
} as const;

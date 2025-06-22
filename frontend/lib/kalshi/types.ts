/**
 * TypeScript type definitions for Kalshi API
 */

export enum Environment {
  DEMO = "demo",
  PROD = "prod"
}

// API Response Types
export interface KalshiBalance {
  balance: number;
  [key: string]: any;
}

export interface KalshiExchangeStatus {
  exchange_active: boolean;
  trading_active: boolean;
  [key: string]: any;
}

export interface KalshiTrade {
  trade_id: string;
  ticker: string;
  price: number;
  count: number;
  side: 'yes' | 'no';
  created_time: string;
  [key: string]: any;
}

export interface KalshiTradesResponse {
  trades: KalshiTrade[];
  cursor?: string;
  [key: string]: any;
}

// WebSocket Message Types
export interface KalshiWebSocketMessage {
  id?: number;
  type: string;
  msg?: string;
  [key: string]: any;
}

export interface KalshiSubscribeMessage {
  id: number;
  cmd: 'subscribe' | 'unsubscribe';
  params: {
    channels: string[];
    market_tickers: string[];
  };
}

export interface KalshiSubscribedMessage extends KalshiWebSocketMessage {
  type: 'subscribed';
  sid: string;
  params: {
    channels: string[];
    market_tickers: string[];
  };
}

export interface KalshiOrderbookSnapshot extends KalshiWebSocketMessage {
  type: 'orderbook_snapshot';
  market_ticker: string;
  yes: Array<[number, number]>; // [price, size]
  no: Array<[number, number]>;  // [price, size]
  ts: number;
}

export interface KalshiOrderbookDelta extends KalshiWebSocketMessage {
  type: 'orderbook_delta';
  market_ticker: string;
  yes?: Array<[number, number]>; // [price, size]
  no?: Array<[number, number]>;  // [price, size]
  ts: number;
}

export interface KalshiTradeMessage extends KalshiWebSocketMessage {
  type: 'trade';
  market_ticker: string;
  price: number;
  count: number;
  side: 'yes' | 'no';
  ts: number;
  trade_id: string;
}

export interface KalshiFillMessage extends KalshiWebSocketMessage {
  type: 'fill';
  market_ticker: string;
  price: number;
  count: number;
  side: 'yes' | 'no';
  ts: number;
  fill_id: string;
}

export interface KalshiTickerV2Message extends KalshiWebSocketMessage {
  type: 'ticker_v2';
  market_ticker: string;
  yes?: number;
  no?: number;
  ts: number;
}

export interface KalshiPingMessage extends KalshiWebSocketMessage {
  type: 'ping';
}

export interface KalshiPongMessage extends KalshiWebSocketMessage {
  type: 'pong';
}

export interface KalshiErrorMessage extends KalshiWebSocketMessage {
  type: 'error';
  msg: string;
  code?: number;
}

// Union type for all possible WebSocket messages
export type KalshiWebSocketIncomingMessage = 
  | KalshiSubscribedMessage
  | KalshiOrderbookSnapshot
  | KalshiOrderbookDelta
  | KalshiTradeMessage
  | KalshiFillMessage
  | KalshiTickerV2Message
  | KalshiPingMessage
  | KalshiErrorMessage
  | KalshiWebSocketMessage;

export type KalshiWebSocketOutgoingMessage = 
  | KalshiSubscribeMessage
  | KalshiPongMessage;

// HTTP Client Configuration
export interface KalshiHttpClientConfig {
  keyId: string;
  privateKey: string; // PEM format private key
  environment: Environment;
  rateLimitMs?: number;
}

// WebSocket Client Configuration
export interface KalshiWebSocketClientConfig {
  keyId: string;
  privateKey: string; // PEM format private key
  environment: Environment;
  reconnectAttempts?: number;
  reconnectDelayMs?: number;
  pingTimeoutMs?: number;
}

// Subscription Configuration
export interface KalshiSubscription {
  channels: string[];
  marketTickers: string[];
}

// Error Types
export class KalshiError extends Error {
  constructor(
    message: string,
    public code?: number,
    public response?: Response
  ) {
    super(message);
    this.name = 'KalshiError';
  }
}

export class KalshiAuthError extends KalshiError {
  constructor(message: string = 'Authentication failed') {
    super(message);
    this.name = 'KalshiAuthError';
  }
}

export class KalshiRateLimitError extends KalshiError {
  constructor(message: string = 'Rate limit exceeded') {
    super(message);
    this.name = 'KalshiRateLimitError';
  }
}

export class KalshiWebSocketError extends KalshiError {
  constructor(message: string = 'WebSocket error') {
    super(message);
    this.name = 'KalshiWebSocketError';
  }
}

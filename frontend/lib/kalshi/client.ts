/**
 * Main Kalshi client that combines HTTP and WebSocket functionality
 */

import { Observable, from } from 'rxjs';
import { map } from 'rxjs/operators';

import { KalshiHttpClient } from './http-client';
import { KalshiWebSocketClient } from './websocket-client';
import {
  Environment,
  KalshiHttpClientConfig,
  KalshiWebSocketClientConfig,
  KalshiSubscription,
  KalshiBalance,
  KalshiExchangeStatus,
  KalshiTradesResponse,
  KalshiWebSocketIncomingMessage,
  KalshiOrderbookSnapshot,
  KalshiOrderbookDelta,
  KalshiTradeMessage,
  KalshiFillMessage,
  KalshiTickerV2Message,
  KalshiSubscribedMessage,
  KalshiWebSocketError
} from './types';
import { KALSHI_API_CONFIG, KALSHI_CHANNELS } from './constants';

export interface KalshiClientConfig {
  keyId?: string;
  privateKey?: string;
  environment: Environment;
  rateLimitMs?: number;
  reconnectAttempts?: number;
  reconnectDelayMs?: number;
  pingTimeoutMs?: number;
}

export class KalshiClient {
  private httpClient: KalshiHttpClient;
  private wsClient: KalshiWebSocketClient;

  constructor(config: KalshiClientConfig) {
    // Use default API config if not provided
    const apiConfig = KALSHI_API_CONFIG[config.environment.toUpperCase() as keyof typeof KALSHI_API_CONFIG];
    const keyId = config.keyId || apiConfig.KEY_ID;
    const privateKey = config.privateKey || this.loadPrivateKey(apiConfig.PRIVATE_KEY_PATH);

    // Initialize HTTP client
    const httpConfig: KalshiHttpClientConfig = {
      keyId,
      privateKey,
      environment: config.environment,
      rateLimitMs: config.rateLimitMs,
    };
    this.httpClient = new KalshiHttpClient(httpConfig);

    // Initialize WebSocket client
    const wsConfig: KalshiWebSocketClientConfig = {
      keyId,
      privateKey,
      environment: config.environment,
      reconnectAttempts: config.reconnectAttempts,
      reconnectDelayMs: config.reconnectDelayMs,
      pingTimeoutMs: config.pingTimeoutMs,
    };
    this.wsClient = new KalshiWebSocketClient(wsConfig);
  }

  // HTTP Methods

  /**
   * Get account balance
   */
  getBalance(): Observable<KalshiBalance> {
    return this.httpClient.getBalance();
  }

  /**
   * Get exchange status
   */
  getExchangeStatus(): Observable<KalshiExchangeStatus> {
    return this.httpClient.getExchangeStatus();
  }

  /**
   * Get trades for a market
   */
  getTrades(options: {
    ticker?: string;
    limit?: number;
    cursor?: string;
    maxTs?: number;
    minTs?: number;
  } = {}): Observable<KalshiTradesResponse> {
    return this.httpClient.getTrades(options);
  }

  /**
   * Generic HTTP GET request
   */
  get<T>(path: string, params?: Record<string, any>): Observable<T> {
    return this.httpClient.get<T>(path, params);
  }

  /**
   * Generic HTTP POST request
   */
  post<T>(path: string, body?: any): Observable<T> {
    return this.httpClient.post<T>(path, body);
  }

  // WebSocket Methods

  /**
   * Connect to WebSocket
   */
  connect(): Observable<void> {
    return this.wsClient.connect();
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect(): void {
    this.wsClient.disconnect();
  }

  /**
   * Get connection status
   */
  get connectionStatus(): Observable<'disconnected' | 'connecting' | 'connected'> {
    return this.wsClient.connectionStatus;
  }

  /**
   * Subscribe to market data
   */
  subscribe(subscription: KalshiSubscription): Observable<KalshiSubscribedMessage> {
    return this.wsClient.subscribe(subscription);
  }

  /**
   * Unsubscribe from market data
   */
  unsubscribe(subscription: KalshiSubscription): Observable<void> {
    return this.wsClient.unsubscribe(subscription);
  }

  /**
   * Subscribe to orderbook for a specific market
   */
  subscribeToOrderbook(marketTicker: string): Observable<KalshiSubscribedMessage> {
    return this.subscribe({
      channels: [KALSHI_CHANNELS.ORDERBOOK_DELTA],
      marketTickers: [marketTicker],
    });
  }

  /**
   * Subscribe to trades for a specific market
   */
  subscribeToTrades(marketTicker: string): Observable<KalshiSubscribedMessage> {
    return this.subscribe({
      channels: [KALSHI_CHANNELS.TRADE],
      marketTickers: [marketTicker],
    });
  }

  /**
   * Subscribe to ticker for a specific market
   */
  subscribeToTicker(marketTicker: string): Observable<KalshiSubscribedMessage> {
    return this.subscribe({
      channels: [KALSHI_CHANNELS.TICKER],
      marketTickers: [marketTicker],
    });
  }

  // WebSocket Data Streams

  /**
   * All incoming WebSocket messages
   */
  get messages(): Observable<KalshiWebSocketIncomingMessage> {
    return this.wsClient.messages;
  }

  /**
   * WebSocket errors
   */
  get errors(): Observable<KalshiWebSocketError> {
    return this.wsClient.errors;
  }

  /**
   * Orderbook snapshots
   */
  get orderbookSnapshots(): Observable<KalshiOrderbookSnapshot> {
    return this.wsClient.orderbookSnapshots;
  }

  /**
   * Orderbook deltas
   */
  get orderbookDeltas(): Observable<KalshiOrderbookDelta> {
    return this.wsClient.orderbookDeltas;
  }

  /**
   * Trade messages
   */
  get trades(): Observable<KalshiTradeMessage> {
    return this.wsClient.trades;
  }

  /**
   * Fill messages
   */
  get fills(): Observable<KalshiFillMessage> {
    return this.wsClient.fills;
  }

  /**
   * Ticker messages
   */
  get tickers(): Observable<KalshiTickerV2Message> {
    return this.wsClient.tickers;
  }

  // Utility Methods

  /**
   * Load private key from file path (for Node.js environments)
   * In browser environments, the private key should be passed directly
   */
  private loadPrivateKey(keyPath: string): string {
    if (typeof window !== 'undefined') {
      throw new Error('Cannot load private key from file in browser environment. Pass privateKey directly in config.');
    }
    
    // This would work in Node.js environments
    // For browser use, private key must be provided in config
    try {
      const fs = require('fs');
      return fs.readFileSync(keyPath, 'utf8');
    } catch (error) {
      throw new Error(`Failed to load private key from ${keyPath}: ${error}`);
    }
  }
}

// Convenience exports
export { 
  Environment,
  KALSHI_CHANNELS
};

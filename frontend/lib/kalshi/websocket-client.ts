/**
 * WebSocket Client for Kalshi API using RxJS WebSocketSubject
 */

import { 
  Observable, 
  Subject, 
  BehaviorSubject,
  timer, 
  NEVER,
  throwError,
  of,
  merge,
  EMPTY
} from 'rxjs';
import {
  webSocket,
  WebSocketSubject
} from 'rxjs/webSocket';
import {
  map,
  filter,
  tap,
  catchError,
  retry,
  retryWhen,
  delay,
  take,
  takeUntil,
  share,
  startWith,
  switchMap,
  timeout
} from 'rxjs/operators';

import {
  Environment,
  KalshiWebSocketClientConfig,
  KalshiWebSocketIncomingMessage,
  KalshiWebSocketOutgoingMessage,
  KalshiSubscribeMessage,
  KalshiSubscribedMessage,
  KalshiOrderbookSnapshot,
  KalshiOrderbookDelta,
  KalshiTradeMessage,
  KalshiFillMessage,
  KalshiTickerV2Message,
  KalshiPingMessage,
  KalshiPongMessage,
  KalshiErrorMessage,
  KalshiSubscription,
  KalshiWebSocketError
} from './types';
import {
  KALSHI_ENDPOINTS,
  KALSHI_PATHS,
  KALSHI_WEBSOCKET_CONFIG,
  KALSHI_CHANNELS
} from './constants';
import { generateAuthHeaders } from './crypto';

export class KalshiWebSocketClient {
  private readonly wsUrl: string;
  private readonly keyId: string;
  private readonly privateKey: string;
  private readonly reconnectAttempts: number;
  private readonly reconnectDelayMs: number;
  private readonly pingTimeoutMs: number;

  private websocket$: WebSocketSubject<any> | null = null;
  private messageId = 1;
  private destroy$ = new Subject<void>();
  private connectionStatus$ = new BehaviorSubject<'disconnected' | 'connecting' | 'connected'>('disconnected');
  private subscriptions = new Map<string, KalshiSubscription>();

  // Message streams
  private messages$ = new Subject<KalshiWebSocketIncomingMessage>();
  private errors$ = new Subject<KalshiWebSocketError>();

  constructor(config: KalshiWebSocketClientConfig) {
    this.keyId = config.keyId;
    this.privateKey = config.privateKey;
    this.reconnectAttempts = config.reconnectAttempts ?? KALSHI_WEBSOCKET_CONFIG.DEFAULT_RECONNECT_ATTEMPTS;
    this.reconnectDelayMs = config.reconnectDelayMs ?? KALSHI_WEBSOCKET_CONFIG.DEFAULT_RECONNECT_DELAY_MS;
    this.pingTimeoutMs = config.pingTimeoutMs ?? KALSHI_WEBSOCKET_CONFIG.DEFAULT_PING_TIMEOUT_MS;

    const endpoints = KALSHI_ENDPOINTS[config.environment];
    this.wsUrl = endpoints.WS_BASE_URL + KALSHI_PATHS.WEBSOCKET;
  }

  /**
   * Connection status observable
   */
  get connectionStatus(): Observable<'disconnected' | 'connecting' | 'connected'> {
    return this.connectionStatus$.asObservable();
  }

  /**
   * All incoming messages
   */
  get messages(): Observable<KalshiWebSocketIncomingMessage> {
    return this.messages$.asObservable();
  }

  /**
   * Error messages
   */
  get errors(): Observable<KalshiWebSocketError> {
    return this.errors$.asObservable();
  }

  /**
   * Subscription confirmations
   */
  get subscribed(): Observable<KalshiSubscribedMessage> {
    return this.messages$.pipe(
      filter((msg): msg is KalshiSubscribedMessage => msg.type === 'subscribed')
    );
  }

  /**
   * Orderbook snapshots
   */
  get orderbookSnapshots(): Observable<KalshiOrderbookSnapshot> {
    return this.messages$.pipe(
      filter((msg): msg is KalshiOrderbookSnapshot => msg.type === 'orderbook_snapshot')
    );
  }

  /**
   * Orderbook deltas
   */
  get orderbookDeltas(): Observable<KalshiOrderbookDelta> {
    return this.messages$.pipe(
      filter((msg): msg is KalshiOrderbookDelta => msg.type === 'orderbook_delta')
    );
  }

  /**
   * Trade messages
   */
  get trades(): Observable<KalshiTradeMessage> {
    return this.messages$.pipe(
      filter((msg): msg is KalshiTradeMessage => msg.type === 'trade')
    );
  }

  /**
   * Fill messages
   */
  get fills(): Observable<KalshiFillMessage> {
    return this.messages$.pipe(
      filter((msg): msg is KalshiFillMessage => msg.type === 'fill')
    );
  }

  /**
   * Ticker v2 messages
   */
  get tickers(): Observable<KalshiTickerV2Message> {
    return this.messages$.pipe(
      filter((msg): msg is KalshiTickerV2Message => msg.type === 'ticker_v2')
    );
  }

  /**
   * Connect to WebSocket
   */
  connect(): Observable<void> {
    if (this.connectionStatus$.value === 'connected' || this.connectionStatus$.value === 'connecting') {
      return EMPTY;
    }

    return this.createConnection().pipe(
      tap(() => {
        console.log('Kalshi WebSocket connected successfully');
        this.connectionStatus$.next('connected');
      }),
      catchError((error) => {
        console.error('Kalshi WebSocket connection failed:', error);
        this.connectionStatus$.next('disconnected');
        this.errors$.next(new KalshiWebSocketError(`Connection failed: ${error}`));
        return throwError(() => error);
      })
    );
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect(): void {
    this.destroy$.next();
    this.connectionStatus$.next('disconnected');
    if (this.websocket$) {
      this.websocket$.complete();
      this.websocket$ = null;
    }
    this.subscriptions.clear();
    console.log('Kalshi WebSocket disconnected');
  }

  /**
   * Subscribe to channels and market tickers
   */
  subscribe(subscription: KalshiSubscription): Observable<KalshiSubscribedMessage> {
    const subscribeMessage: KalshiSubscribeMessage = {
      id: this.messageId++,
      cmd: 'subscribe',
      params: {
        channels: subscription.channels,
        market_tickers: subscription.marketTickers,
      },
    };

    // Store subscription for reconnection
    const key = this.getSubscriptionKey(subscription);
    this.subscriptions.set(key, subscription);

    return this.sendMessage(subscribeMessage).pipe(
      switchMap(() => 
        this.subscribed.pipe(
          filter(msg => 
            this.arraysEqual(msg.params.channels, subscription.channels) &&
            this.arraysEqual(msg.params.market_tickers, subscription.marketTickers)
          ),
          take(1),
          timeout(10000),
          catchError(error => {
            this.errors$.next(new KalshiWebSocketError(`Subscription timeout: ${error}`));
            return throwError(() => error);
          })
        )
      )
    );
  }

  /**
   * Unsubscribe from channels and market tickers
   */
  unsubscribe(subscription: KalshiSubscription): Observable<void> {
    const unsubscribeMessage: KalshiSubscribeMessage = {
      id: this.messageId++,
      cmd: 'unsubscribe',
      params: {
        channels: subscription.channels,
        market_tickers: subscription.marketTickers,
      },
    };

    // Remove from stored subscriptions
    const key = this.getSubscriptionKey(subscription);
    this.subscriptions.delete(key);

    return this.sendMessage(unsubscribeMessage);
  }

  /**
   * Send a message to the WebSocket
   */
  private sendMessage(message: KalshiWebSocketOutgoingMessage): Observable<void> {
    if (!this.websocket$ || this.connectionStatus$.value !== 'connected') {
      return throwError(() => new KalshiWebSocketError('Not connected to WebSocket'));
    }

    try {
      this.websocket$.next(message);
      console.log('Sent Kalshi WebSocket message:', message);
      return of(undefined);
    } catch (error) {
      const wsError = new KalshiWebSocketError(`Failed to send message: ${error}`);
      this.errors$.next(wsError);
      return throwError(() => wsError);
    }
  }

  /**
   * Create WebSocket connection with authentication and retry logic
   */
  private createConnection(): Observable<void> {
    this.connectionStatus$.next('connecting');

    return of(null).pipe(
      switchMap(() => this.generateAuthHeaders()),
      switchMap((headers) => this.createWebSocket(headers)),
      retryWhen(errors =>
        errors.pipe(
          tap(error => console.log('WebSocket connection error, retrying...', error)),
          delay(this.reconnectDelayMs),
          take(this.reconnectAttempts)
        )
      )
    );
  }

  /**
   * Generate authentication headers for WebSocket connection
   */
  private async generateAuthHeaders(): Promise<Record<string, string>> {
    return generateAuthHeaders('GET', KALSHI_PATHS.WEBSOCKET, this.keyId, this.privateKey);
  }

  /**
   * Create the actual WebSocket connection
   */
  private createWebSocket(headers: Record<string, string>): Observable<void> {
    this.websocket$ = webSocket({
      url: this.wsUrl,
      openObserver: {
        next: () => {
          console.log('Kalshi WebSocket connection opened');
          this.resubscribeAll();
        }
      },
      closeObserver: {
        next: (event) => {
          console.log('Kalshi WebSocket connection closed:', event);
          this.connectionStatus$.next('disconnected');
        }
      },
      serializer: (msg) => JSON.stringify(msg),
      deserializer: (e) => {
        try {
          return JSON.parse(e.data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', e.data);
          return { type: 'error', msg: 'Failed to parse message' };
        }
      }
    });

    // Subscribe to messages and handle them
    this.websocket$.pipe(
      takeUntil(this.destroy$),
      tap(message => {
        console.log('Received Kalshi WebSocket message:', message);
        this.handleMessage(message);
      }),
      catchError(error => {
        console.error('WebSocket error:', error);
        this.connectionStatus$.next('disconnected');
        this.errors$.next(new KalshiWebSocketError(`WebSocket error: ${error}`));
        return EMPTY;
      })
    ).subscribe();

    return of(undefined);
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleMessage(message: any): void {
    try {
      // Handle ping/pong
      if (message.type === 'ping') {
        const pongMessage: KalshiPongMessage = { type: 'pong' };
        this.sendMessage(pongMessage).subscribe();
        return;
      }

      // Handle errors
      if (message.type === 'error') {
        const error = new KalshiWebSocketError(message.msg || 'Unknown WebSocket error');
        this.errors$.next(error);
        return;
      }

      // Emit message to subscribers
      this.messages$.next(message as KalshiWebSocketIncomingMessage);
    } catch (error) {
      console.error('Error handling WebSocket message:', error);
      this.errors$.next(new KalshiWebSocketError(`Message handling error: ${error}`));
    }
  }

  /**
   * Resubscribe to all stored subscriptions after reconnection
   */
  private resubscribeAll(): void {
    this.subscriptions.forEach((subscription) => {
      const subscribeMessage: KalshiSubscribeMessage = {
        id: this.messageId++,
        cmd: 'subscribe',
        params: {
          channels: subscription.channels,
          market_tickers: subscription.marketTickers,
        },
      };
      this.sendMessage(subscribeMessage).subscribe();
    });
  }

  /**
   * Generate a unique key for a subscription
   */
  private getSubscriptionKey(subscription: KalshiSubscription): string {
    return `${subscription.channels.sort().join(',')}:${subscription.marketTickers.sort().join(',')}`;
  }

  /**
   * Compare two arrays for equality
   */
  private arraysEqual<T>(a: T[], b: T[]): boolean {
    return a.length === b.length && a.every((val, i) => val === b[i]);
  }
}

/**
 * HTTP Client for Kalshi API using modern fetch with RxJS integration
 */

import { 
  Observable, 
  from, 
  delay, 
  retry, 
  catchError, 
  throwError,
  BehaviorSubject,
  filter,
  take
} from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { 
  Environment, 
  KalshiHttpClientConfig, 
  KalshiBalance, 
  KalshiExchangeStatus, 
  KalshiTradesResponse,
  KalshiError,
  KalshiAuthError,
  KalshiRateLimitError
} from './types';
import { 
  KALSHI_ENDPOINTS, 
  KALSHI_PATHS, 
  KALSHI_RATE_LIMITS,
  KALSHI_DEFAULT_HEADERS
} from './constants';
import { generateAuthHeaders } from './crypto';

export class KalshiHttpClient {
  private readonly baseUrl: string;
  private readonly keyId: string;
  private readonly privateKey: string;
  private readonly rateLimitMs: number;
  private lastRequestTime = 0;
  private readonly rateLimitSubject = new BehaviorSubject<boolean>(true);

  constructor(config: KalshiHttpClientConfig) {
    this.keyId = config.keyId;
    this.privateKey = config.privateKey;
    this.rateLimitMs = config.rateLimitMs ?? KALSHI_RATE_LIMITS.DEFAULT_RATE_LIMIT_MS;
    
    const endpoints = KALSHI_ENDPOINTS[config.environment];
    this.baseUrl = endpoints.HTTP_BASE_URL;
  }

  /**
   * Enforces rate limiting before making requests
   */
  private waitForRateLimit(): Observable<boolean> {
    const now = Date.now();
    const timeSinceLastRequest = now - this.lastRequestTime;
    
    if (timeSinceLastRequest >= this.rateLimitMs) {
      this.lastRequestTime = now;
      this.rateLimitSubject.next(true);
      return this.rateLimitSubject.pipe(take(1));
    }
    
    const waitTime = this.rateLimitMs - timeSinceLastRequest;
    return this.rateLimitSubject.pipe(
      delay(waitTime),
      take(1),
      filter(() => {
        this.lastRequestTime = Date.now();
        return true;
      })
    );
  }

  /**
   * Makes an authenticated HTTP request
   */
  private request<T>(
    method: string,
    path: string,
    params?: Record<string, any>,
    body?: any
  ): Observable<T> {
    return this.waitForRateLimit().pipe(
      switchMap(() => from(this.makeRequest<T>(method, path, params, body))),
      retry({
        count: 3,
        delay: (error, retryCount) => {
          if (error instanceof KalshiRateLimitError) {
            return delay(Math.pow(2, retryCount) * 1000)(throwError(error));
          }
          if (error instanceof KalshiAuthError) {
            return throwError(error); // Don't retry auth errors
          }
          return delay(1000 * retryCount)(throwError(error));
        }
      }),
      catchError((error) => {
        console.error('Kalshi HTTP request failed:', error);
        return throwError(() => error);
      })
    );
  }

  private async makeRequest<T>(
    method: string,
    path: string,
    params?: Record<string, any>,
    body?: any
  ): Promise<T> {
    try {
      // Build URL with query parameters
      const url = new URL(path, this.baseUrl);
      if (params) {
        Object.entries(params).forEach(([key, value]) => {
          if (value !== undefined && value !== null) {
            url.searchParams.append(key, String(value));
          }
        });
      }

      // Generate authentication headers
      const authHeaders = await generateAuthHeaders(
        method,
        url.pathname + url.search,
        this.keyId,
        this.privateKey
      );

      // Prepare request options
      const requestInit: RequestInit = {
        method,
        headers: {
          ...KALSHI_DEFAULT_HEADERS,
          ...authHeaders,
        },
      };

      if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
        requestInit.body = JSON.stringify(body);
      }

      // Make the request
      const response = await fetch(url.toString(), requestInit);

      // Handle response
      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json();
      return data as T;
    } catch (error) {
      if (error instanceof KalshiError) {
        throw error;
      }
      throw new KalshiError(`Request failed: ${error}`);
    }
  }

  private async handleErrorResponse(response: Response): Promise<never> {
    const errorText = await response.text();
    let errorData: any = {};
    
    try {
      errorData = JSON.parse(errorText);
    } catch {
      // Response is not JSON
    }

    const message = errorData.msg || errorData.message || `HTTP ${response.status}: ${response.statusText}`;

    switch (response.status) {
      case 401:
      case 403:
        throw new KalshiAuthError(message);
      case 429:
        throw new KalshiRateLimitError(message);
      default:
        throw new KalshiError(message, response.status, response);
    }
  }

  // Public API Methods

  /**
   * Get account balance
   */
  getBalance(): Observable<KalshiBalance> {
    return this.request<KalshiBalance>('GET', KALSHI_PATHS.PORTFOLIO + '/balance');
  }

  /**
   * Get exchange status
   */
  getExchangeStatus(): Observable<KalshiExchangeStatus> {
    return this.request<KalshiExchangeStatus>('GET', KALSHI_PATHS.EXCHANGE + '/status');
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
    const params = {
      ticker: options.ticker,
      limit: options.limit,
      cursor: options.cursor,
      max_ts: options.maxTs,
      min_ts: options.minTs,
    };

    return this.request<KalshiTradesResponse>('GET', KALSHI_PATHS.MARKETS + '/trades', params);
  }

  /**
   * Generic GET request
   */
  get<T>(path: string, params?: Record<string, any>): Observable<T> {
    return this.request<T>('GET', path, params);
  }

  /**
   * Generic POST request
   */
  post<T>(path: string, body?: any): Observable<T> {
    return this.request<T>('POST', path, undefined, body);
  }

  /**
   * Generic PUT request
   */
  put<T>(path: string, body?: any): Observable<T> {
    return this.request<T>('PUT', path, undefined, body);
  }

  /**
   * Generic DELETE request
   */
  delete<T>(path: string): Observable<T> {
    return this.request<T>('DELETE', path);
  }
}

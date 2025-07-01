/**
 * React hooks for Kalshi client integration
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { Observable, Subscription, firstValueFrom } from 'rxjs';
import { KalshiClient, Environment, KalshiWebSocketIncomingMessage, KalshiSubscription } from './index';

export interface UseKalshiClientOptions {
  environment: Environment;
  keyId?: string;
  privateKey?: string;
  autoConnect?: boolean;
}

export interface KalshiClientState {
  client: KalshiClient | null;
  isConnected: boolean;
  isConnecting: boolean;
  error: Error | null;
}

/**
 * Hook for managing Kalshi client instance
 */
export function useKalshiClient(options: UseKalshiClientOptions): KalshiClientState & {
  connect: () => Promise<void>;
  disconnect: () => void;
  subscribe: (subscription: KalshiSubscription) => Promise<void>;
  unsubscribe: (subscription: KalshiSubscription) => Promise<void>;
} {
  const [state, setState] = useState<KalshiClientState>({
    client: null,
    isConnected: false,
    isConnecting: false,
    error: null,
  });

  const subscriptionsRef = useRef<Set<Subscription>>(new Set());

  // Initialize client
  useEffect(() => {
    try {
      const client = new KalshiClient({
        environment: options.environment,
        keyId: options.keyId,
        privateKey: options.privateKey,
      });

      setState(prev => ({ ...prev, client, error: null }));

      // Subscribe to connection status
      const statusSub = client.connectionStatus.subscribe(status => {
        setState(prev => ({
          ...prev,
          isConnected: status === 'connected',
          isConnecting: status === 'connecting',
        }));
      });

      // Subscribe to errors
      const errorSub = client.errors.subscribe(error => {
        setState(prev => ({ ...prev, error }));
      });

      subscriptionsRef.current.add(statusSub);
      subscriptionsRef.current.add(errorSub);

      // Auto-connect if enabled
      if (options.autoConnect) {
        client.connect().subscribe({
          error: (error) => {
            setState(prev => ({ ...prev, error }));
          }
        });
      }

    } catch (error) {
      setState(prev => ({ ...prev, error: error as Error }));
    }

    return () => {
      // Cleanup subscriptions
      subscriptionsRef.current.forEach(sub => sub.unsubscribe());
      subscriptionsRef.current.clear();
      
      // Disconnect client
      if (state.client) {
        state.client.disconnect();
      }
    };
  }, [options.environment, options.keyId, options.privateKey, options.autoConnect]);

  const connect = useCallback(async () => {
    if (!state.client) {
      throw new Error('Kalshi client not initialized');
    }

    setState(prev => ({ ...prev, isConnecting: true, error: null }));

    try {
      await firstValueFrom(state.client.connect());
    } catch (error) {
      setState(prev => ({ ...prev, error: error as Error, isConnecting: false }));
      throw error;
    }
  }, [state.client]);

  const disconnect = useCallback(() => {
    if (state.client) {
      state.client.disconnect();
    }
  }, [state.client]);

  const subscribe = useCallback(async (subscription: KalshiSubscription) => {
    if (!state.client) {
      throw new Error('Kalshi client not initialized');
    }

    if (!state.isConnected) {
      throw new Error('Not connected to Kalshi WebSocket');
    }

    try {
      await firstValueFrom(state.client.subscribe(subscription));
    } catch (error) {
      setState(prev => ({ ...prev, error: error as Error }));
      throw error;
    }
  }, [state.client, state.isConnected]);

  const unsubscribe = useCallback(async (subscription: KalshiSubscription) => {
    if (!state.client) {
      throw new Error('Kalshi client not initialized');
    }

    try {
      await firstValueFrom(state.client.unsubscribe(subscription));
    } catch (error) {
      setState(prev => ({ ...prev, error: error as Error }));
      throw error;
    }
  }, [state.client]);

  return {
    ...state,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
  };
}

/**
 * Hook for subscribing to specific Kalshi data streams
 */
export function useKalshiData<T extends KalshiWebSocketIncomingMessage>(
  client: KalshiClient | null,
  streamSelector: (client: KalshiClient) => Observable<T>,
  deps: any[] = []
): {
  data: T[];
  latest: T | null;
  error: Error | null;
} {
  const [data, setData] = useState<T[]>([]);
  const [latest, setLatest] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!client) {
      return;
    }

    setError(null);
    const subscription = streamSelector(client).subscribe({
      next: (message) => {
        setLatest(message);
        setData(prev => [...prev, message]);
      },
      error: (err) => {
        setError(err);
      }
    });

    return () => subscription.unsubscribe();
  }, [client, ...deps]);

  return { data, latest, error };
}

/**
 * Hook for Kalshi orderbook data
 */
export function useKalshiOrderbook(client: KalshiClient | null, marketTicker?: string) {
  const snapshots = useKalshiData(
    client,
    (c) => marketTicker 
      ? c.orderbookSnapshots.pipe(filter((msg: any) => msg.market_ticker === marketTicker))
      : c.orderbookSnapshots,
    [marketTicker]
  );

  const deltas = useKalshiData(
    client,
    (c) => marketTicker
      ? c.orderbookDeltas.pipe(filter((msg: any) => msg.market_ticker === marketTicker))
      : c.orderbookDeltas,
    [marketTicker]
  );

  return {
    snapshots: snapshots.data,
    latestSnapshot: snapshots.latest,
    deltas: deltas.data,
    latestDelta: deltas.latest,
    error: snapshots.error || deltas.error,
  };
}

/**
 * Hook for Kalshi trade data
 */
export function useKalshiTrades(client: KalshiClient | null, marketTicker?: string) {
  return useKalshiData(
    client,
    (c) => marketTicker
      ? c.trades.pipe(filter((msg: any) => msg.market_ticker === marketTicker))
      : c.trades,
    [marketTicker]
  );
}

/**
 * Hook for Kalshi ticker data
 */
export function useKalshiTickers(client: KalshiClient | null, marketTicker?: string) {
  return useKalshiData(
    client,
    (c) => marketTicker
      ? c.tickers.pipe(filter((msg: any) => msg.market_ticker === marketTicker))
      : c.tickers,
    [marketTicker]
  );
}

// Import filter operator
import { filter } from 'rxjs/operators';

/**
 * CHART EVENT HOOKS
 * 
 * React hooks for type-safe Pub/Sub integration with automatic cleanup.
 * Provides easy subscription management for chart components.
 */

import { useEffect, useRef, useCallback } from 'react';
import { chartEventBus, ChartEventName, ChartEventTypes } from '../events/ChartEventBus';

/**
 * Hook for subscribing to chart events with automatic cleanup
 */
export function useChartEvent<K extends ChartEventName>(
  eventName: K,
  handler: (payload: ChartEventTypes[K]) => void,
  dependencies: any[] = []
): void {
  const handlerRef = useRef(handler);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  // Update handler ref when it changes
  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  useEffect(() => {
    // Create stable handler that uses the ref
    const stableHandler = (payload: ChartEventTypes[K]) => {
      handlerRef.current(payload);
    };

    // Subscribe to event
    const unsubscribe = chartEventBus.on(eventName, stableHandler);
    unsubscribeRef.current = unsubscribe;
    // Cleanup on unmount or dependency change
    return () => {
      unsubscribe();
      unsubscribeRef.current = null;
    };
  }, [eventName, ...dependencies]);
}

/**
 * Hook for subscribing to multiple chart events
 */
export function useChartEvents(
  subscriptions: Array<{
    eventName: ChartEventName;
    handler: (payload: any) => void;
  }>,
  dependencies: any[] = []
): void {
  const handlersRef = useRef(subscriptions);
  const unsubscribersRef = useRef<(() => void)[]>([]);

  // Update handlers ref when they change
  useEffect(() => {
    handlersRef.current = subscriptions;
  }, [subscriptions]);

  useEffect(() => {
    // Clean up previous subscriptions
    unsubscribersRef.current.forEach(unsubscribe => unsubscribe());
    unsubscribersRef.current = [];

    // Create new subscriptions
    const unsubscribers = subscriptions.map(({ eventName, handler }) => {
      const stableHandler = (payload: any) => {
        // Find current handler for this event
        const currentSub = handlersRef.current.find(s => s.eventName === eventName);
        if (currentSub) {
          currentSub.handler(payload);
        }
      };

      return chartEventBus.on(eventName, stableHandler);
    });

    unsubscribersRef.current = unsubscribers;

    // Cleanup on unmount or dependency change
    return () => {
      unsubscribers.forEach(unsubscribe => unsubscribe());
      unsubscribersRef.current = [];
    };
  }, [subscriptions.length, ...dependencies]);
}

/**
 * Hook for pattern-based event subscription (e.g., 'data.*')
 */
export function useChartEventPattern(
  pattern: string,
  handler: (eventName: string, payload: any) => void,
  dependencies: any[] = []
): void {
  const handlerRef = useRef(handler);

  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  useEffect(() => {
    const stableHandler = (eventName: string, payload: any) => {
      handlerRef.current(eventName, payload);
    };

    const unsubscribe = chartEventBus.onPattern(pattern, stableHandler);

    return () => {
      unsubscribe();
    };
  }, [pattern, ...dependencies]);
}

/**
 * Hook for one-time event subscription
 */
export function useChartEventOnce<K extends ChartEventName>(
  eventName: K,
  handler: (payload: ChartEventTypes[K]) => void,
  condition: boolean = true
): void {
  const handlerRef = useRef(handler);

  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  useEffect(() => {
    if (!condition) return;

    const stableHandler = (payload: ChartEventTypes[K]) => {
      handlerRef.current(payload);
    };

    chartEventBus.once(eventName, stableHandler);
  }, [eventName, condition]);
}

/**
 * Hook that provides event emission functions
 */
export function useChartEventEmitters() {
  return useCallback(() => ({
    emitStreamingUpdate: (data: any, source: 'websocket' | 'generator' | 'api' = 'generator') =>
      chartEventBus.emit('data.streaming.update', {
        timestamp: Date.now(),
        data,
        source
      }),

    emitSeriesCreated: (seriesId: string, seriesType: 'line' | 'moving-average' | 'candlestick', view: any, config: any = {}) =>
      chartEventBus.emit('series.created', {
        timestamp: Date.now(),
        seriesId,
        seriesType,
        view,
        config
      }),

    emitSeriesRemoved: (seriesId: string, seriesType: string) =>
      chartEventBus.emit('series.removed', {
        timestamp: Date.now(),
        seriesId,
        seriesType
      }),

    emitVisibilityChanged: (seriesId: string, visible: boolean) =>
      chartEventBus.emit('series.visibility.changed', {
        timestamp: Date.now(),
        seriesId,
        visible
      }),

    emitRangeChanged: (oldRange: any, newRange: any, data: any) =>
      chartEventBus.emit('data.range.changed', {
        timestamp: Date.now(),
        oldRange,
        newRange,
        data
      })
  }), []);
}

/**
 * Hook for performance monitoring
 */
export function useChartPerformanceMonitor(
  onPerformanceUpdate?: (metrics: any) => void
): void {
  useChartEvent('performance.update', 
    useCallback((payload) => {
      if (onPerformanceUpdate) {
        onPerformanceUpdate(payload);
      }
    }, [onPerformanceUpdate])
  );
}

/**
 * Debug hook to log all chart events
 */
export function useChartEventDebugger(enabled: boolean = false): void {
  useChartEventPattern('**', 
    useCallback((eventName: string, payload: any) => {
      if (enabled) {
        // Chart event debugger
      }
    }, [enabled]),
    [enabled]
  );
}

/**
 * Kalshi WebSocket Manager Component using TypeScript RxJS client
 */

import React, { useEffect, useState } from 'react';
import { 
  useKalshiClient, 
  useKalshiOrderbook, 
  useKalshiTrades, 
  useKalshiTickers 
} from '@/lib/kalshi/hooks';
import { Environment, KALSHI_CHANNELS } from '@/lib/kalshi';

interface KalshiWebsocketProps {
  marketTicker?: string;
  environment?: Environment;
  autoConnect?: boolean;
}

export function KalshiWebsocket({ 
  marketTicker = 'PRESWIN24',
  environment = Environment.DEMO,
  autoConnect = true 
}: KalshiWebsocketProps) {
  const [selectedMarket, setSelectedMarket] = useState(marketTicker);
  
  const {
    client,
    isConnected,
    isConnecting,
    error,
    connect,
    disconnect,
    subscribe,
    unsubscribe
  } = useKalshiClient({
    environment,
    autoConnect,
    // Note: In production, these should come from environment variables
    // keyId: process.env.KALSHI_API_KEY,
    // privateKey: process.env.KALSHI_PRIVATE_KEY,
  });

  const orderbook = useKalshiOrderbook(client, selectedMarket);
  const trades = useKalshiTrades(client, selectedMarket);
  const tickers = useKalshiTickers(client, selectedMarket);

  // Subscribe to market data when connected
  useEffect(() => {
    if (isConnected && selectedMarket) {
      const subscriptions = [
        { channels: [KALSHI_CHANNELS.ORDERBOOK_DELTA], marketTickers: [selectedMarket] },
        { channels: [KALSHI_CHANNELS.TRADE], marketTickers: [selectedMarket] },
        { channels: [KALSHI_CHANNELS.TICKER], marketTickers: [selectedMarket] },
      ];

      subscriptions.forEach(sub => {
        subscribe(sub).catch(console.error);
      });

      return () => {
        subscriptions.forEach(sub => {
          unsubscribe(sub).catch(console.error);
        });
      };
    }
  }, [isConnected, selectedMarket, subscribe, unsubscribe]);

  const handleMarketChange = (newMarket: string) => {
    setSelectedMarket(newMarket);
  };

  const handleConnect = () => {
    connect().catch(console.error);
  };

  const handleDisconnect = () => {
    disconnect();
  };

  return (
    <div className="p-4 border rounded-lg bg-card">
      <div className="mb-4">
        <h3 className="text-lg font-semibold mb-2">Kalshi WebSocket Client</h3>
        
        {/* Connection Status */}
        <div className="flex items-center gap-2 mb-2">
          <div 
            className={`w-3 h-3 rounded-full ${
              isConnected ? 'bg-green-500' : 
              isConnecting ? 'bg-yellow-500' : 
              'bg-red-500'
            }`}
          />
          <span className="text-sm">
            {isConnected ? 'Connected' : 
             isConnecting ? 'Connecting...' : 
             'Disconnected'}
          </span>
        </div>

        {/* Environment */}
        <div className="text-sm text-muted-foreground mb-2">
          Environment: {environment.toUpperCase()}
        </div>

        {/* Error Display */}
        {error && (
          <div className="text-sm text-red-500 mb-2 p-2 bg-red-50 rounded">
            Error: {error.message}
          </div>
        )}

        {/* Controls */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={handleConnect}
            disabled={isConnected || isConnecting}
            className="px-3 py-1 text-sm bg-green-500 text-white rounded disabled:bg-gray-300"
          >
            Connect
          </button>
          <button
            onClick={handleDisconnect}
            disabled={!isConnected}
            className="px-3 py-1 text-sm bg-red-500 text-white rounded disabled:bg-gray-300"
          >
            Disconnect
          </button>
        </div>

        {/* Market Selector */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1">Market Ticker:</label>
          <input
            type="text"
            value={selectedMarket}
            onChange={(e) => handleMarketChange(e.target.value)}
            className="px-2 py-1 border rounded text-sm w-48"
            placeholder="Enter market ticker"
          />
        </div>
      </div>

      {/* Data Display */}
      {isConnected && (
        <div className="space-y-4">
          {/* Latest Ticker */}
          {tickers.latest && (
            <div>
              <h4 className="font-medium mb-2">Latest Ticker</h4>
              <div className="text-sm bg-gray-50 p-2 rounded">
                <div>Market: {tickers.latest.market_ticker}</div>
                <div>Yes: {tickers.latest.yes || 'N/A'}</div>
                <div>No: {tickers.latest.no || 'N/A'}</div>
                <div>Timestamp: {new Date(tickers.latest.ts).toLocaleString()}</div>
              </div>
            </div>
          )}

          {/* Latest Orderbook */}
          {orderbook.latestSnapshot && (
            <div>
              <h4 className="font-medium mb-2">Orderbook Snapshot</h4>
              <div className="text-sm bg-gray-50 p-2 rounded">
                <div>Market: {orderbook.latestSnapshot.market_ticker}</div>
                <div>Yes Orders: {orderbook.latestSnapshot.yes?.length || 0}</div>
                <div>No Orders: {orderbook.latestSnapshot.no?.length || 0}</div>
                <div>Timestamp: {new Date(orderbook.latestSnapshot.ts).toLocaleString()}</div>
              </div>
            </div>
          )}

          {/* Recent Trades */}
          {trades.data.length > 0 && (
            <div>
              <h4 className="font-medium mb-2">Recent Trades ({trades.data.length})</h4>
              <div className="max-h-40 overflow-y-auto">
                {trades.data.slice(-5).reverse().map((trade, index) => (
                  <div key={index} className="text-sm bg-gray-50 p-2 rounded mb-1">
                    <div className="flex justify-between">
                      <span>{trade.market_ticker}</span>
                      <span className={trade.side === 'yes' ? 'text-green-600' : 'text-red-600'}>
                        {trade.side.toUpperCase()}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Price: ¢{trade.price}</span>
                      <span>Size: {trade.count}</span>
                    </div>
                    <div className="text-xs text-gray-500">
                      {new Date(trade.ts).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Connection Info */}
          <div className="text-xs text-gray-500">
            <div>Orderbook Updates: {orderbook.deltas.length}</div>
            <div>Total Trades: {trades.data.length}</div>
            <div>Total Tickers: {tickers.data.length}</div>
          </div>
        </div>
      )}
    </div>
  );
}



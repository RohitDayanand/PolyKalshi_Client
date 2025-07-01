'use client'

import React, { useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { useRxJSChannelWithRedux } from '../lib/store/useRxJSChannelWithRedux'
import { callSubscriptionAPI, selectSubscriptions, selectIsLoading } from '../lib/store/apiSubscriptionSlice'
import { getRxJSStats } from '../lib/store/rxjsSubscriptionMiddleware'
import { Card, CardHeader, CardTitle, CardContent } from './ui/card'
import { Button } from './ui/button'

export function RxJSDebugPanel() {
  const dispatch = useDispatch()
  const subscriptions = useSelector(selectSubscriptions)
  const isLoading = useSelector(selectIsLoading)
  const [selectedMarket, setSelectedMarket] = useState<string>('')
  const [stats, setStats] = useState<any>(null)

  // Example RxJS channel subscription
  const { 
    data, 
    lastUpdate, 
    isConnected, 
    isMarketSubscribed, 
    subscriptionStatus,
    backendMarketId 
  } = useRxJSChannelWithRedux(selectedMarket, 'yes', '1D', { autoReplay: true })

  const handleSubscribeKalshi = () => {
    const market = {
      id: 'test-kalshi-market',
      title: 'Test Kalshi Market',
      kalshiTicker: 'EXAMPLE-24'
    }
    
    dispatch(callSubscriptionAPI({ 
      platform: 'kalshi', 
      market 
    }) as any)
    
    setSelectedMarket('test-kalshi-market')
  }

  const handleSubscribePolymarket = () => {
    const market = {
      id: 'test-poly-market',
      title: 'Test Polymarket Market',
      tokenIds: ['12345', '67890']
    }
    
    dispatch(callSubscriptionAPI({ 
      platform: 'polymarket', 
      market 
    }) as any)
    
    setSelectedMarket('test-poly-market')
  }

  const refreshStats = () => {
    setStats(getRxJSStats())
  }

  const subscriptionList = Object.entries(subscriptions)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>RxJS Channel Debug</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-x-2">
            <Button 
              onClick={handleSubscribeKalshi}
              disabled={isLoading}
              variant="outline"
            >
              Subscribe Kalshi
            </Button>
            <Button 
              onClick={handleSubscribePolymarket}
              disabled={isLoading}
              variant="outline"
            >
              Subscribe Polymarket
            </Button>
            <Button 
              onClick={refreshStats}
              variant="outline"
            >
              Refresh Stats
            </Button>
          </div>

          <div className="space-y-2">
            <p><strong>Selected Market:</strong> {selectedMarket || 'None'}</p>
            <p><strong>Backend Market ID:</strong> {backendMarketId || 'None'}</p>
            <p><strong>WebSocket Connected:</strong> {isConnected ? '✅' : '❌'}</p>
            <p><strong>Market Subscribed:</strong> {isMarketSubscribed ? '✅' : '❌'}</p>
            <p><strong>Subscription Status:</strong> {subscriptionStatus || 'None'}</p>
            <p><strong>Data Points:</strong> {data.length}</p>
            <p><strong>Last Update:</strong> {lastUpdate ? new Date(lastUpdate.time * 1000).toLocaleTimeString() : 'None'}</p>
          </div>

          {lastUpdate && (
            <div className="bg-gray-100 p-2 rounded">
              <p><strong>Latest Data:</strong></p>
              <pre className="text-xs">{JSON.stringify(lastUpdate, null, 2)}</pre>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Redux Subscriptions</CardTitle>
        </CardHeader>
        <CardContent>
          {subscriptionList.length === 0 ? (
            <p>No subscriptions</p>
          ) : (
            <div className="space-y-2">
              {subscriptionList.map(([frontendId, subscription]) => (
                <div key={frontendId} className="border p-2 rounded">
                  <p><strong>Frontend ID:</strong> {frontendId}</p>
                  <p><strong>Backend ID:</strong> {(subscription as any).backend_market_id}</p>
                  <p><strong>Platform:</strong> {(subscription as any).platform}</p>
                  <p><strong>Status:</strong> {(subscription as any).status}</p>
                  <Button
                    size="sm"
                    onClick={() => setSelectedMarket(frontendId)}
                    disabled={selectedMarket === frontendId}
                  >
                    {selectedMarket === frontendId ? 'Selected' : 'Select'}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {stats && (
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>RxJS Channel Stats</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p><strong>Total Channels:</strong> {stats.totalChannels}</p>
                <p><strong>Active Channels:</strong> {stats.activeChannels}</p>
                <p><strong>Total Cache Size:</strong> {stats.totalCacheSize}</p>
                <p><strong>WebSocket Connected:</strong> {stats.websocketConnected ? '✅' : '❌'}</p>
              </div>
              <div>
                <p><strong>Channels:</strong></p>
                <div className="max-h-40 overflow-y-auto">
                  {stats.channels.map((channel: any) => (
                    <div key={channel.channelKey} className="text-xs border-b py-1">
                      <p><strong>{channel.channelKey}</strong></p>
                      <p>Cache: {channel.cacheSize}, Throttle: {channel.throttleMs}ms</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
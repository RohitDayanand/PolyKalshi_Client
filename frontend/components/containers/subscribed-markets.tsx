"use client"

import { useMarketSubscription } from "@/lib/store/marketSubscriptionHooks"
import { useAppSelector } from "@/lib/store/hooks"
import { selectSubscriptions } from "@/lib/store/apiSubscriptionSlice"
import { useState, useEffect } from "react"
import type { Market } from "@/types/market"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Trash2, Eye, Wifi, WifiOff, AlertCircle } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"

export function SubscribedMarkets() {
  const { isWebSocketConnected } = useMarketSubscription()
  const subscriptions = useAppSelector(selectSubscriptions)
  
  // Convert Redux subscriptions to Market format
  const subscribedMarkets: Market[] = Object.values(subscriptions)
    .filter(sub => sub.status === 'connected' || sub.status === 'receiving_data' || sub.status === 'websocket_connected')
    .map(sub => ({
      id: sub.original_market_id,
      title: sub.market_title,
      category: 'General',
      volume: 0,
      platform: sub.platform as "polymarket" | "kalshi"
    }))

  const getConnectionIcon = (marketId: string) => {
    const state = subscriptions[marketId]
    if (!isWebSocketConnected) {
      return <WifiOff className="h-3 w-3 text-red-500" />
    }
    if (!state) {
      return <AlertCircle className="h-3 w-3 text-yellow-500" />
    }
    if (state.status === 'connected' || state.status === 'receiving_data') {
      return <Wifi className="h-3 w-3 text-green-500" />
    }
    return <AlertCircle className="h-3 w-3 text-yellow-500" />
  }

  const getConnectionStatus = (marketId: string) => {
    if (!isWebSocketConnected) return "WebSocket disconnected"
    const state = subscriptions[marketId]
    if (!state) return "Unknown"
    return state.status
  }
  
  const unsubscribeFromMarket = async (marketId: string) => {
    try {
      console.log('🔍 Unsubscribing from market:', marketId)
      
      // TODO: Implement unsubscribe API call to backend
      // For now, just remove from Redux state (handled by action creators)
      
      console.log(`✅ Unsubscribed from market: ${marketId}`)
    } catch (error) {
      console.error('Error unsubscribing from market:', error)
    }
  }
  
  const setActiveMarkets = (markets: Market[]) => {
    // TODO: Implement active market selection logic
    console.log('Setting active markets:', markets)
  }

  if (subscribedMarkets.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Subscribed Markets</CardTitle>
        </CardHeader>
        <CardContent className="p-4 text-center text-muted-foreground">
          No subscribed markets. Search and add markets to visualize them.
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Subscribed Markets</CardTitle>
      </CardHeader>
      <CardContent className="p-2">
        <ScrollArea className="h-[300px]">
          <div className="space-y-2 p-2">
            {subscribedMarkets.map((market) => (
              <div key={market.id} className="flex items-start justify-between p-2 rounded-md hover:bg-muted">
                <div className="space-y-1">
                  <div className="font-medium text-sm">{market.title}</div>
                  <div className="flex items-center gap-2">
                    <Badge variant={market.platform === "polymarket" ? "default" : "secondary"} className="text-xs">
                      {market.platform}
                    </Badge>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      {getConnectionIcon(market.id)}
                      <span>{getConnectionStatus(market.id)}</span>
                    </div>
                  </div>
                </div>
                <div className="flex gap-1">
                  <Button size="icon" variant="ghost" onClick={() => setActiveMarkets([market])}>
                    <Eye className="h-4 w-4" />
                    <span className="sr-only">View</span>
                  </Button>
                  <Button size="icon" variant="ghost" onClick={() => unsubscribeFromMarket(market.id)}>
                    <Trash2 className="h-4 w-4" />
                    <span className="sr-only">Unsubscribe</span>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

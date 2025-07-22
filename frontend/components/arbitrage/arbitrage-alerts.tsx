"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Trash2, TrendingUp, TrendingDown, ArrowRight } from "lucide-react"

interface ArbitrageAlert {
  market_pair: string
  timestamp: string
  spread: number
  direction: "kalshi_to_polymarket" | "polymarket_to_kalshi"
  side: "yes" | "no"
  kalshi_price?: number
  polymarket_price?: number
  kalshi_market_id?: number
  polymarket_asset_id?: string
  confidence: number
}

interface ArbitrageAlertsProps {
  className?: string
}

export function ArbitrageAlerts({ className }: ArbitrageAlertsProps) {
  const [alerts, setAlerts] = useState<ArbitrageAlert[]>([])
  const [isConnected, setIsConnected] = useState(false)

  // Mock data for development - will be replaced with real WebSocket connection
  useEffect(() => {
    // Simulate some initial alerts for UI testing
    const mockAlerts: ArbitrageAlert[] = [
      {
        market_pair: "PRES24-DJT",
        timestamp: new Date().toISOString(),
        spread: 0.035,
        direction: "kalshi_to_polymarket",
        side: "yes",
        kalshi_price: 0.52,
        polymarket_price: 0.48,
        confidence: 1.0
      },
      {
        market_pair: "PRES24-HARRIS",
        timestamp: new Date(Date.now() - 300000).toISOString(),
        spread: 0.022,
        direction: "polymarket_to_kalshi", 
        side: "no",
        kalshi_price: 0.45,
        polymarket_price: 0.47,
        confidence: 1.0
      }
    ]
    setAlerts(mockAlerts)
  }, [])

  // TODO: Implement WebSocket connection for real-time alerts
  // useEffect(() => {
  //   const ws = new WebSocket('ws://localhost:8000/ws/ticker')
  //   
  //   ws.onopen = () => setIsConnected(true)
  //   ws.onclose = () => setIsConnected(false)
  //   ws.onmessage = (event) => {
  //     const data = JSON.parse(event.data)
  //     if (data.type === 'arbitrage_alert') {
  //       setAlerts(prev => [data, ...prev].slice(0, 50)) // Keep only last 50 alerts
  //     }
  //   }
  //   
  //   return () => ws.close()
  // }, [])

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  const formatSpread = (spread: number) => {
    return `${(spread * 100).toFixed(2)}%`
  }

  const formatPrice = (price?: number) => {
    return price ? `$${price.toFixed(3)}` : "N/A"
  }

  const getDirectionIcon = (direction: string) => {
    if (direction === "kalshi_to_polymarket") {
      return <ArrowRight className="h-4 w-4 text-blue-500" />
    }
    return <ArrowRight className="h-4 w-4 text-green-500 rotate-180" />
  }

  const getDirectionText = (direction: string) => {
    return direction === "kalshi_to_polymarket" ? "K → P" : "P → K"
  }

  const getSideColor = (side: string) => {
    return side === "yes" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
  }

  const clearAlerts = () => {
    setAlerts([])
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg">Arbitrage Alerts</CardTitle>
            <div className="flex items-center gap-1">
              <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm text-muted-foreground">
                {isConnected ? 'Live' : 'Disconnected'}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{alerts.length} alerts</Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={clearAlerts}
              disabled={alerts.length === 0}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-64">
          {alerts.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-muted-foreground">
              No arbitrage alerts
            </div>
          ) : (
            <div className="space-y-2 p-4">
              {alerts.map((alert, index) => (
                <div
                  key={`${alert.market_pair}-${alert.timestamp}-${index}`}
                  className="flex items-center justify-between p-3 border rounded-lg bg-card hover:bg-accent/50 transition-colors font-mono text-sm"
                >
                  <div className="flex items-center gap-3 flex-1">
                    <span className="text-xs text-muted-foreground w-16">
                      {formatTimestamp(alert.timestamp)}
                    </span>
                    <span className="font-medium w-24 truncate">
                      {alert.market_pair}
                    </span>
                    <div className="flex items-center gap-1">
                      {getDirectionIcon(alert.direction)}
                      <span className="text-xs">
                        {getDirectionText(alert.direction)}
                      </span>
                    </div>
                    <Badge className={getSideColor(alert.side)} variant="secondary">
                      {alert.side.toUpperCase()}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground">Spread</div>
                      <div className="font-semibold text-green-600">
                        {formatSpread(alert.spread)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground">K / P</div>
                      <div>
                        {formatPrice(alert.kalshi_price)} / {formatPrice(alert.polymarket_price)}
                      </div>
                    </div>
                    <div className="w-8 flex justify-center">
                      {alert.spread > 0.03 ? (
                        <TrendingUp className="h-4 w-4 text-green-500" />
                      ) : (
                        <TrendingDown className="h-4 w-4 text-yellow-500" />
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
"use client"

import { useMarketSubscription, useWebSocketMessages } from "@/lib/store/marketSubscriptionHooks"
import { useAppSelector } from "@/lib/store/hooks"
import { selectSubscriptions } from "@/lib/store/apiSubscriptionSlice"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Trash2, Wifi, WifiOff, Activity } from "lucide-react"
import { useState } from "react"

export function WebSocketDebug() {
  const { 
    isWebSocketConnected,
    recentMessages,
    clearWebSocketMessages
  } = useMarketSubscription()
  
  const websocketMessages = useWebSocketMessages()
  const subscriptions = useAppSelector(selectSubscriptions)
  
  const [isExpanded, setIsExpanded] = useState(false)

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  const getMessageTypeColor = (type: string) => {
    switch (type) {
      case 'ticker_update': return 'bg-green-100 text-green-800'
      case 'connection_status': return 'bg-blue-100 text-blue-800'
      case 'error': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="h-4 w-4" />
            WebSocket Debug Panel
            {isWebSocketConnected ? (
              <Wifi className="h-4 w-4 text-green-500" />
            ) : (
              <WifiOff className="h-4 w-4 text-red-500" />
            )}
          </CardTitle>
          <div className="flex gap-2">
            <Button 
              size="sm" 
              variant="outline" 
              onClick={() => setIsExpanded(!isExpanded)}
            >
              {isExpanded ? 'Collapse' : 'Expand'}
            </Button>
            <Button 
              size="sm" 
              variant="outline" 
              onClick={clearWebSocketMessages}
              disabled={websocketMessages.length === 0}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Connection Status */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="font-medium">WebSocket Status:</span>
            <Badge variant={isWebSocketConnected ? "default" : "destructive"} className="ml-2">
              {isWebSocketConnected ? "Connected" : "Disconnected"}
            </Badge>
          </div>
          <div>
            <span className="font-medium">Messages:</span>
            <span className="ml-2">{websocketMessages.length}</span>
          </div>
        </div>

        {/* Market Connection States */}
        {Object.keys(subscriptions).length > 0 && (
          <div>
            <h4 className="font-medium text-sm mb-2">Market Connections:</h4>
            <div className="space-y-1">
              {Object.entries(subscriptions).map(([marketId, state]) => (
                <div key={marketId} className="flex items-center justify-between text-xs p-2 bg-muted rounded">
                  <span className="font-mono">{state.backend_market_id}</span>
                  <Badge 
                    variant={state.status === 'connected' || state.status === 'receiving_data' ? "default" : "secondary"}
                    className="text-xs"
                  >
                    {state.status}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {isExpanded && (
          <div>
            <h4 className="font-medium text-sm mb-2">Recent Messages:</h4>
            <ScrollArea className="h-[400px] border rounded p-2">
              {websocketMessages.length === 0 ? (
                <div className="text-center text-muted-foreground text-sm py-8">
                  No messages received yet. Subscribe to a market to see real-time updates.
                </div>
              ) : (
                <div className="space-y-2">
                  {websocketMessages.map((message, index) => (
                    <div key={index} className="border-l-2 border-gray-200 pl-3 py-2">
                      <div className="flex items-center justify-between mb-1">
                        <Badge className={`text-xs ${getMessageTypeColor(message.type)}`}>
                          {message.type}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(message.timestamp)}
                        </span>
                      </div>
                      
                      {message.type === 'ticker_update' && (
                        <div className="text-xs space-y-1">
                          <div><strong>Market:</strong> {message.market_id}</div>
                          <div><strong>Platform:</strong> {message.platform}</div>
                          {message.summary_stats.yes && (
                            <div><strong>YES:</strong> Bid: {message.summary_stats.yes.bid}, Ask: {message.summary_stats.yes.ask}, Vol: {message.summary_stats.yes.volume}</div>
                          )}
                          {message.summary_stats.no && (
                            <div><strong>NO:</strong> Bid: {message.summary_stats.no.bid}, Ask: {message.summary_stats.no.ask}, Vol: {message.summary_stats.no.volume}</div>
                          )}
                        </div>
                      )}
                      
                      {message.type === 'connection_status' && (
                        <div className="text-xs space-y-1">
                          <div><strong>Market:</strong> {message.market_id}</div>
                          <div><strong>Status:</strong> {message.status}</div>
                          {message.retry_attempt && (
                            <div><strong>Retry:</strong> {message.retry_attempt}</div>
                          )}
                        </div>
                      )}
                      
                      {message.type === 'error' && (
                        <div className="text-xs">
                          <strong>Error:</strong> {message.message}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
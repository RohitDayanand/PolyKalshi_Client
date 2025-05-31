"use client"

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { RefreshCw, Database, Clock, Check, X } from 'lucide-react'
import { marketSearchService } from '@/lib/search-service'
import type { SelectedToken } from '@/lib/market-cache'

interface CacheStats {
  marketCount: number
  selectedTokenCount: number
  lastUpdate: string
  cacheAge: number
  isStale: boolean
}

export function CacheDebugPanel() {
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null)
  const [selectedTokens, setSelectedTokens] = useState<SelectedToken[]>([])
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [lastRefresh, setLastRefresh] = useState<string>('')

  const loadCacheData = async () => {
    try {
      const stats = await marketSearchService.getCacheStats()
      const tokens = await marketSearchService.getSelectedTokens()
      
      setCacheStats(stats)
      setSelectedTokens(tokens)
    } catch (error) {
      console.error('Failed to load cache data:', error)
    }
  }

  const handleRefreshCache = async () => {
    setIsRefreshing(true)
    try {
      // Trigger a search to refresh cache
      await marketSearchService.searchPolymarketQuestions('test')
      setLastRefresh(new Date().toLocaleTimeString())
      await loadCacheData()
    } catch (error) {
      console.error('Failed to refresh cache:', error)
    } finally {
      setIsRefreshing(false)
    }
  }

  const clearSelectedTokens = async () => {
    if (typeof window !== 'undefined') {
      const cache = require('@/lib/browser-market-cache').browserMarketCache
      cache.clearCache()
      await loadCacheData()
    }
  }

  const formatTimeAgo = (timestamp: string) => {
    const now = new Date()
    const time = new Date(timestamp)
    const diffMs = now.getTime() - time.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays}d ago`
  }

  useEffect(() => {
    loadCacheData()
    // Disable automatic polling to prevent constant API calls
    // const interval = setInterval(() => {
    //   loadCacheData()
    // }, 30000) // Update every 30 seconds
    // return () => clearInterval(interval)
  }, [])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base font-medium">Cache Status</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshCache}
            disabled={isRefreshing}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {cacheStats ? (
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center space-x-2">
                <Database className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">Markets: {cacheStats.marketCount}</span>
              </div>
              <div className="flex items-center space-x-2">
                <Check className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">Tokens: {cacheStats.selectedTokenCount}</span>
              </div>
              <div className="flex items-center space-x-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">
                  Updated: {formatTimeAgo(cacheStats.lastUpdate)}
                </span>
              </div>
              <div className="flex items-center space-x-2">
                {cacheStats.isStale ? (
                  <X className="h-4 w-4 text-red-500" />
                ) : (
                  <Check className="h-4 w-4 text-green-500" />
                )}
                <span className="text-sm">
                  {cacheStats.isStale ? 'Stale' : 'Fresh'}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Loading cache stats...</p>
          )}
          
          {lastRefresh && (
            <p className="text-xs text-muted-foreground">
              Last refresh: {lastRefresh}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base font-medium">
            Selected Tokens ({selectedTokens.length})
          </CardTitle>
          {selectedTokens.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={clearSelectedTokens}
            >
              Clear All
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {selectedTokens.length > 0 ? (
            <div className="space-y-3 max-h-60 overflow-y-auto">
              {selectedTokens.slice(0, 10).map((token, index) => (
                <div key={`${token.marketId}-${token.tokenId}`} className="space-y-2">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {token.marketTitle}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="secondary" className="text-xs">
                          {token.outcomeName}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          Token: {token.tokenId.substring(0, 8)}...
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Selected: {formatTimeAgo(token.selectedAt)}
                      </p>
                    </div>
                  </div>
                  {index < selectedTokens.length - 1 && index < 9 && (
                    <Separator />
                  )}
                </div>
              ))}
              {selectedTokens.length > 10 && (
                <p className="text-xs text-muted-foreground text-center py-2">
                  ...and {selectedTokens.length - 10} more
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No tokens selected yet. Search and click on markets to select them.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">CLOB API Info</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="text-sm">
            <p><strong>Endpoint:</strong> https://clob.polymarket.com</p>
            <p><strong>Update Interval:</strong> Every 1 minute</p>
            <p><strong>Cache Lifetime:</strong> 30 minutes</p>
            <p><strong>Max Markets:</strong> 300</p>
            <p><strong>Storage:</strong> Browser localStorage</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

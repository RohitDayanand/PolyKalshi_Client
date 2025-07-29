"use client"

import React, { useState } from "react"
import { useMarketSubscription } from "@/lib/store/marketSubscriptionHooks"
import { useAppDispatch } from "@/lib/store/hooks"
import { startLoading, stopLoading } from "@/lib/store/loadingBarSlice"
import { useFirstDataEmission } from "@/hooks/useFirstDataEmission"
import { useStreamingSearch } from "@/hooks/useStreamingSearch"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PlusCircle, Search, Loader2, Check, X } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { SearchProgress } from "@/components/ui/search-progress"
import { useToast } from "@/hooks/use-toast"
import type { Market } from "@/types/market"

interface MarketListProps {
  platform: "polymarket" | "kalshi"
  onSearchLoadingChange?: (platform: "polymarket" | "kalshi", isLoading: boolean) => void
}

export function MarketList({ platform, onSearchLoadingChange }: MarketListProps) {
  const [query, setQuery] = useState("")
  const [selectedMarkets, setSelectedMarkets] = useState<Set<string>>(new Set())
  const { subscribeToMarket, subscriptions } = useMarketSubscription()
  const dispatch = useAppDispatch()
  const { toast } = useToast()
  
  // Hook to listen for first data emissions
  useFirstDataEmission()
  
  // Use streaming search hook
  const { search, cancelSearch, isLoading, progress, results, error } = useStreamingSearch()
  
  // Notify parent of loading state changes
  React.useEffect(() => {
    onSearchLoadingChange?.(platform, isLoading)
  }, [isLoading, platform, onSearchLoadingChange])

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      await search(platform, query.trim())
    }
  }

  const handleCancelSearch = () => {
    cancelSearch()
  }

  /*
  * Handle the add button by subscribing to market using WebSocket
  */
  const handleMarketAdd = async (market: Market) => {
    try {
      // Check subscription limit (max 2 total subscriptions)
      const currentSubscriptionCount = Object.keys(subscriptions).length
      if (currentSubscriptionCount >= 2) {
        toast({
          title: "Subscription Limit Reached",
          description: "Maximum 2 market subscriptions allowed. Please unsubscribe from a market first.",
          variant: "destructive"
        })
        return
      }

      // Validate that market has required token data IF polymarket
      if (market.platform == "polymarket" && (!market.tokenIds || market.tokenIds.length === 0)) {
        console.warn('❌ No tokenIds found for polymarket market:', market.id)
        return
      }
      
      console.log('🔍 DEBUG: Adding market with tokenIds:', market.tokenIds)
      
      // Start loading bar
      dispatch(startLoading({ marketId: market.id, platform }))
      
      // Subscribe to the market for WebSocket data and backend ticker
      await subscribeToMarket(platform, market)
      
      // Note: Loading bar will be stopped by useFirstDataEmission hook when first data is received
      
      // Update local selection state
      setSelectedMarkets(prev => new Set([...prev, market.id]))
      
      console.log(`✅ Added market: ${market.title}`)
      console.log(`✅ Token IDs:`, market.tokenIds)
    } catch (error) {
      console.error('Error adding market:', error)
      // Stop loading bar on error
      dispatch(stopLoading())
    }
  }

  // Use results from streaming search
  const searchResultsToShow = results || []

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Search & Add {platform === 'polymarket' ? 'Polymarket' : 'Kalshi'} Markets</CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        {/* Search Form */}
        <form onSubmit={handleSearch} className="relative">
          <Input
            type="text"
            placeholder={`Search ${platform} markets...`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className={isLoading ? "pr-20" : "pr-10"}
            disabled={isLoading}
          />
          <div className="absolute right-0 top-0 h-full flex items-center">
            {isLoading && (
              <Button 
                type="button" 
                size="icon" 
                variant="ghost" 
                onClick={handleCancelSearch}
                className="h-full"
              >
                <X className="h-4 w-4" />
                <span className="sr-only">Cancel search</span>
              </Button>
            )}
            <Button 
              type="submit" 
              size="icon" 
              variant="ghost" 
              className="h-full"
              disabled={isLoading || !query.trim()}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              <span className="sr-only">
                {isLoading ? 'Searching...' : 'Search'}
              </span>
            </Button>
          </div>
        </form>

        {/* Progress Indicator */}
        {isLoading && progress && (
          <SearchProgress 
            stage={progress.stage}
            message={progress.message}
            progress={progress.progress}
          />
        )}

        {/* Error Display */}
        {error && (
          <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* Search Results */}
        {searchResultsToShow.length === 0 && !isLoading && query && !error && (
          <div className="text-center text-muted-foreground py-4">
            No markets found for "{query}". Try a different search term.
          </div>
        )}
        
        {searchResultsToShow.length === 0 && !query && !isLoading && (
          <div className="text-center text-muted-foreground py-4">
            Search for markets to add them to your dashboard.
          </div>
        )}

        {searchResultsToShow.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Found {searchResultsToShow.length} {platform} markets
            </p>
            <ScrollArea className="h-[400px]">
              <div className="space-y-2 p-2">
                {searchResultsToShow.map((market) => (
                  <div key={market.id} className="flex items-start justify-between p-3 rounded-md border hover:bg-accent transition-colors">
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <div className="font-medium text-sm">{market.title}</div>
                        {market.platform === 'kalshi' && market.yes_subtitle && (
                          <div className="text-xs text-muted-foreground italic">
                            {market.yes_subtitle}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        {market.volume && (
                          <span className="text-xs text-muted-foreground">
                            ${market.volume.toLocaleString()} volume
                          </span>
                        )}
                        {market.platform === 'kalshi' && market.price && (
                          <span className="text-xs text-muted-foreground">
                            {market.price}¢
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {selectedMarkets.has(market.id) && (
                        <Check className="h-4 w-4 text-green-500" />
                      )}
                      <Button 
                        size="icon" 
                        variant="ghost" 
                        onClick={() => handleMarketAdd(market)}
                        disabled={selectedMarkets.has(market.id) || Object.keys(subscriptions).length >= 2}
                      >
                        <PlusCircle className="h-4 w-4" />
                        <span className="sr-only">Add to dashboard</span>
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}

        {/* Selection Summary */}
        {selectedMarkets.size > 0 && (
          <div className="p-3 bg-muted rounded-lg">
            <p className="text-sm font-medium">
              {selectedMarkets.size} market{selectedMarkets.size === 1 ? '' : 's'} added to dashboard
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Token pairs stored for tracking • Markets added to visualization
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

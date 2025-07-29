"use client"

import type React from "react"

import { useState } from "react"
import { Search, Loader2, Check, X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { SearchProgress } from "@/components/ui/search-progress"
import { useMarketSubscription } from "@/lib/store/marketSubscriptionHooks"
import { useStreamingSearch } from "@/hooks/useStreamingSearch"
import { marketSearchService } from "@/lib/search-service"
import type { Market } from "@/types/market"

interface MarketSearchProps {
  platform: "polymarket" | "kalshi"
}

export function MarketSearch({ platform }: MarketSearchProps) {
  const [query, setQuery] = useState("")
  const [selectedMarkets, setSelectedMarkets] = useState<Set<string>>(new Set())
  const { subscribeToMarket } = useMarketSubscription()
  
  // Use streaming search hook
  const { search, cancelSearch, isLoading, progress, results, error } = useStreamingSearch()

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      await search(platform, query.trim())
    }
  }

  const handleCancelSearch = () => {
    cancelSearch()
  }

  const handleMarketSelect = async (market: Market) => {
    try {
      // First subscribe to the market for visualization
      subscribeToMarket(platform, market)
      
      // Then get the full market data with token information for storage
      const fullMarket = await marketSearchService.getMarket(market.id)
      
      if (fullMarket && fullMarket.clobTokenIds && fullMarket.clobTokenIds.length > 0) {
        // For binary markets, default to the first token (usually "Yes")
        const selectedTokenId = fullMarket.clobTokenIds[0]
        const outcome = fullMarket.outcomes?.[0] || { name: 'Yes' }
        
        // Store the selected token (this will store both tokens from the pair)
        await marketSearchService.storeSelectedToken(
          market.id,
          selectedTokenId,
          outcome.name,
          market.title
        )
        
        // Update local selection state
        setSelectedMarkets(prev => new Set([...prev, market.id]))
        
        console.log(`Selected market: ${market.title}`)
        console.log(`Token pair stored:`, fullMarket.clobTokenIds)
      } else {
        console.warn('No token IDs found for market:', market.id)
      }
    } catch (error) {
      console.error('Error selecting market:', error)
    }
  }

  // Use results from streaming search
  const markets = results || []

  return (
    <div className="space-y-4">
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
      {markets.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            Found {markets.length} {platform} markets
          </p>
          <div className="grid gap-2 max-h-96 overflow-y-auto">
            {markets.map((market) => (
              <Card 
                key={market.id} 
                className={`cursor-pointer transition-colors hover:bg-accent ${
                  selectedMarkets.has(market.id) ? 'ring-2 ring-primary' : ''
                }`}
                onClick={() => handleMarketSelect(market)}
              >
                <CardContent className="p-3">
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{market.title}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="secondary" className="text-xs">
                          {market.category}
                        </Badge>
                        {market.volume && (
                          <span className="text-xs text-muted-foreground">
                            ${market.volume.toLocaleString()} volume
                          </span>
                        )}
                        {market.price && (
                          <span className="text-xs text-muted-foreground">
                            ${market.price.toLocaleString()}
                          </span>
                        )}
                      </div>
                      {market.platform === 'kalshi' && market.yes_subtitle && (
                        <div className="text-xs text-muted-foreground italic mt-1">
                          {market.yes_subtitle}
                        </div>
                      )}
                    </div>
                    {selectedMarkets.has(market.id) && (
                      <Check className="h-5 w-5 text-primary flex-shrink-0" />
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
      
      {/* Selection Summary */}
      {selectedMarkets.size > 0 && (
        <div className="p-3 bg-muted rounded-lg">
          <p className="text-sm font-medium">
            {selectedMarkets.size} market{selectedMarkets.size === 1 ? '' : 's'} selected
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Token pairs have been stored for tracking
          </p>
        </div>
      )}
    </div>
  )
}

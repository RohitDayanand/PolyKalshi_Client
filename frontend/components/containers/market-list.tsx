"use client"

import { useState } from "react"
import { useMarketSubscription } from "@/lib/store/marketSubscriptionHooks"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PlusCircle, Search, Loader2, Check } from "lucide-react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import type { Market } from "@/types/market"

interface MarketListProps {
  platform: "polymarket" | "kalshi"
}

export function MarketList({ platform }: MarketListProps) {
  const [query, setQuery] = useState("")
  const [selectedMarkets, setSelectedMarkets] = useState<Set<string>>(new Set())
  const { subscribeToMarket } = useMarketSubscription()
  
  // Keep existing search functionality - only replace subscription logic
  const [searchResults, setSearchResults] = useState<{
    polymarket: Market[]
    kalshi: Market[]  
    loading: boolean
  }>({
    polymarket: [],
    kalshi: [],
    loading: false
  })
  
  // Keep existing search implementation
  const searchMarkets = async (platform: "polymarket" | "kalshi", query: string) => {
    setSearchResults(prev => ({ ...prev, loading: true }))
    
    try {
      const response = await fetch(`/api/search?platform=${platform}&query=${encodeURIComponent(query)}`)
      const data = await response.json()
      
      if (data.success) {
        setSearchResults(prev => ({
          ...prev,
          [platform]: data.data,
          loading: false,
        }))
      } else {
        console.error('Search failed:', data.error)
        setSearchResults(prev => ({ ...prev, loading: false }))
      }
    } catch (error) {
      console.error('Search API error:', error)
      setSearchResults(prev => ({ ...prev, loading: false }))
    }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      await searchMarkets(platform, query.trim())
    }
  }

  /*
  * Handle the add button by subscribing to market using WebSocket
  */
  const handleMarketAdd = async (market: Market) => {
    try {
      // Validate that market has required token data IF polymarket
      if (market.platform == "polymarket" && (!market.tokenIds || market.tokenIds.length === 0)) {
        console.warn('❌ No tokenIds found for polymarket market:', market.id)
        return
      }
      
      console.log('🔍 DEBUG: Adding market with tokenIds:', market.tokenIds)
      
      // Subscribe to the market for WebSocket data and backend ticker
      await subscribeToMarket(platform, market)
      
      // Update local selection state
      setSelectedMarkets(prev => new Set([...prev, market.id]))
      
      console.log(`✅ Added market: ${market.title}`)
      console.log(`✅ Token IDs:`, market.tokenIds)
    } catch (error) {
      console.error('Error adding market:', error)
    }
  }

  const results = searchResults[platform] || []
  const isLoading = searchResults.loading

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
            className="pr-10"
            disabled={isLoading}
          />
          <Button 
            type="submit" 
            size="icon" 
            variant="ghost" 
            className="absolute right-0 top-0 h-full"
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
        </form>

        {/* Search Results */}
        {results.length === 0 && !isLoading && query && (
          <div className="text-center text-muted-foreground py-4">
            No markets found for "{query}". Try a different search term.
          </div>
        )}
        
        {results.length === 0 && !query && (
          <div className="text-center text-muted-foreground py-4">
            Search for markets to add them to your dashboard.
          </div>
        )}

        {isLoading && (
          <div className="text-center text-muted-foreground py-4">
            Searching {platform} markets...
          </div>
        )}

        {results.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Found {results.length} {platform} markets
            </p>
            <ScrollArea className="h-[400px]">
              <div className="space-y-2 p-2">
                {results.map((market) => (
                  <div key={market.id} className="flex items-start justify-between p-3 rounded-md border hover:bg-accent transition-colors">
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="font-medium text-sm">{market.title}</div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          {market.category}
                        </Badge>
                        {market.volume && (
                          <span className="text-xs text-muted-foreground">
                            ${market.volume.toLocaleString()} volume
                          </span>
                        )}
                        {market.price && (
                          <span className="text-xs text-muted-foreground">
                            {(market.price * 100).toFixed(1)}%
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
                        disabled={selectedMarkets.has(market.id)}
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

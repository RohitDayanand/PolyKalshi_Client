"use client"

import { createContext, useContext, useState, type ReactNode } from "react"
import type { Market, SearchResults } from "@/types/market"
import { mockPolymarketSearch, mockKalshiSearch } from "@/lib/mock-data"

interface MarketContextType {
  searchResults: {
    polymarket: Market[]
    kalshi: Market[]
    loading: boolean
  }
  subscribedMarkets: Market[]
  activeMarkets: Market[]
  searchMarkets: (platform: "polymarket" | "kalshi", query: string) => void
  subscribeToMarket: (platform: "polymarket" | "kalshi", market: Market) => void
  unsubscribeFromMarket: (marketId: string) => void
  setActiveMarkets: (markets: Market[]) => void
}

const MarketContext = createContext<MarketContextType | undefined>(undefined)

export function MarketProvider({ children }: { children: ReactNode }) {
  const [searchResults, setSearchResults] = useState<SearchResults>({
    polymarket: [],
    kalshi: [],
    loading: false,
  })

  const [subscribedMarkets, setSubscribedMarkets] = useState<Market[]>([])
  const [activeMarkets, setActiveMarkets] = useState<Market[]>([])

  const searchMarkets = async (platform: "polymarket" | "kalshi", query: string) => {
    setSearchResults((prev) => ({ ...prev, loading: true }))

    try {
      const response = await fetch(`/api/search?platform=${platform}&query=${encodeURIComponent(query)}`)
      const data = await response.json()
      
      if (data.success) {
        setSearchResults((prev) => ({
          ...prev,
          [platform]: data.data,
          loading: false,
        }))
      } else {
        console.error('Search failed:', data.error)
        setSearchResults((prev) => ({ ...prev, loading: false }))
      }
    } catch (error) {
      console.error('Search API error:', error)
      setSearchResults((prev) => ({ ...prev, loading: false }))
    }
  }

  const subscribeToMarket = (platform: "polymarket" | "kalshi", market: Market) => {
    // Check if already subscribed
    if (subscribedMarkets.some((m) => m.id === market.id)) {
      return
    }

    const marketWithPlatform = {
      ...market,
      platform,
    }

    setSubscribedMarkets((prev) => [...prev, marketWithPlatform])
  }

  const unsubscribeFromMarket = (marketId: string) => {
    setSubscribedMarkets((prev) => prev.filter((market) => market.id !== marketId))
    setActiveMarkets((prev) => prev.filter((market) => market.id !== marketId))
  }

  return (
    <MarketContext.Provider
      value={{
        searchResults,
        subscribedMarkets,
        activeMarkets,
        searchMarkets,
        subscribeToMarket,
        unsubscribeFromMarket,
        setActiveMarkets,
      }}
    >
      {children}
    </MarketContext.Provider>
  )
}

export function useMarketContext() {
  const context = useContext(MarketContext)
  if (context === undefined) {
    throw new Error("useMarketContext must be used within a MarketProvider")
  }
  return context
}

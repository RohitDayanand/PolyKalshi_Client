import type { Market } from "@/types/market"

// Mock data for Polymarket search
export function mockPolymarketSearch(query: string): Market[] {
  const polymarkets = [
    {
      id: "poly-1",
      title: "Will Trump win the 2024 election?",
      category: "Politics",
      volume: 2500000,
      liquidity: 1200000,
      price: 0.42,
    },
    {
      id: "poly-2",
      title: "Will Bitcoin exceed $100k in 2024?",
      category: "Crypto",
      volume: 1800000,
      liquidity: 900000,
      price: 0.65,
    },
    {
      id: "poly-3",
      title: "Will Ethereum merge to PoS in 2024?",
      category: "Crypto",
      volume: 1200000,
      liquidity: 600000,
      price: 0.88,
    },
    {
      id: "poly-4",
      title: "Will inflation exceed 5% in 2024?",
      category: "Economics",
      volume: 950000,
      liquidity: 450000,
      price: 0.32,
    },
    {
      id: "poly-5",
      title: "Will SpaceX reach Mars by 2026?",
      category: "Science",
      volume: 750000,
      liquidity: 350000,
      price: 0.18,
    },
  ]

  if (!query) return polymarkets

  const lowercaseQuery = query.toLowerCase()
  return polymarkets.filter(
    (market) =>
      market.title.toLowerCase().includes(lowercaseQuery) || market.category.toLowerCase().includes(lowercaseQuery),
  )
}

// Mock data for Kalshi search
export function mockKalshiSearch(query: string): Market[] {
  const kalshiMarkets = [
    {
      id: "kalshi-1",
      title: "Will Fed raise rates in Q3 2024?",
      category: "Economics",
      volume: 1800000,
      liquidity: 900000,
      price: 0.58,
    },
    {
      id: "kalshi-2",
      title: "Will US GDP grow >3% in 2024?",
      category: "Economics",
      volume: 1500000,
      liquidity: 750000,
      price: 0.42,
    },
    {
      id: "kalshi-3",
      title: "Will Democrats win the House in 2024?",
      category: "Politics",
      volume: 2200000,
      liquidity: 1100000,
      price: 0.51,
    },
    {
      id: "kalshi-4",
      title: "Will hurricane hit Florida in 2024?",
      category: "Weather",
      volume: 980000,
      liquidity: 490000,
      price: 0.72,
    },
    {
      id: "kalshi-5",
      title: "Will S&P 500 exceed 6000 in 2024?",
      category: "Finance",
      volume: 1650000,
      liquidity: 825000,
      price: 0.38,
    },
  ]

  if (!query) return kalshiMarkets

  const lowercaseQuery = query.toLowerCase()
  return kalshiMarkets.filter(
    (market) =>
      market.title.toLowerCase().includes(lowercaseQuery) || market.category.toLowerCase().includes(lowercaseQuery),
  )
}

// Generate mock price data for charts
export function generateMarketPriceData(markets: Market[], timeframe: string) {
  const dataPoints = getDataPointsForTimeframe(timeframe)
  const data = []

  for (let i = 0; i < dataPoints; i++) {
    const point: any = {
      time: getTimeLabel(i, dataPoints, timeframe),
    }

    markets.forEach((market) => {
      // Generate a price that fluctuates around the market's current price
      const basePrice = market.price || 0.5
      const randomFactor = 0.1 // 10% max fluctuation
      const fluctuation = (Math.random() * 2 - 1) * randomFactor
      const timeProgress = i / dataPoints

      // Create a trend based on the time progress
      let trendFactor = 0
      if (market.id.includes("poly")) {
        // Polymarket trends slightly up
        trendFactor = timeProgress * 0.15
      } else {
        // Kalshi trends slightly down
        trendFactor = -timeProgress * 0.1
      }

      point[market.id] = Math.max(0, Math.min(1, basePrice + fluctuation + trendFactor))
    })

    data.push(point)
  }

  return data
}

// Generate mock orderbook data
export function generateOrderbookData(market: Market) {
  const basePrice = market.price || 0.5
  const data = []

  // Generate 10 price levels on each side
  for (let i = -10; i <= 10; i++) {
    if (i === 0) continue // Skip the exact price point

    const priceOffset = i * 0.01
    const price = basePrice + priceOffset

    if (price <= 0 || price >= 1) continue

    // Higher volume near the current price
    const volumeFactor = Math.max(0.1, 1 - Math.abs(i) * 0.08)

    const point = {
      price,
      bids: i < 0 ? Math.round(Math.random() * 100 * volumeFactor) : 0,
      asks: i > 0 ? Math.round(Math.random() * 100 * volumeFactor) : 0,
    }

    data.push(point)
  }

  // Sort by price
  return data.sort((a, b) => a.price - b.price)
}

// Generate mock volume data
export function generateVolumeData(markets: Market[], timeframe: string) {
  const dataPoints = getDataPointsForTimeframe(timeframe)
  const data = []

  for (let i = 0; i < dataPoints; i++) {
    const point: any = {
      time: getTimeLabel(i, dataPoints, timeframe),
    }

    markets.forEach((market) => {
      // Base volume on the market's reported volume
      const baseVolume = market.volume || 1000000
      const dailyVolume = baseVolume / 30 // Approximate daily volume

      // Add some randomness
      const randomFactor = 0.3 // 30% max fluctuation
      const fluctuation = (Math.random() * 2 - 1) * randomFactor

      // Scale based on timeframe
      let timeframeScale = 1
      if (timeframe === "1h") timeframeScale = 1 / 24
      if (timeframe === "7d") timeframeScale = 7
      if (timeframe === "30d") timeframeScale = 30

      point[market.id] = Math.max(0, (dailyVolume * (1 + fluctuation) * timeframeScale) / dataPoints)
    })

    data.push(point)
  }

  return data
}

// Generate comparison data for scatter plot
export function generateComparisonData(markets: Market[], timeframe: string, metric1: string, metric2: string) {
  const data = []

  markets.forEach((market) => {
    // Generate 10 data points for each market
    for (let i = 0; i < 10; i++) {
      const point: any = {
        marketId: market.id,
        name: market.title,
      }

      // Generate values for each metric
      point.price = getMetricValue(market, "price", i)
      point.volume = getMetricValue(market, "volume", i)
      point.liquidity = getMetricValue(market, "liquidity", i)
      point.volatility = getMetricValue(market, "volatility", i)

      data.push(point)
    }
  })

  return data
}

// Helper function to get metric values
function getMetricValue(market: Market, metric: string, index: number) {
  const randomFactor = 0.2 // 20% max fluctuation
  const fluctuation = (Math.random() * 2 - 1) * randomFactor

  switch (metric) {
    case "price":
      return Math.max(0, Math.min(1, (market.price || 0.5) * (1 + fluctuation)))
    case "volume":
      return ((market.volume || 1000000) * (1 + fluctuation)) / 10
    case "liquidity":
      return ((market.liquidity || 500000) * (1 + fluctuation)) / 10
    case "volatility":
      // Generate a volatility value between 0.01 and 0.2
      return 0.01 + Math.random() * 0.19
    default:
      return 0
  }
}

// Helper function to get the number of data points based on timeframe
function getDataPointsForTimeframe(timeframe: string) {
  switch (timeframe) {
    case "1h":
      return 12 // 5-minute intervals
    case "24h":
      return 24 // Hourly intervals
    case "7d":
      return 28 // 6-hour intervals
    case "30d":
      return 30 // Daily intervals
    default:
      return 24
  }
}

// Helper function to generate time labels
function getTimeLabel(index: number, totalPoints: number, timeframe: string) {
  const now = new Date()
  let date: Date

  switch (timeframe) {
    case "1h":
      date = new Date(now.getTime() - (60 - index * 5) * 60 * 1000)
      return `${date.getHours().toString().padStart(2, "0")}:${date.getMinutes().toString().padStart(2, "0")}`
    case "24h":
      date = new Date(now.getTime() - (24 - index) * 60 * 60 * 1000)
      return `${date.getHours().toString().padStart(2, "0")}:00`
    case "7d":
      date = new Date(now.getTime() - (7 - index / 4) * 24 * 60 * 60 * 1000)
      return `${date.getMonth() + 1}/${date.getDate()}`
    case "30d":
      date = new Date(now.getTime() - (30 - index) * 24 * 60 * 60 * 1000)
      return `${date.getMonth() + 1}/${date.getDate()}`
    default:
      return index.toString()
  }
}

import mitt from 'mitt'
import { MarketDataPoint, MarketDataUpdate, SubscriptionConfig } from './chart-types'
import { generateBaselineSubscriptionConfigs, ALL_SUBSCRIPTION_IDS, getSubscriptionConfig } from './subscription-baseline'
import { CandlestickUpdateLength } from '../components/chart/Overlays/CandleStick'

/**
 * MARKET DATA EVENT EMITTER
 * 
 * Handles real-time market data streaming with:
 * - Rolling window caching (1000 points max)
 * - Multiple subscription frequencies per time range
 * - Initial data replay for new subscribers
 * - High-frequency update batching
 */

interface MarketDataCache {
  data: MarketDataPoint[]
  lastUpdate: number
  config: SubscriptionConfig
  intervalId?: NodeJS.Timeout
  subscriberCount: number // Track how many components are subscribed
}

// Simplified events for mitt compatibility
type Events = {
  'market-data': MarketDataUpdate
  'subscription-error': { subscriptionId: string; error: string }
}

// Raw data generation intervals that correspond to candlestick timeframes
const RAW_DATA_INTERVALS: CandlestickUpdateLength = {
  '1H': 60 * 1000,    // 10 seconds for hourly data (increased frequency)
  '1W': 150 * 1000,   // 150 seconds (2.5 min) for weekly data  
  '1M': 1500 * 1000,  // 1500 seconds (25 min) for monthly data
  '1Y': 24 * 60 * 60 * 1000 // 1 day for yearly data
}

export class MarketDataEmitter {
  private emitter = mitt<Events>()
  private subscriptions: Map<string, MarketDataCache> = new Map()
  private readonly HISTORY_LIMIT = 1000
  private baselineInitialized = false
  
  constructor() {
    console.log('📡 MarketDataEmitter initialized')
  }

  /**
   * BASELINE SETUP: Initialize all baseline subscription feeds
   * This creates live data streams for all time ranges and series types
   */
  initializeBaseline(): void {
    if (this.baselineInitialized) {
      console.log('⚠️ Baseline subscriptions already initialized')
      return
    }

    console.log('🚀 Initializing baseline subscription feeds...')
    const configs = generateBaselineSubscriptionConfigs()
    
    console.log(`📊 Creating ${configs.length} baseline subscriptions:`, configs.map(c => c.id))
    
    // Subscribe to all baseline feeds
    configs.forEach(config => {
      this.subscribe(config)
    })
    
    this.baselineInitialized = true
    console.log('✅ Baseline subscription feeds initialized')
    console.log('📋 Active subscriptions:', Array.from(this.subscriptions.keys()))
  }

  /**
   * Check if baseline subscriptions are initialized
   */
  isBaselineInitialized(): boolean {
    return this.baselineInitialized
  }

  /**
   * Get all available subscription IDs
   */
  getAvailableSubscriptions(): string[] {
    return Array.from(this.subscriptions.keys())
  }

  /**
   * STEP 1: Generate realistic initial historical data
   * Creates different patterns for each time range with bounds at 0.05 and 0.95
   */
  private generateInitialData(subscriptionId: string, pointCount: number = 100): MarketDataPoint[] {
    const now = Date.now()
    const data: MarketDataPoint[] = []
    
    // Determine if this is YES or NO series from subscription ID
    const isYesSeries = subscriptionId.includes('yes')
    const isNoSeries = subscriptionId.includes('no')
    
    // Determine time range from subscription ID
    const is1H = subscriptionId.includes('1H')
    const is1W = subscriptionId.includes('1W')
    const is1M = subscriptionId.includes('1M')
    const is1Y = subscriptionId.includes('1Y')
    
    // Different patterns based on time range
    let frequency: number
    let phaseShift: number
    let noiseAmplitude: number
    let patternType: 'sine' | 'sawtooth' | 'square' | 'triangle'
    let trendStrength: number
    
    if (is1H) {
      // 1H: High frequency sine waves (volatile short-term)
      frequency = isYesSeries ? 1.2 : 1.0
      phaseShift = isYesSeries ? 0 : Math.PI
      noiseAmplitude = 0.12 // High noise for short term
      patternType = 'sine'
      trendStrength = 0.1
    } else if (is1W) {
      // 1W: Sawtooth pattern (trending with reversals)
      frequency = isYesSeries ? 0.8 : 0.6
      phaseShift = isYesSeries ? 0 : Math.PI / 2
      noiseAmplitude = 0.08
      patternType = 'sawtooth'
      trendStrength = 0.2
    } else if (is1M) {
      // 1M: Square wave pattern (distinct phases)
      frequency = isYesSeries ? 0.5 : 0.4
      phaseShift = isYesSeries ? 0 : Math.PI
      noiseAmplitude = 0.06
      patternType = 'square'
      trendStrength = 0.15
    } else if (is1Y) {
      // 1Y: Triangle wave (smooth long-term trends)
      frequency = isYesSeries ? 0.3 : 0.25
      phaseShift = isYesSeries ? 0 : Math.PI / 3
      noiseAmplitude = 0.04 // Low noise for long term
      patternType = 'triangle'
      trendStrength = 0.3
    } else {
      // Default
      frequency = 0.7
      phaseShift = Math.PI / 2
      noiseAmplitude = 0.07
      patternType = 'sine'
      trendStrength = 0.1
    }
    
    // Determine time interval based on subscription type
    const timeInterval = this.getTimeIntervalForSubscription(subscriptionId)
    const startTime = now - (pointCount * timeInterval)

    for (let i = 0; i < pointCount; i++) {
      const progress = i / pointCount
      let waveValue: number
      
      // Generate different wave patterns based on range
      switch (patternType) {
        case 'sine':
          waveValue = Math.sin(progress * 2 * Math.PI * frequency + phaseShift)
          break
          
        case 'sawtooth':
          const sawtoothPos = (progress * frequency + phaseShift / (2 * Math.PI)) % 1
          waveValue = 2 * sawtoothPos - 1 // Convert to [-1, 1]
          break
          
        case 'square':
          const squarePos = (progress * frequency + phaseShift / (2 * Math.PI)) % 1
          waveValue = squarePos < 0.5 ? -1 : 1
          break
          
        case 'triangle':
          const trianglePos = (progress * frequency + phaseShift / (2 * Math.PI)) % 1
          waveValue = trianglePos < 0.5 ? 
            4 * trianglePos - 1 : // Rising edge
            3 - 4 * trianglePos   // Falling edge
          break
          
        default:
          waveValue = Math.sin(progress * 2 * Math.PI * frequency + phaseShift)
      }
      
      // Add long-term trend component
      const trendComponent = Math.sin(progress * Math.PI) * trendStrength * (isYesSeries ? 1 : -0.5)
      
      // Normalize wave to [0, 1] and scale to [0.05, 0.95]
      const normalizedWave = (waveValue + trendComponent + 1) / 2
      const scaledValue = 0.05 + normalizedWave * 0.9
      
      // Add range-specific noise and variation
      const randomNoise = (Math.random() - 0.5) * noiseAmplitude
      const microTrend = Math.sin(i / (15 / frequency)) * 0.02 // Scale micro trends with frequency
      
      // Combine components and ensure bounds
      const finalValue = Math.max(0.05, Math.min(0.95, 
        scaledValue + randomNoise + microTrend
      ))
      
      data.push({
        time: (startTime + i * timeInterval) / 1000,
        value: parseFloat(finalValue.toFixed(4))
      })
    }

    console.log(`📈 Generated ${pointCount} ${patternType} wave data for ${subscriptionId} (${isYesSeries ? 'YES' : isNoSeries ? 'NO' : 'OTHER'} ${is1H ? '1H' : is1W ? '1W' : is1M ? '1M' : is1Y ? '1Y' : 'DEFAULT'})`)
    return data
  }

  /**
   * STEP 2: Generate single update point with range-specific movement within bounds [0.05, 0.95]
   */
  private generateUpdatePoint(subscriptionId: string): MarketDataPoint {
    const cache = this.subscriptions.get(subscriptionId)
    if (!cache || cache.data.length === 0) {
      throw new Error(`No cache found for subscription: ${subscriptionId}`)
    }

    const lastPoint = cache.data[cache.data.length - 1]
    const now = Date.now() / 1000
    
    // Determine series type for different behaviors
    const isYesSeries = subscriptionId.includes('yes')
    const isNoSeries = subscriptionId.includes('no')
    
    // Determine time range for different volatility patterns
    const is1H = subscriptionId.includes('1H')
    const is1W = subscriptionId.includes('1W')
    const is1M = subscriptionId.includes('1M')
    const is1Y = subscriptionId.includes('1Y')
    
    // Range-specific volatility and movement parameters
    let baseVolatility: number
    let trendBias: number
    let bounceStrength: number
    let momentumFactor: number
    
    if (is1H) {
      // 1H: High volatility, frequent reversals
      baseVolatility = isYesSeries ? 0.025 : 0.02
      trendBias = isYesSeries ? 0.001 : -0.0005
      bounceStrength = 0.03
      momentumFactor = 0.8 // Lower momentum for more erratic movement
    } else if (is1W) {
      // 1W: Medium volatility, trending behavior
      baseVolatility = isYesSeries ? 0.018 : 0.015
      trendBias = isYesSeries ? 0.0008 : -0.0003
      bounceStrength = 0.025
      momentumFactor = 1.2 // Higher momentum for trends
    } else if (is1M) {
      // 1M: Lower volatility, phase-like movements
      baseVolatility = isYesSeries ? 0.012 : 0.01
      trendBias = isYesSeries ? 0.0005 : -0.0002
      bounceStrength = 0.02
      momentumFactor = 1.5 // Strong momentum for sustained moves
    } else if (is1Y) {
      // 1Y: Very low volatility, smooth long-term trends
      baseVolatility = isYesSeries ? 0.008 : 0.006
      trendBias = isYesSeries ? 0.0003 : -0.0001
      bounceStrength = 0.015
      momentumFactor = 2.0 // Very strong momentum for long-term trends
    } else {
      // Default
      baseVolatility = 0.015
      trendBias = 0
      bounceStrength = 0.02
      momentumFactor = 1.0
    }
    
    // Add boundary bounce effect - stronger movements away from edges
    let boundaryEffect = 0
    if (lastPoint.value > 0.85) {
      // Near upper bound - bias downward
      boundaryEffect = -bounceStrength * Math.pow((lastPoint.value - 0.85) / 0.1, 2)
    } else if (lastPoint.value < 0.15) {
      // Near lower bound - bias upward
      boundaryEffect = bounceStrength * Math.pow((0.15 - lastPoint.value) / 0.1, 2)
    }
    
    // Calculate momentum from recent price changes (range-specific lookback)
    let momentum = 0
    const lookbackPeriod = is1H ? 2 : is1W ? 3 : is1M ? 5 : 8 // Different momentum periods
    if (cache.data.length >= lookbackPeriod) {
      const recentChange = lastPoint.value - cache.data[cache.data.length - lookbackPeriod].value
      momentum = recentChange * (momentumFactor * 0.1)
    }
    
    // Generate range-specific price movement components
    const randomVolatility = (Math.random() - 0.5) * 2 * baseVolatility
    const microTrendFreq = is1H ? 8000 : is1W ? 12000 : is1M ? 20000 : 30000
    const microTrend = Math.sin(Date.now() / microTrendFreq) * (baseVolatility * 0.3)
    
    // Range-specific market sentiment (larger occasional moves)
    const sentimentChance = is1H ? 0.12 : is1W ? 0.08 : is1M ? 0.05 : 0.03
    const sentimentMagnitude = is1H ? 0.03 : is1W ? 0.025 : is1M ? 0.02 : 0.015
    const marketSentiment = (Math.random() < sentimentChance) ? 
      (Math.random() - 0.5) * sentimentMagnitude : 0
    
    const meanReversion = (0.5 - lastPoint.value) * (baseVolatility * 0.1) // Gentle pull toward middle
    
    // Combine all movement components
    const totalMovement = randomVolatility + trendBias + microTrend + 
                         marketSentiment + boundaryEffect + momentum + meanReversion
    
    // Apply movement and enforce strict bounds
    const newValue = Math.max(0.05, Math.min(0.95, lastPoint.value + totalMovement))
    
    return {
      time: now,
      value: parseFloat(newValue.toFixed(4))
    }
  }

  /**
   * HELPER: Get time interval for subscription based on time range
   */
  private getTimeIntervalForSubscription(subscriptionId: string): number {
    if (subscriptionId.includes('1H')) {
      return RAW_DATA_INTERVALS['1H'] // 15 seconds for hourly data
    } else if (subscriptionId.includes('1W')) {
      return RAW_DATA_INTERVALS['1W'] // 150 seconds for weekly data
    } else if (subscriptionId.includes('1M')) {
      return RAW_DATA_INTERVALS['1M'] // 1500 seconds for monthly data
    } else {
      return RAW_DATA_INTERVALS['1Y'] // 1 day for yearly data
    }
  }

  /**
   * STEP 3: Subscribe to a market data feed
   * Returns initial data immediately, then sets up periodic updates
   * PURE BROADCAST APPROACH - all data goes through mitt events
   * RETURNS: Teardown function for automatic cleanup
   */
  subscribe(config: SubscriptionConfig): () => void {
    console.log(`🔗 Subscribing to ${config.id} with ${config.updateFrequency}ms frequency`)
    
    // Check if already subscribed
    if (this.subscriptions.has(config.id)) {
      // Increment subscriber count for existing subscription
      const cache = this.subscriptions.get(config.id)!
      cache.subscriberCount++
      console.log(`👥 Additional subscriber for ${config.id} (total: ${cache.subscriberCount})`)
      
      // Emit initial data to ALL listeners (they will filter by subscriptionId)
      this.emitter.emit('market-data', {
        subscriptionId: config.id,
        type: 'initial',
        data: cache.data
      })
      
      // Return teardown function
      return () => {
        this.unsubscribe(config.id)
      }
    }

    // Generate initial historical data
    const initialData = this.generateInitialData(config.id)
    
    // Create cache entry
    const cache: MarketDataCache = {
      data: initialData,
      lastUpdate: Date.now(),
      config,
      subscriberCount: 1 // First subscriber
    }
    
    this.subscriptions.set(config.id, cache)
    
    // Emit initial data to ALL listeners (they will filter by subscriptionId)
    this.emitter.emit('market-data', {
      subscriptionId: config.id,
      type: 'initial',
      data: initialData
    })

    // Set up periodic updates
    cache.intervalId = setInterval(() => {
      try {
        const updatePoint = this.generateUpdatePoint(config.id)
        
        // Add to cache with rolling window
        cache.data.push(updatePoint)
        if (cache.data.length > this.HISTORY_LIMIT) {
          cache.data.shift() // Remove oldest point
        }
        
        //milisecond time
        cache.lastUpdate = Date.now()
        
        // Emit update to ALL listeners (they will filter by subscriptionId)
        this.emitter.emit('market-data', {
          subscriptionId: config.id,
          type: 'update', 
          data: updatePoint
        })
        
        //console.log(`📈 Emitted update for ${config.id}:`, updatePoint)
        
      } catch (error) {
        console.error(`❌ Error generating update for ${config.id}:`, error)
        this.emitter.emit('subscription-error', {
          subscriptionId: config.id,
          error: error instanceof Error ? error.message : 'Unknown error'
        })
      }
    }, config.updateFrequency)

    console.log(`✅ Subscription active for ${config.id} (subscribers: 1)`)
    
    // Return teardown function for this subscriber
    return () => {
      this.unsubscribe(config.id)
    }
  }

  /**
   * STEP 4: Unsubscribe from a market data feed
   * SUPPORTS REFERENCE COUNTING - only stops when all subscribers unsubscribe
   */
  unsubscribe(subscriptionId: string): void {
    const cache = this.subscriptions.get(subscriptionId)
    if (!cache) {
      console.warn(`⚠️ No subscription found for ${subscriptionId}`)
      return
    }

    // Decrement subscriber count
    cache.subscriberCount--
    console.log(`👤 Unsubscribed from ${subscriptionId} (remaining: ${cache.subscriberCount})`)

    // Only stop data generation when no subscribers remain
    if (cache.subscriberCount <= 0) {
      if (cache.intervalId) {
        clearInterval(cache.intervalId)
      }
      
      this.subscriptions.delete(subscriptionId)
      console.log(`🔌 Stopped data generation for ${subscriptionId} (no subscribers)`)
    }
  }

  /**
   * STEP 5: Get replay data for new subscribers (last N points)
   */
  getReplayData(subscriptionId: string, pointCount: number = 100): MarketDataPoint[] {
    const cache = this.subscriptions.get(subscriptionId)
    if (!cache) {
      console.warn(`⚠️ No data available for ${subscriptionId}`)
      return []
    }

    const startIndex = Math.max(0, cache.data.length - pointCount)
    return cache.data.slice(startIndex)
  }

  /**
   * STEP 6: Event listener management
   */
  on(event: 'market-data', handler: (data: MarketDataUpdate) => void): void
  on(event: 'subscription-error', handler: (error: { subscriptionId: string; error: string }) => void): void
  on(event: keyof Events, handler: (data: any) => void): void {
    this.emitter.on(event, handler)
  }

  off(event: keyof Events, handler: (data: any) => void): void {
    this.emitter.off(event, handler)
  }

  /**
   * STEP 7: Cleanup all subscriptions
   */
  destroy(): void {
    console.log('🧹 Destroying MarketDataEmitter...')
    
    for (const [subscriptionId, cache] of this.subscriptions) {
      if (cache.intervalId) {
        clearInterval(cache.intervalId)
      }
    }
    
    this.subscriptions.clear()
    this.emitter.all.clear()
    console.log('✅ MarketDataEmitter destroyed')
  }

  /**
   * STEP 8: Get current status
   */
  getStatus(): { activeSubscriptions: number; totalDataPoints: number } {
    let totalPoints = 0
    for (const cache of this.subscriptions.values()) {
      totalPoints += cache.data.length
    }
    
    return {
      activeSubscriptions: this.subscriptions.size,
      totalDataPoints: totalPoints
    }
  }
}

// Create singleton instance
export const marketDataEmitter = new MarketDataEmitter()

// Auto-initialize baseline subscriptions when module loads
// This ensures all subscription feeds are ready immediately
setTimeout(() => {
  console.log('⏰ Auto-initializing baseline subscriptions...')
  marketDataEmitter.initializeBaseline()
}, 100) // Small delay to ensure module is fully loaded

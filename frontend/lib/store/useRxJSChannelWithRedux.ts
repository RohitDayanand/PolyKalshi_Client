import { useEffect, useState, useRef } from 'react'
import { useSelector } from 'react-redux'
import { Subscription } from 'rxjs'
import { rxjsChannelManager, type TimeRange, type MarketSide, type DataPoint, type ChannelMessage } from '../RxJSChannelManager'
import { selectMarketSubscription, selectIsMarketSubscribed } from './apiSubscriptionSlice'

interface UseRxJSChannelWithReduxOptions {
  throttleMs?: number
  autoReplay?: boolean
}

/**
 * Hook that bridges Redux subscription state with RxJS channels
 * Automatically subscribes to RxJS channels when Redux subscription is confirmed
 */
export function useRxJSChannelWithRedux(
  frontendMarketId: string | null,
  side: MarketSide,
  range: TimeRange,
  options: UseRxJSChannelWithReduxOptions = {}
) {
  const [data, setData] = useState<DataPoint[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<DataPoint | null>(null)
  const subscriptionRef = useRef<Subscription | null>(null)
  const connectionSubscriptionRef = useRef<Subscription | null>(null)

  // Get Redux subscription state
  const isMarketSubscribed = useSelector((state: any) => 
    frontendMarketId ? selectIsMarketSubscribed(state, frontendMarketId) : false
  )
  const marketSubscription = useSelector((state: any) => 
    frontendMarketId ? selectMarketSubscription(state, frontendMarketId) : null
  )

  // Backend market ID from Redux subscription
  const backendMarketId = marketSubscription?.backend_market_id || null
  const subscriptionStatus = marketSubscription?.status || null

  useEffect(() => {
    // Clear data if no market is selected
    if (!frontendMarketId || !backendMarketId) {
      setData([])
      setLastUpdate(null)
      return
    }

    // Only subscribe to RxJS channels if the market is confirmed as subscribed
    if (!isMarketSubscribed || subscriptionStatus !== 'websocket_connected') {
      console.log(`⏳ useRxJSChannelWithRedux: Waiting for subscription confirmation for ${frontendMarketId} (status: ${subscriptionStatus})`)
      return
    }

    console.log(`🎯 useRxJSChannelWithRedux: Subscribing to ${backendMarketId}&${side}&${range} (frontend: ${frontendMarketId})`)

    // Subscribe to connection status
    connectionSubscriptionRef.current = rxjsChannelManager.getConnectionStatus().subscribe(
      (connected) => setIsConnected(connected)
    )

    // Subscribe to RxJS channel using backend market ID
    subscriptionRef.current = rxjsChannelManager.subscribe(
      backendMarketId,
      side,
      range,
      options.throttleMs
    ).subscribe({
      next: (message: ChannelMessage) => {
        console.log(`📨 useRxJSChannelWithRedux: Received message for ${message.channel}`, message)
        
        if (message.updateType === 'initial_data') {
          // Replace all data with historical data
          const historyData = Array.isArray(message.data) ? message.data : [message.data]
          setData(historyData)
          if (historyData.length > 0) {
            setLastUpdate(historyData[historyData.length - 1])
          }
        } else if (message.updateType === 'update') {
          // Add new data point
          const newPoint = Array.isArray(message.data) ? message.data[0] : message.data
          setData(prevData => [...prevData, newPoint])
          setLastUpdate(newPoint)
        }
      },
      error: (error) => {
        console.error(`❌ useRxJSChannelWithRedux: Error in ${backendMarketId}&${side}&${range}:`, error)
      }
    })

    // Auto-replay if requested
    if (options.autoReplay) {
      rxjsChannelManager.replay(backendMarketId, side, range)
    }

    return () => {
      if (subscriptionRef.current) {
        subscriptionRef.current.unsubscribe()
        subscriptionRef.current = null
      }
      if (connectionSubscriptionRef.current) {
        connectionSubscriptionRef.current.unsubscribe()
        connectionSubscriptionRef.current = null
      }
    }
  }, [frontendMarketId, backendMarketId, side, range, isMarketSubscribed, subscriptionStatus, options.throttleMs, options.autoReplay])

  const replay = () => {
    if (backendMarketId && isMarketSubscribed && subscriptionStatus === 'websocket_connected') {
      rxjsChannelManager.replay(backendMarketId, side, range)
    }
  }

  const getCache = () => {
    if (backendMarketId && isMarketSubscribed && subscriptionStatus === 'websocket_connected') {
      return rxjsChannelManager.getChannelCache(backendMarketId, side, range)
    }
    return []
  }

  return {
    data,
    lastUpdate,
    isConnected,
    isMarketSubscribed,
    subscriptionStatus,
    backendMarketId,
    replay,
    getCache
  }
}

/**
 * Hook for subscribing to multiple channels from different markets
 */
export function useMultipleRxJSChannelsWithRedux(
  markets: Array<{frontendMarketId: string, side: MarketSide, range: TimeRange}>,
  options: UseRxJSChannelWithReduxOptions = {}
) {
  const [channelData, setChannelData] = useState<Map<string, DataPoint[]>>(new Map())
  const [isConnected, setIsConnected] = useState(false)
  const subscriptionRef = useRef<Subscription | null>(null)
  const connectionSubscriptionRef = useRef<Subscription | null>(null)

  // Get all market subscriptions from Redux
  const marketSubscriptions = useSelector((state: any) => {
    const subscriptions: {[key: string]: any} = {}
    markets.forEach(({frontendMarketId}) => {
      const subscription = selectMarketSubscription(state, frontendMarketId)
      if (subscription) {
        subscriptions[frontendMarketId] = subscription
      }
    })
    return subscriptions
  })

  // Filter to only confirmed subscriptions
  const confirmedMarkets = markets.filter(({frontendMarketId}) => {
    const subscription = marketSubscriptions[frontendMarketId]
    return subscription && subscription.status === 'websocket_connected'
  })

  useEffect(() => {
    if (confirmedMarkets.length === 0) {
      setChannelData(new Map())
      return
    }

    console.log(`🎯 useMultipleRxJSChannelsWithRedux: Subscribing to ${confirmedMarkets.length} confirmed markets`)

    // Subscribe to connection status
    connectionSubscriptionRef.current = rxjsChannelManager.getConnectionStatus().subscribe(
      (connected) => setIsConnected(connected)
    )

    // Map to backend market IDs and subscribe
    const backendChannels = confirmedMarkets.map(({frontendMarketId, side, range}) => {
      const subscription = marketSubscriptions[frontendMarketId]
      return {
        marketId: subscription.backend_market_id,
        side,
        range
      }
    })

    subscriptionRef.current = rxjsChannelManager.subscribeToChannels(backendChannels).subscribe({
      next: (message: ChannelMessage) => {
        console.log(`📨 useMultipleRxJSChannelsWithRedux: Received message for ${message.channel}`, message)
        
        setChannelData(prevData => {
          const newData = new Map(prevData)
          
          if (message.updateType === 'initial_data') {
            // Replace all data with historical data
            const historyData = Array.isArray(message.data) ? message.data : [message.data]
            newData.set(message.channel, historyData)
          } else if (message.updateType === 'update') {
            // Add new data point
            const newPoint = Array.isArray(message.data) ? message.data[0] : message.data
            const existingData = newData.get(message.channel) || []
            newData.set(message.channel, [...existingData, newPoint])
          }
          
          return newData
        })
      },
      error: (error) => {
        console.error(`❌ useMultipleRxJSChannelsWithRedux: Error:`, error)
      }
    })

    return () => {
      if (subscriptionRef.current) {
        subscriptionRef.current.unsubscribe()
        subscriptionRef.current = null
      }
      if (connectionSubscriptionRef.current) {
        connectionSubscriptionRef.current.unsubscribe()
        connectionSubscriptionRef.current = null
      }
    }
  }, [JSON.stringify(confirmedMarkets), options.throttleMs])

  const getChannelKey = (marketId: string, side: MarketSide, range: TimeRange) => {
    return `${marketId}&${side}&${range}`
  }

  const getDataForMarket = (frontendMarketId: string, side: MarketSide, range: TimeRange) => {
    const subscription = marketSubscriptions[frontendMarketId]
    if (!subscription) return []
    
    const channelKey = getChannelKey(subscription.backend_market_id, side, range)
    return channelData.get(channelKey) || []
  }

  return {
    channelData,
    isConnected,
    confirmedMarkets,
    marketSubscriptions,
    getDataForMarket,
    getChannelKey
  }
}
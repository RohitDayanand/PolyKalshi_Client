import { useEffect, useState, useRef } from 'react'
import { Subscription } from 'rxjs'
import { rxjsChannelManager, type TimeRange, type MarketSide, type DataPoint, type ChannelMessage } from '../RxJSChannel'

interface UseRxJSChannelOptions {
  throttleMs?: number
  autoReplay?: boolean
}

export function useRxJSChannel(
  marketId: string | null,
  side: MarketSide,
  range: TimeRange,
  options: UseRxJSChannelOptions = {}
) {
  const [data, setData] = useState<DataPoint[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<DataPoint | null>(null)
  const subscriptionRef = useRef<Subscription | null>(null)
  const connectionSubscriptionRef = useRef<Subscription | null>(null)

  useEffect(() => {
    if (!marketId) {
      setData([])
      setLastUpdate(null)
      return
    }

    console.log(`🎯 useRxJSChannel: Subscribing to ${marketId}&${side}&${range}`)

    // Subscribe to connection status
    connectionSubscriptionRef.current = rxjsChannelManager.getConnectionStatus().subscribe(
      (connected) => setIsConnected(connected)
    )

    // Subscribe to channel
    subscriptionRef.current = rxjsChannelManager.subscribe(
      marketId,
      side,
      range,
      options.throttleMs
    ).subscribe({
      next: (message: ChannelMessage) => {
        console.log(`📨 useRxJSChannel: Received message for ${message.channel}`, message)
        
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
        console.error(`❌ useRxJSChannel: Error in ${marketId}&${side}&${range}:`, error)
      }
    })

    // Auto-replay if requested
    if (options.autoReplay) {
      rxjsChannelManager.replay(marketId, side, range)
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
  }, [marketId, side, range, options.throttleMs, options.autoReplay])

  const replay = () => {
    if (marketId) {
      rxjsChannelManager.replay(marketId, side, range)
    }
  }

  const getCache = () => {
    if (marketId) {
      return rxjsChannelManager.getChannelCache(marketId, side, range)
    }
    return []
  }

  return {
    data,
    lastUpdate,
    isConnected,
    replay,
    getCache
  }
}

export function useMultipleRxJSChannels(
  channels: Array<{marketId: string, side: MarketSide, range: TimeRange}>,
  options: UseRxJSChannelOptions = {}
) {
  const [channelData, setChannelData] = useState<Map<string, DataPoint[]>>(new Map())
  const [isConnected, setIsConnected] = useState(false)
  const subscriptionRef = useRef<Subscription | null>(null)
  const connectionSubscriptionRef = useRef<Subscription | null>(null)

  useEffect(() => {
    if (channels.length === 0) {
      setChannelData(new Map())
      return
    }

    console.log(`🎯 useMultipleRxJSChannels: Subscribing to ${channels.length} channels`)

    // Subscribe to connection status
    connectionSubscriptionRef.current = rxjsChannelManager.getConnectionStatus().subscribe(
      (connected) => setIsConnected(connected)
    )

    // Subscribe to multiple channels
    subscriptionRef.current = rxjsChannelManager.subscribeToChannels(channels).subscribe({
      next: (message: ChannelMessage) => {
        console.log(`📨 useMultipleRxJSChannels: Received message for ${message.channel}`, message)
        
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
        console.error(`❌ useMultipleRxJSChannels: Error:`, error)
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
  }, [JSON.stringify(channels), options.throttleMs])

  const getChannelKey = (marketId: string, side: MarketSide, range: TimeRange) => {
    return `${marketId}&${side}&${range}`
  }

  const getDataForChannel = (marketId: string, side: MarketSide, range: TimeRange) => {
    const channelKey = getChannelKey(marketId, side, range)
    return channelData.get(channelKey) || []
  }

  return {
    channelData,
    isConnected,
    getDataForChannel,
    getChannelKey
  }
}
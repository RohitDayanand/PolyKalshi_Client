import { useAppDispatch, useAppSelector } from './hooks'
import { 
  callSubscriptionAPI, 
  selectIsLoading,
  selectLastError,
  selectSubscriptions
} from './apiSubscriptionSlice'
import {
  clearMessages,
  selectIsConnected,
  selectConnectionStatus,
  selectRecentMessages,
  subscribeToMarket as subscribeToMarketAction
} from './websocketSlice'

interface Market {
  id: string
  title: string
  platform?: "polymarket" | "kalshi"
  tokenIds?: string[]
  kalshiTicker?: string
}

// Main hook for market subscription logic
export const useMarketSubscription = () => {
  const dispatch = useAppDispatch()
  
  // Redux state
  const isApiLoading = useAppSelector(selectIsLoading)
  const apiError = useAppSelector(selectLastError)
  const subscriptions = useAppSelector(selectSubscriptions)
  const isWebSocketConnected = useAppSelector(selectIsConnected)
  const connectionStatus = useAppSelector(selectConnectionStatus)
  const recentMessages = useAppSelector((state) => selectRecentMessages(state, 10))

  // Subscribe to a market
  const subscribeToMarket = async (platform: "polymarket" | "kalshi", market: Market) => {
    console.log('🚀 Subscribing to market:', { platform, market })
    
    try {
      // Step 1: Call backend API to establish market connection
      const result = await dispatch(callSubscriptionAPI({ platform, market })).unwrap()
      
      console.log('🔍 API Response:', result.apiResponse)
      console.log('🔍 Market ID from API:', result.apiResponse.market_id)
      console.log('🔍 Full result object:', result)
      console.log('🔍 Market ID exists?', !!result.apiResponse.market_id)
      console.log('🔍 Market ID value:', JSON.stringify(result.apiResponse.market_id))
      
      // Step 2: Send subscription message via singleton WebSocket (handled by middleware)
      if (result.apiResponse.market_id) {
        console.log('✅ Dispatching WebSocket subscription for:', result.apiResponse.market_id)
        dispatch(subscribeToMarketAction({
          marketId: result.apiResponse.market_id,
          platform: platform
        }))
        
        console.log('✅ Market subscription dispatched to singleton WebSocket')
      } else {
        console.warn('❌ No market_id in API response - WebSocket subscription skipped!')
      }
      
      console.log('✅ Market subscription process completed')
      return result
      
    } catch (error) {
      console.error('❌ Market subscription failed:', error)
      throw error
    }
  }

  // Clear WebSocket messages
  const clearWebSocketMessages = () => {
    dispatch(clearMessages())
  }

  return {
    // Actions
    subscribeToMarket,
    clearWebSocketMessages,
    
    // State
    isApiLoading,
    apiError,
    subscriptions,
    isWebSocketConnected,
    connectionStatus,
    recentMessages
  }
}

// Hook for accessing WebSocket messages by type
export const useWebSocketMessages = (messageType?: string, count: number = 10) => {
  const allMessages = useAppSelector((state) => selectRecentMessages(state, count))
  
  if (messageType) {
    // @ToDo: Explain why this is using any
    return allMessages.filter((msg: any) => msg.type === messageType)
  }
  
  return allMessages
}

// Hook for checking specific market subscription status
export const useMarketSubscriptionStatus = (marketId: string) => {
  const subscriptions = useAppSelector(selectSubscriptions)
  const subscription = subscriptions[marketId]
  
  return {
    isSubscribed: !!subscription,
    status: subscription?.status || 'not_subscribed',
    backendMarketId: subscription?.backend_market_id,
    platform: subscription?.platform,
    subscribedAt: subscription?.subscribed_at
  }
}
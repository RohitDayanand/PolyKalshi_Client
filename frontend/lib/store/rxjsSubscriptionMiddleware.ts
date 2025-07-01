import { Middleware } from '@reduxjs/toolkit'
import { markWebSocketSubscribed } from './apiSubscriptionSlice'
import { rxjsChannelManager } from '../RxJSChannel'

export const rxjsSubscriptionMiddleware: Middleware = (store) => (next) => (action) => {
  const result = next(action)
  
  // Intercept markWebSocketSubscribed actions
  if (markWebSocketSubscribed.match(action)) {

    //@TODO - add good comments and documentation for the formatting of the backend id
    const backendMarketId = action.payload
    
    console.log('🎯 RxJSSubscriptionMiddleware: Intercepted markWebSocketSubscribed for:', backendMarketId)
    
    // Get the subscription details from the updated state
    const state = store.getState()
    const subscriptions = state.apiSubscription.subscriptions
    
    // Find the subscription that matches this backend market ID
    let matchedSubscription = null
    let frontendId = null
    
    for (const [fId, subscription] of Object.entries(subscriptions)) {
      if ((subscription as any).backend_market_id === backendMarketId) {
        matchedSubscription = subscription
        frontendId = fId
        break
      }
    }
    
    if (matchedSubscription && frontendId) {
      console.log('✅ RxJSSubscriptionMiddleware: Found subscription details:', {
        frontendId,
        backendMarketId,
        platform: (matchedSubscription as any).platform
      })
      
      // Notify RxJS Channel Manager to create market channels
      rxjsChannelManager.onMarketSubscribed(
        backendMarketId, // Use backend market ID as the primary identifier
        (matchedSubscription as any).platform
      )
    } else {
      console.warn('⚠️ RxJSSubscriptionMiddleware: Could not find subscription details for backend market:', backendMarketId)
    }
  }
  
  return result
}

/**
 * Set the WebSocket instance for the RxJS Channel Manager
 * This should be called from the existing websocketMiddleware
 */
export const setRxJSWebSocket = (ws: WebSocket | null) => {
  rxjsChannelManager.setWebSocketInstance(ws)
  console.log('🔗 RxJSSubscriptionMiddleware: WebSocket instance set')
}

/**
 * Get statistics from the RxJS Channel Manager
 */
export const getRxJSStats = () => {
  return rxjsChannelManager.getStats()
}
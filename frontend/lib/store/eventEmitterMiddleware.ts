import { Middleware } from '@reduxjs/toolkit'
import { markWebSocketSubscribed } from './apiSubscriptionSlice'
import { eventEmitterManager } from '../EventEmitterManager'

let websocketInstance: WebSocket | null = null

export const eventEmitterMiddleware: Middleware = (store) => (next) => (action) => {
  const result = next(action)
  
  // Intercept markWebSocketSubscribed actions
  if (markWebSocketSubscribed.match(action)) {
    const backendMarketId = action.payload
    
    console.log('🎯 EventEmitterMiddleware: Intercepted markWebSocketSubscribed for:', backendMarketId)
    
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
      console.log('✅ EventEmitterMiddleware: Found subscription details:', {
        frontendId,
        backendMarketId,
        platform: (matchedSubscription as any).platform
      })
      
      // Notify EventEmitterManager to create market emitters
      eventEmitterManager.onMarketSubscribed(
        frontendId,
        backendMarketId,
        (matchedSubscription as any).platform
      )
    } else {
      console.warn('⚠️ EventEmitterMiddleware: Could not find subscription details for backend market:', backendMarketId)
    }
  }
  
  return result
}

/**
 * Set the WebSocket instance for the EventEmitterManager
 * This should be called from the existing websocketMiddleware
 */
export const setEventEmitterWebSocket = (ws: WebSocket | null) => {
  websocketInstance = ws
  eventEmitterManager.setWebSocketInstance(ws)
  console.log('🔗 EventEmitterMiddleware: WebSocket instance set')
}

/**
 * Get the current WebSocket instance
 */
export const getEventEmitterWebSocket = (): WebSocket | null => {
  return websocketInstance
}
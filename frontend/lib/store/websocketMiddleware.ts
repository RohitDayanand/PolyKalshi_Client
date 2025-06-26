import { Middleware } from '@reduxjs/toolkit'
import { 
  connect, 
  connected, 
  disconnect, 
  addTickerUpdate, 
  addConnectionStatus,
  subscribeToMarket
} from './websocketSlice'
import { 
  markWebSocketSubscribed,
  updateSubscriptionStatus,
  selectPendingWebSocketSubscriptions
} from './apiSubscriptionSlice'
import { setRxJSWebSocket } from './rxjsSubscriptionMiddleware'

let websocketInstance: WebSocket | null = null

export const websocketMiddleware: Middleware = (store) => (next) => (action) => {
  const result = next(action)
  
  // Handle WebSocket connection
  if (connect.match(action)) {
    // Close existing connection if any
    if (websocketInstance && websocketInstance.readyState !== WebSocket.CLOSED) {
      websocketInstance.close()
    }
    
    console.log('🔌 Initializing singleton WebSocket connection...')
    
    // Create new WebSocket connection
    websocketInstance = new WebSocket('ws://localhost:8000/ws/ticker')
    
    websocketInstance.onopen = () => {
      console.log('✅ Singleton WebSocket connected')
      store.dispatch(connected())
      
      // Set WebSocket instance in RxJS Channel Manager
      setRxJSWebSocket(websocketInstance)
      
      // Send any pending subscriptions
      const state = store.getState()
      const pendingWebSocketSubs = selectPendingWebSocketSubscriptions(state)
      
      if (pendingWebSocketSubs.length > 0) {
        pendingWebSocketSubs.forEach((marketId: string) => {
          const subscriptionMessage = {
            type: 'subscribe_market',
            market_id: marketId
          }
          console.log('📡 Sending pending WebSocket subscription:', subscriptionMessage)
          websocketInstance?.send(JSON.stringify(subscriptionMessage))
          store.dispatch(markWebSocketSubscribed(marketId))
        })
      }
    }
    
    websocketInstance.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        console.log('📨 WebSocket message received:', message)
        
        // Should not be streaming ticker updates here 
        // Dispatch to Redux based on message type
        if (message.type === 'ticker_update') {
          store.dispatch(addTickerUpdate(message))
          
          // Update subscription status if needed
          if (message.market_id) {
            store.dispatch(updateSubscriptionStatus({
              backend_market_id: message.market_id,
              status: 'receiving_data'
            }))
          }
        } else if (message.type === 'connection_status') {
          store.dispatch(addConnectionStatus(message))
          
          if (message.market_id) {
            store.dispatch(updateSubscriptionStatus({
              backend_market_id: message.market_id,
              status: message.status || 'unknown'
            }))
          }
        }
      } catch (error) {
        console.error('❌ Error parsing WebSocket message:', error)
      }
    }
    
    websocketInstance.onclose = () => {
      console.log('🔌 Singleton WebSocket disconnected')
      store.dispatch(disconnect())
      
      // Clear WebSocket instance in RxJS Channel Manager
      setRxJSWebSocket(null)
      
      // Attempt reconnection after 3 seconds
      setTimeout(() => {
        if (websocketInstance?.readyState === WebSocket.CLOSED) {
          console.log('🔄 Attempting singleton WebSocket reconnection...')
          store.dispatch(connect())
        }
      }, 3000)
    }
    
    websocketInstance.onerror = (error) => {
      console.error('❌ Singleton WebSocket error:', error)
    }
  }
  
  // Handle WebSocket disconnection
  if (disconnect.match(action)) {
    if (websocketInstance) {
      websocketInstance.close()
      websocketInstance = null
    }
    // Clear WebSocket instance in RxJS Channel Manager
    setRxJSWebSocket(null)
  }
  
  // Handle market subscription
  if (subscribeToMarket.match(action)) {
    const { marketId, platform } = action.payload
    
    if (websocketInstance?.readyState === WebSocket.OPEN) {
      const subscriptionMessage = {
        type: 'subscribe_market',
        market_id: marketId,
        platform: platform
      }
      
      console.log('📡 Sending market subscription via singleton WebSocket:', subscriptionMessage)
      websocketInstance.send(JSON.stringify(subscriptionMessage))
      store.dispatch(markWebSocketSubscribed(marketId))
    } else {
      console.warn('⚠️ Singleton WebSocket not connected, subscription will be pending')
    }
  }
  
  return result
}

// Initialize WebSocket connection when store is created
export const initializeWebSocket = (store: any) => {
  store.dispatch(connect())
}
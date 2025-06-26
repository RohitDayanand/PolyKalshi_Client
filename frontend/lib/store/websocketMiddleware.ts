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
    
    
    // Create new WebSocket connection
    websocketInstance = new WebSocket('ws://localhost:8000/ws/ticker')
    
    websocketInstance.onopen = () => {
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
          websocketInstance?.send(JSON.stringify(subscriptionMessage))
          store.dispatch(markWebSocketSubscribed(marketId))
        })
      }
    }
    
    websocketInstance.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        
        // Only handle connection status changes, not ticker updates
        if (message.type === 'connection_status') {
          store.dispatch(addConnectionStatus(message))
          
          if (message.market_id) {
            store.dispatch(updateSubscriptionStatus({
              backend_market_id: message.market_id,
              status: message.status || 'unknown'
            }))
          }
        }
        // Ticker updates are handled by RxJS Channel Manager, not Redux
      } catch (error) {
      }
    }
    
    websocketInstance.onclose = () => {
      store.dispatch(disconnect())
      
      // Clear WebSocket instance in RxJS Channel Manager
      setRxJSWebSocket(null)
      
      // Attempt reconnection after 3 seconds
      setTimeout(() => {
        if (websocketInstance?.readyState === WebSocket.CLOSED) {
          store.dispatch(connect())
        }
      }, 3000)
    }
    
    websocketInstance.onerror = (error) => {
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
      
      websocketInstance.send(JSON.stringify(subscriptionMessage))
      store.dispatch(markWebSocketSubscribed(marketId))
    } else {
    }
  }
  
  return result
}

// Initialize WebSocket connection when store is created
export const initializeWebSocket = (store: any) => {
  store.dispatch(connect())
}
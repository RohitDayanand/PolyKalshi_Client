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
  console.log('🔄 WebSocket Middleware - Action received:', action)
  const result = next(action)
  
  // Handle WebSocket connection
  if (connect.match(action)) {
    console.log('🔌 WebSocket Middleware - Connecting to WebSocket...')
    // Close existing connection if any
    if (websocketInstance && websocketInstance.readyState !== WebSocket.CLOSED) {
      console.log('🔌 Closing existing WebSocket connection')
      websocketInstance.close()
    }
    
    
    // Create new WebSocket connection
    console.log('🔌 Creating new WebSocket connection to ws://localhost:8000/ws/ticker')
    websocketInstance = new WebSocket('ws://localhost:8000/ws/ticker')
    
    websocketInstance.onopen = () => {
      console.log('✅ WebSocket connected successfully!')
      store.dispatch(connected())
      
      // Set WebSocket instance in RxJS Channel Manager
      setRxJSWebSocket(websocketInstance)
      console.log('🔗 WebSocket instance set in RxJS Channel Manager')
      
      // Send any pending subscriptions
      const state = store.getState()
      const pendingWebSocketSubs = selectPendingWebSocketSubscriptions(state)
      console.log('📋 Pending WebSocket subscriptions:', pendingWebSocketSubs)
      
      if (pendingWebSocketSubs.length > 0) {
        console.log('📤 Sending pending subscriptions...')
        pendingWebSocketSubs.forEach((marketId: string) => {
          const subscriptionMessage = {
            type: 'subscribe_market',
            market_id: marketId
          }
          console.log('📤 Sending pending subscription for market:', marketId, subscriptionMessage)
          websocketInstance?.send(JSON.stringify(subscriptionMessage))
          store.dispatch(markWebSocketSubscribed(marketId))
          console.log('✅ Pending subscription sent and marked as subscribed')
        })
      } else {
        console.log('📋 No pending subscriptions to send')
      }
    }
    
    websocketInstance.onmessage = (event) => {
      console.log('📨 WebSocket message received:', event.data)
      try {
        const message = JSON.parse(event.data)
        console.log('📨 Parsed message:', message)
        
        // Only handle connection status changes, not ticker updates
        if (message.type === 'connection_status') {
          console.log('🔄 Handling connection status message:', message)
          store.dispatch(addConnectionStatus(message))
          
          if (message.market_id) {
            console.log('🔄 Updating subscription status for market:', message.market_id, 'status:', message.status)
            store.dispatch(updateSubscriptionStatus({
              backend_market_id: message.market_id,
              status: message.status || 'unknown'
            }))
          }
        } else {
          console.log('📨 Message type not handled by middleware:', message.type)
        }
        // Ticker updates are handled by RxJS Channel Manager, not Redux
      } catch (error) {
        console.error('❌ Error parsing WebSocket message:', error, 'Raw data:', event.data)
      }
    }
    
    websocketInstance.onclose = () => {
      console.log('🔌 WebSocket connection closed')
      store.dispatch(disconnect())
      
      // Clear WebSocket instance in RxJS Channel Manager
      setRxJSWebSocket(null)
      console.log('🔗 WebSocket instance cleared from RxJS Channel Manager')
      
      // Attempt reconnection after 3 seconds
      console.log('⏰ Scheduling reconnection in 3 seconds...')
      setTimeout(() => {
        if (websocketInstance?.readyState === WebSocket.CLOSED) {
          console.log('🔄 Attempting to reconnect WebSocket...')
          store.dispatch(connect())
        }
      }, 3000)
    }
    
    websocketInstance.onerror = (error) => {
      console.error('❌ WebSocket error:', error)
    }
  }
  
  // Handle WebSocket disconnection
  if (disconnect.match(action)) {
    console.log('🔌 WebSocket Middleware - Disconnecting WebSocket...')
    if (websocketInstance) {
      websocketInstance.close()
      websocketInstance = null
      console.log('🔌 WebSocket instance closed and nullified')
    }
    // Clear WebSocket instance in RxJS Channel Manager
    setRxJSWebSocket(null)
    console.log('🔗 WebSocket instance cleared from RxJS Channel Manager')
  }
  
  // Handle market subscription  
  if (subscribeToMarket.match(action)) {
    console.log('🎯 WebSocket Middleware - subscribeToMarket matched!', action.payload)
    const { marketId, platform } = action.payload
    
    console.log('🔍 WebSocket state:', websocketInstance?.readyState, 'OPEN:', WebSocket.OPEN)
    
    if (websocketInstance?.readyState === WebSocket.OPEN) {
      const subscriptionMessage = {
        type: 'subscribe_market',
        market_id: marketId,
        platform: platform
      }
      
      console.log('📤 Sending WebSocket subscription:', subscriptionMessage)
      websocketInstance.send(JSON.stringify(subscriptionMessage))
      store.dispatch(markWebSocketSubscribed(marketId))
      console.log('✅ WebSocket subscription sent and Redux updated')
    } else {
      console.warn('❌ WebSocket not open - cannot send subscription. Current state:', websocketInstance?.readyState)
      console.warn('❌ WebSocket states: CONNECTING=0, OPEN=1, CLOSING=2, CLOSED=3')
      if (!websocketInstance) {
        console.warn('❌ WebSocket instance is null/undefined')
      }
    }
  }
  
  return result
}

// Initialize WebSocket connection when store is created
export const initializeWebSocket = (store: any) => {
  store.dispatch(connect())
}
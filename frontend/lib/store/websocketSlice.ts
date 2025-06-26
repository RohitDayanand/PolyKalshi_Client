import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import { 
  markWebSocketSubscribed,
  updateSubscriptionStatus,
  selectPendingWebSocketSubscriptions
} from './apiSubscriptionSlice'

// Updated to match our backend API message types
export interface WebSocketMessage {
  type: 'ticker_update' | 'connection_status' | 'subscription_confirmed' | 'error'
  data?: any
  timestamp: number
  market_id?: string
  platform?: string
  summary_stats?: {
    yes?: { bid: number; ask: number; volume: number }
    no?: { bid: number; ask: number; volume: number }
  }
  status?: 'disconnected' | 'reconnecting' | 'stale' | 'connected'
  message?: string
  subscription?: string
  retry_attempt?: number
}

export interface WebSocketState {
  isConnected: boolean
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error'
  messages: WebSocketMessage[]
  lastMessage: WebSocketMessage | null
  error: string | null
  reconnectAttempts: number
  maxReconnectAttempts: number
}

const initialState: WebSocketState = {
  isConnected: false,
  connectionStatus: 'disconnected',
  messages: [],
  lastMessage: null,
  error: null,
  reconnectAttempts: 0,
  maxReconnectAttempts: 5,
}

const websocketSlice = createSlice({
  name: 'websocket',
  initialState,
  reducers: {
    // Connection management
    connect: (state) => {
      state.connectionStatus = 'connecting'
      state.error = null
    },
    
    connected: (state) => {
      state.isConnected = true
      state.connectionStatus = 'connected'
      state.reconnectAttempts = 0
      state.error = null
    },
    
    disconnect: (state) => {
      state.isConnected = false
      state.connectionStatus = 'disconnected'
    },
    
    reconnecting: (state) => {
      state.connectionStatus = 'reconnecting'
      state.reconnectAttempts += 1
    },
    
    connectionError: (state, action: PayloadAction<string>) => {
      state.isConnected = false
      state.connectionStatus = 'error'
      state.error = action.payload
    },
    
    // Message handling
    addMessage: (state, action: PayloadAction<WebSocketMessage>) => {
      const message = {
        ...action.payload,
        timestamp: action.payload.timestamp || new Date().toISOString(),
      }
      
      state.messages.push(message)
      state.lastMessage = message
      
      // Keep only last 100 messages to prevent memory issues
      if (state.messages.length > 100) {
        state.messages = state.messages.slice(-100)
      }
    },
    
    // Market data updates
    updateOrderbook: (state, action: PayloadAction<{
      marketId: string
      orderbook: any
      timestamp?: string
    }>) => {
      const message: WebSocketMessage = {
        type: 'orderbook',
        data: action.payload.orderbook,
        timestamp: action.payload.timestamp || new Date().toISOString(),
        marketId: action.payload.marketId,
      }
      
      state.messages.push(message)
      state.lastMessage = message
      
      if (state.messages.length > 100) {
        state.messages = state.messages.slice(-100)
      }
    },
    
    updatePriceChange: (state, action: PayloadAction<{
      marketId: string
      priceChange: any
      timestamp?: string
    }>) => {
      const message: WebSocketMessage = {
        type: 'price_change',
        data: action.payload.priceChange,
        timestamp: action.payload.timestamp || new Date().toISOString(),
        marketId: action.payload.marketId,
      }
      
      state.messages.push(message)
      state.lastMessage = message
      
      if (state.messages.length > 100) {
        state.messages = state.messages.slice(-100)
      }
    },
    
    updateTickSizeChange: (state, action: PayloadAction<{
      marketId: string
      tickSizeChange: any
      timestamp?: string
    }>) => {
      const message: WebSocketMessage = {
        type: 'tick_size_change',
        data: action.payload.tickSizeChange,
        timestamp: action.payload.timestamp || new Date().toISOString(),
        marketId: action.payload.marketId,
      }
      
      state.messages.push(message)
      state.lastMessage = message
      
      if (state.messages.length > 100) {
        state.messages = state.messages.slice(-100)
      }
    },
    
    // Clear messages
    clearMessages: (state) => {
      state.messages = []
      state.lastMessage = null
    },
    
    // Clear error
    clearError: (state) => {
      state.error = null
    },
    
    // Reset reconnect attempts
    resetReconnectAttempts: (state) => {
      state.reconnectAttempts = 0
    },

    // New actions for our backend API integration
    addTickerUpdate: (state, action: PayloadAction<WebSocketMessage>) => {
      const message = {
        ...action.payload,
        timestamp: action.payload.timestamp || Date.now(),
      }
      
      state.messages.push(message)
      state.lastMessage = message
      
      // Keep only last 50 messages for UI display
      if (state.messages.length > 50) {
        state.messages = state.messages.slice(-50)
      }
    },

    addConnectionStatus: (state, action: PayloadAction<WebSocketMessage>) => {
      const message = {
        ...action.payload,
        timestamp: action.payload.timestamp || Date.now(),
      }
      
      state.messages.push(message)
      state.lastMessage = message
      
      if (state.messages.length > 50) {
        state.messages = state.messages.slice(-50)
      }
    },

    // Subscribe to market via WebSocket
    subscribeToMarket: (state, action: PayloadAction<{marketId: string, platform: string}>) => {
      // This will be handled by middleware
    },
  },
})

export const {
  connect,
  connected,
  disconnect,
  reconnecting,
  connectionError,
  addMessage,
  updateOrderbook,
  updatePriceChange,
  updateTickSizeChange,
  clearMessages,
  clearError,
  resetReconnectAttempts,
  addTickerUpdate,
  addConnectionStatus,
  subscribeToMarket,
} = websocketSlice.actions

export default websocketSlice.reducer

// Selectors
export const selectIsConnected = (state: any) => state.websocket.isConnected
export const selectConnectionStatus = (state: any) => state.websocket.connectionStatus
export const selectWebSocketError = (state: any) => state.websocket.error
export const selectLastMessage = (state: any) => state.websocket.lastMessage
export const selectRecentMessages = (state: any, count: number = 10) => {
  const messages = state.websocket.messages
  if (messages.length <= count) return messages
  return messages.slice(-count)
}
export const selectMessagesByMarket = (state: any, marketId: string) =>
  state.websocket.messages.filter((message: any) => message.marketId === marketId)
export const selectMessagesByType = (state: any, type: WebSocketMessage['type']) =>
  state.websocket.messages.filter((message: any) => message.type === type)
export const selectReconnectAttempts = (state: any) => state.websocket.reconnectAttempts
export const selectCanReconnect = (state: any) =>
  state.websocket.reconnectAttempts < state.websocket.maxReconnectAttempts

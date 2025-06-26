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
    
    // Message handling - no message storage to prevent re-renders
    addMessage: (state, action: PayloadAction<WebSocketMessage>) => {
      // Only update connection status if needed, don't store messages
      if (action.payload.type === 'connection_status') {
        state.connectionStatus = action.payload.status || 'connected'
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

    // Ticker updates - no message storage
    addTickerUpdate: (state, action: PayloadAction<WebSocketMessage>) => {
      // Process ticker data without storing in Redux
    },

    addConnectionStatus: (state, action: PayloadAction<WebSocketMessage>) => {
      // Only update connection status, don't store messages
      state.connectionStatus = action.payload.status || 'connected'
    },

    // Subscribe to market via WebSocket
    subscribeToMarket: (_state, _action: PayloadAction<{marketId: string, platform: string}>) => {
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

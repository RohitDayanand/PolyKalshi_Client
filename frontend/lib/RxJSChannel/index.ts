// Main exports
export { RxJSChannelManager, rxjsChannelManager } from './RxJSChannelManager'

// Subclasses (for advanced usage)
export { ChannelCache } from './ChannelCache'
export { ApiPoller } from './ApiPoller'
export { WebSocketHandler } from './WebSocketHandler'

// Types and interfaces
export type {
  TimeRange,
  MarketSide,
  UpdateType,
  Platform,
  DataPoint,
  TickerData,
  ChannelMessage,
  ChannelConfig,
  ChannelStats,
  ManagerStats,
  ChannelKey
} from './types'
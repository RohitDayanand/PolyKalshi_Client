import { ISeriesApi, IChartApi } from 'lightweight-charts'

export const TIME_RANGES = ['1H', '1W', '1M', '1Y'] as const;
export type TimeRange = typeof TIME_RANGES[number];

export const SERIES_VIEWS = ['BOTH', 'YES', 'NO'] as const;
export type SeriesView = typeof SERIES_VIEWS[number];

// Series overlay types for dependency management
//No such thing as a BOTH overlay - there is yes and no
export const SERIES_TYPES = ['YES', 'NO'] as const;
export type SeriesType = typeof SERIES_TYPES[number];

// Fullscreen state types
//isFullscreen checks whether fullscreen is activated
//show fullscreenbutton checks whether fullscreen button in UI
export interface FullscreenState {
  isFullscreen: boolean;
  showFullscreenButton: boolean;
}

export interface ChartDataPoint {
  time: number;
  yesValue: number;
  noValue: number;
}

export interface StreamingDataPoint {
  time: number;
  value: number;
}

export interface StreamingData {
  yes: StreamingDataPoint[];
  no: StreamingDataPoint[];
}

export interface ChartSeriesRefs {
  yes: ISeriesApi<'Line'> | null;
  no: ISeriesApi<'Line'> | null;
}


// Market subscription state types
// Represents subscription IDs for event emitter price updates
// Each series type (YES/NO) has subscription IDs for each time range
export interface MarketSubscription {
  yes: Record<TimeRange, string>;
  no: Record<TimeRange, string>;
}

export interface ChartInstanceRef {
  instance: any;
  handleResize: () => void;
}

// SeriesClass constructor options for overlay dependency management
export interface SeriesClassConstructorOptions {
  chartInstance: IChartApi;
  seriesType: SeriesType;
  parent?: any; // Will be SeriesClass but avoiding circular import
  subscriptionId: string; // Each series must own a subscription 
}

// Overlay management types for global store
export interface Overlay {
  type: SeriesType;
  range: TimeRange;
  enabled: boolean;
  available: boolean;
}

// Dictionary of overlays indexed by name
export interface OverlayDictionary {
  [overlayName: string]: Overlay;
}

// Event Emitter Data Types for Market Data Streaming
export interface MarketDataPoint {
  time: number;
  value: number;
}

export interface MarketDataUpdate {
  subscriptionId: string;
  type: 'initial' | 'update';
  data: MarketDataPoint | MarketDataPoint[]; // Array for initial, single object for updates
}

export interface SubscriptionConfig {
  id: string;
  updateFrequency: number; // milliseconds between updates
  historyLimit: number; // max data points to cache
}


/**
 * CANDLESTICK VIEW COMPONENT
 * Handles candlestick chart generation and data transformation
 */

import { CandlestickSeries } from 'lightweight-charts'

export interface CandlestickData {
  time: any;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface CandlestickOptions {
  upColor?: string;
  downColor?: string;
  borderVisible?: boolean;
  wickUpColor?: string;
  wickDownColor?: string;
}

export const defaultCandlestickOptions: CandlestickOptions = {
  upColor: '#00C851',    // Bright green for up/bullish candles
  downColor: '#ff4444',  // Bright red for down/bearish candles
  borderVisible: false,
  wickUpColor: '#00C851',    // Green wicks for up candles
  wickDownColor: '#ff4444',  // Red wicks for down candles
}

export const yesCandlestickOptions: CandlestickOptions = {
  upColor: '#00C851',    // Green for up/bullish candles
  downColor: '#ff4444',  // Red for down/bearish candles
  borderVisible: false,
  wickUpColor: '#00C851',    // Green wicks for up candles
  wickDownColor: '#ff4444',  // Red wicks for down candles
}

export const noCandlestickOptions: CandlestickOptions = {
  upColor: '#00C851',    // Green for up/bullish candles
  downColor: '#ff4444',  // Red for down/bearish candles
  borderVisible: false,
  wickUpColor: '#00C851',    // Green wicks for up candles
  wickDownColor: '#ff4444',  // Red wicks for down candles
}

/**
 * CANDLESTICK DATA GENERATION
 * Generates candlestick data from line series data
 */
export function generateCandlestickData(
  yesData: Array<{time: any, value: number}>, 
  noData: Array<{time: any, value: number}>
): CandlestickData[] {
  // Generate candlesticks from YES data for backward compatibility
  return generateYesCandlestickData(yesData)
}

/**
 * GENERATE YES CANDLESTICK DATA
 * Creates candlestick data specifically from Yes series data
 */
export function generateYesCandlestickData(
  yesData: Array<{time: any, value: number}>
): CandlestickData[] {
  const createCandle = (val: number, time: any): CandlestickData => ({
    time,
    open: val,
    high: val,
    low: val,
    close: val,
  });

  const updateCandle = (candle: CandlestickData, val: number): CandlestickData => ({
    time: candle.time,
    close: val,
    open: candle.open,
    low: Math.min(candle.low, val),
    high: Math.max(candle.high, val),
  });

  const candlestickData: CandlestickData[] = [];
  const updatesPerCandle = 5;
  
  for (let i = 0; i < yesData.length; i += updatesPerCandle) {
    const baseTime = yesData[i].time;
    const baseValue = yesData[i].value;
    
    let candle = createCandle(baseValue, baseTime);
    
    // Update candle with next few points
    for (let j = 1; j < updatesPerCandle && i + j < yesData.length; j++) {
      // Scale volatility appropriately for probability data (0-1 range)
      const volatility = (Math.random() - 0.5) * 0.02; // ±0.01 for Yes data
      const value = Math.max(0, Math.min(1, yesData[i + j].value + volatility)); // Clamp to [0,1]
      candle = updateCandle(candle, value);
    }
    
    candlestickData.push(candle);
  }
  
  return candlestickData;
}

/**
 * GENERATE NO CANDLESTICK DATA
 * Creates candlestick data specifically from No series data
 */
export function generateNoCandlestickData(
  noData: Array<{time: any, value: number}>
): CandlestickData[] {
  const createCandle = (val: number, time: any): CandlestickData => ({
    time,
    open: val,
    high: val,
    low: val,
    close: val,
  });

  const updateCandle = (candle: CandlestickData, val: number): CandlestickData => ({
    time: candle.time,
    close: val,
    open: candle.open,
    low: Math.min(candle.low, val),
    high: Math.max(candle.high, val),
  });

  const candlestickData: CandlestickData[] = [];
  const updatesPerCandle = 5;
  
  for (let i = 0; i < noData.length; i += updatesPerCandle) {
    const baseTime = noData[i].time;
    const baseValue = noData[i].value;
    
    let candle = createCandle(baseValue, baseTime);
    
    // Update candle with next few points
    for (let j = 1; j < updatesPerCandle && i + j < noData.length; j++) {
      // Scale volatility appropriately for probability data (0-1 range)
      const volatility = (Math.random() - 0.5) * 0.02; // ±0.01 for No data
      const value = Math.max(0, Math.min(1, noData[i + j].value + volatility)); // Clamp to [0,1]
      candle = updateCandle(candle, value);
    }
    
    candlestickData.push(candle);
  }
  
  return candlestickData;
}

/**
 * CANDLESTICK SERIES MANAGEMENT
 * Utilities for creating and managing candlestick series
 */
export class CandlestickManager {
  private chart: any;
  private series: any = null;
  private candlestickData: CandlestickData[] = [];
  private intervalMs: number = 5 * 60 * 1000; // 5 minutes default

  constructor(chart: any, intervalMs: number = 5 * 60 * 1000) {
    this.chart = chart;
    this.intervalMs = intervalMs;
  }

  /**
   * Create and add candlestick series to the chart
   */
  createSeries(data: CandlestickData[], options: CandlestickOptions = defaultCandlestickOptions): any {
    if (this.series) {
      this.removeSeries();
    }

    this.series = this.chart.addSeries(CandlestickSeries, options);
    this.candlestickData = [...data]; // Store a copy of the data
    this.series.setData(data);
    return this.series;
  }

  /**
   * Update candlestick series with a new data point (for streaming)
   */
  update(newPoint: { time: any, value: number }): void {
    if (!this.series) return;

    // Convert time to unix timestamp if it's an object
    let currentTime: number
    if (typeof newPoint.time === 'object' && newPoint.time !== null) {
      // Handle lightweight-charts time object format
      if ('year' in newPoint.time) {
        const date = new Date(
          newPoint.time.year,
          newPoint.time.month - 1, // Month is 0-indexed in Date
          newPoint.time.day || 1,
          newPoint.time.hour || 0,
          newPoint.time.minute || 0,
          newPoint.time.second || 0
        )
        currentTime = Math.floor(date.getTime() / 1000) // Convert to unix timestamp
      } else {
        console.error('Unknown time object format:', newPoint.time)
        return
      }
    } else if (typeof newPoint.time === 'number') {
      currentTime = newPoint.time
    } else {
      console.error('Invalid time format:', newPoint.time)
      return
    }

    const intervalStart = Math.floor(currentTime / this.intervalMs) * this.intervalMs;
    
    // Find if we have a candlestick for this time interval
    let lastCandle = this.candlestickData[this.candlestickData.length - 1];
    
    if (lastCandle && lastCandle.time === intervalStart) {
      // Update existing candlestick (same interval)
      lastCandle.close = newPoint.value;
      lastCandle.high = Math.max(lastCandle.high, newPoint.value);
      lastCandle.low = Math.min(lastCandle.low, newPoint.value);
      
      // Update the chart series with the modified candle
      this.series.update(lastCandle);
    } else {
      // Create new candlestick (new interval)
      const newCandle: CandlestickData = {
        time: intervalStart,
        open: newPoint.value,
        high: newPoint.value,
        low: newPoint.value,
        close: newPoint.value
      };
      
      this.candlestickData.push(newCandle);
      this.series.update(newCandle);
    }
  }

  /**
   * Update existing series with new data
   */
  updateData(data: CandlestickData[]): void {
    if (this.series) {
      this.candlestickData = [...data]; // Store a copy of the data
      this.series.setData(data);
    }
  }

  /**
   * Remove the candlestick series from the chart
   */
  removeSeries(): void {
    if (this.series) {
      this.chart.removeSeries(this.series);
      this.series = null;
    }
  }

  /**
   * Get the current series reference
   */
  getSeries(): any {
    return this.series;
  }

  /**
   * Check if series exists
   */
  hasSeries(): boolean {
    return this.series !== null;
  }

  /**
   * Show the candlestick series
   */
  show(): void {
    if (this.series) {
      this.series.applyOptions({ visible: true });
    }
  }

  /**
   * Hide the candlestick series
   */
  hide(): void {
    if (this.series) {
      this.series.applyOptions({ visible: false });
    }
  }

  /**
   * Check if series is visible
   */
  isVisible(): boolean {
    if (!this.series) return false;
    // Get current options - if visible is not set, default is true
    const options = this.series.options();
    return options.visible !== false;
  }
}

import { TimeRange, ChartDataPoint, StreamingData } from './chart-types';

/**
 * REALISTIC DATA GENERATOR
 * Generates realistic streaming data for YES/NO price series with trending and smooth curves
 */
let randomFactor = 25 + Math.random() * 25;

// Enhanced random walk with trending and volatility
class MarketSimulator {
  private trendDirection: number = 1;
  private trendStrength: number = 0.2;
  private volatility: number = 0.05;
  private trendDuration: number = 50;
  private trendCounter: number = 0;
  
  constructor() {
    this.resetTrend();
  }
  
  private resetTrend() {
    this.trendDirection = Math.random() > 0.5 ? 1 : -1;
    this.trendStrength = 0.1 + Math.random() * 0.3; // Trend strength 0.1-0.4
    this.volatility = 0.02 + Math.random() * 0.08; // Volatility 0.02-0.1
    this.trendDuration = 20 + Math.random() * 80; // Trend lasts 20-100 points
    this.trendCounter = 0;
  }
  
  generateValue(i: number, previousValue: number): number {
    // Update trend occasionally
    this.trendCounter++;
    if (this.trendCounter > this.trendDuration) {
      this.resetTrend();
    }
    
    // Multiple sine wave components for realistic market movement
    const longTerm = Math.sin(i / 100) * 0.15;      // Long-term cycle
    const mediumTerm = Math.sin(i / 30) * 0.08;     // Medium-term cycle  
    const shortTerm = Math.sin(i / 8) * 0.04;       // Short-term fluctuations
    const noise = Math.sin(i / randomFactor) * 0.02; // Random noise
    
    // Trending component with momentum
    const trend = this.trendDirection * this.trendStrength * Math.sin(i / 50) * 0.1;
    
    // Combine all components
    const baseChange = longTerm + mediumTerm + shortTerm + noise + trend;
    
    // Add random volatility
    const randomChange = (Math.random() - 0.5) * this.volatility;
    
    // Apply change to previous value
    const newValue = previousValue + baseChange + randomChange;
    
    // Keep values in realistic range (0.1 to 0.9)
    return Math.max(0.1, Math.min(0.9, newValue));
  }
}

const samplePoint = (i: number): number =>
  i *
    (0.5 +
      Math.sin(i / 1) * 0.2 +
      Math.sin(i / 2) * 0.4 +
      Math.sin(i / randomFactor) * 0.8 +
      Math.sin(i / 50) * 0.5) +
  200 +
  i * 2;

/**
 * Generate sample data for different time ranges with realistic market behavior
 */
export const generateRangeData = (range: TimeRange): ChartDataPoint[] => {
  const now = new Date();
  let dataPoints: ChartDataPoint[] = [];
  
  const config = {
    '1H': { points: 400, interval: 60 * 60 * 1000, startDaysAgo: 1 },
    '1W': { points: 300, interval: 24 * 60 * 60 * 1000, startDaysAgo: 7 },
    '1M': { points: 200, interval: 24 * 60 * 60 * 1000, startDaysAgo: 30 },
    '1Y': { points: 200, interval: 30 * 24 * 60 * 60 * 1000, startDaysAgo: 365 },
  }[range];
  
  const startTime = new Date(now.getTime() - (config.startDaysAgo * 24 * 60 * 60 * 1000));
  
  // Initialize market simulator for realistic data
  const marketSim = new MarketSimulator();
  
  // Start with random but realistic initial value
  let yesValue = 0.4 + (Math.random() * 0.4); // Start between 0.4-0.8
  
  for (let i = 0; i < config.points; i++) {
    const currentTime = new Date(startTime.getTime() + (i * config.interval));
    const timestamp = Math.floor(currentTime.getTime() / 1000);
    
    // Generate realistic YES value using market simulator
    yesValue = marketSim.generateValue(i, yesValue);
    
    // NO value is correlated but has some independence
    // Add small random variance to make it not perfectly inverse
    const baseNoValue = 1 - yesValue;
    const noVariance = (Math.random() - 0.5) * 0.02; // Small variance
    let noValue = baseNoValue + noVariance;
    
    // Normalize to ensure they sum to approximately 1
    const total = yesValue + noValue;
    if (total > 0) {
      yesValue = yesValue / total;
      noValue = noValue / total;
    }
    
    // Ensure values stay in valid range
    yesValue = Math.max(0.05, Math.min(0.95, yesValue));
    noValue = Math.max(0.05, Math.min(0.95, noValue));
    
    dataPoints.push({
      time: timestamp,
      yesValue,
      noValue,
    });
  }
  
  return dataPoints;
};

/**
 * Generate streaming data for real-time updates with realistic market behavior
 * Will shift to a Kalshi/long-term web socket for the actual data generation long term
 */
export function generateStreamingData(
  numberOfPoints = 500,
  startAt = 100
): { initialData: StreamingData; realtimeUpdates: StreamingData } {
  randomFactor = 25 + Math.random() * 25;
  const now = new Date();
  const startDate = new Date(now.getTime() - (numberOfPoints * 24 * 60 * 60 * 1000));
  
  const initialData: StreamingData = { yes: [], no: [] };
  const realtimeUpdates: StreamingData = { yes: [], no: [] };
  
  // Initialize market simulators for both YES and NO series
  const yesMarketSim = new MarketSimulator();
  const noMarketSim = new MarketSimulator();
  
  // Start with realistic initial values
  let previousYesValue = 0.5 + (Math.random() - 0.5) * 0.3; // Start between 0.35-0.65
  let previousNoValue = 1 - previousYesValue;
  
  for (let i = 0; i < numberOfPoints; ++i) {
    const currentDate = new Date(startDate.getTime() + (i * 24 * 60 * 60 * 1000));
    // Use Unix timestamp instead of date string for consistency with static data
    const timestamp = Math.floor(currentDate.getTime() / 1000);
    
    // Generate realistic YES value using market simulator
    let yesValue = yesMarketSim.generateValue(i, previousYesValue);
    
    // Generate NO value with correlation to YES but some independence
    let noValue = noMarketSim.generateValue(i, previousNoValue);
    
    // Ensure they are somewhat correlated (inverse relationship with some variance)
    const correlationFactor = 0.8; // 80% correlation
    const targetNoValue = 1 - yesValue;
    noValue = (correlationFactor * targetNoValue) + ((1 - correlationFactor) * noValue);
    
    // Normalize to ensure they sum to approximately 1
    const total = yesValue + noValue;
    if (total > 0) {
      yesValue = yesValue / total;
      noValue = noValue / total;
    }
    
    // Ensure values stay in valid range
    yesValue = Math.max(0.05, Math.min(0.95, yesValue));
    noValue = Math.max(0.05, Math.min(0.95, noValue));
    
    previousYesValue = yesValue;
    previousNoValue = noValue;
    
    const yesPoint = { time: timestamp, value: yesValue };
    const noPoint = { time: timestamp, value: noValue };
    
    if (i < startAt) {
      initialData.yes.push(yesPoint);
      initialData.no.push(noPoint);
    } else {
      realtimeUpdates.yes.push(yesPoint);
      realtimeUpdates.no.push(noPoint);
    }
  }
  
  return { initialData, realtimeUpdates };
}
/**
 * Generator function for streaming updates
 */
export function* getNextRealtimeUpdate(realtimeData: StreamingData) {
  const maxLength = Math.max(realtimeData.yes.length, realtimeData.no.length);
  for (let i = 0; i < maxLength; i++) {
    yield {
      yes: realtimeData.yes[i] || null,
      no: realtimeData.no[i] || null
    };
  }
  return null;
}
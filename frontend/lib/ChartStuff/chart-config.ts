import { ColorType, TimeScaleOptions, Time } from 'lightweight-charts';

/**
 * GLOBAL CHART THEME CONFIGURATION
 * Centralized styling for all chart components
 */
export const CHART_THEME = {
  colors: {
    background: '#111111', // Match your market page background
    containerBackground: 'transparent', // Remove blue background
    border: '#232323', // Match your market page borders
    text: '#ffffff',
    textSecondary: '#bdbdbd',
    button: {
      default: 'transparent',
      hover: '#232323',
      active: '#333333',
      text: '#ffffff'
    },
    accent: {
      green: '#22c55e', // or use var(--strike-green) equivalent
      red: '#ef4444',   // or use var(--strike-red) equivalent
      blue: '#3b82f6'
    }
  },
  spacing: {
    padding: '0.5rem',
    margin: '0.25rem',
    borderRadius: '0.5rem'
  }
}

/**
 * CHART CONFIGURATION
 * Configuration options for the lightweight-charts library
 */
export const getChartOptions = (containerWidth: number, containerHeight?: number, timeRange?: string) => ({
  layout: { 
    textColor: CHART_THEME.colors.text, 
    background: { type: ColorType.Solid, color: CHART_THEME.colors.background },
    attributionLogo: false,
  },
  width: containerWidth,
  height: containerHeight || 400,
  grid: { 
    vertLines: { visible: false },
    horzLines: { visible: false }
  },
  timeScale: getTimeScaleOptions(timeRange),
});

/**
 * TIME SCALE CONFIGURATION
 * Custom time formatting for different time ranges
 */
export const getTimeScaleOptions = (timeRange?: string): Partial<TimeScaleOptions> => {
  const baseOptions: Partial<TimeScaleOptions> = {
    timeVisible: true,
    secondsVisible: false,
    rightOffset: 12,
    fixLeftEdge: false,
    fixRightEdge: false,
  }

  // For 1H view, show minutes:seconds format
  if (timeRange === '1H') {
    return {
      ...baseOptions,
      secondsVisible: true, // Show seconds for sub-minute precision
      tickMarkFormatter: (time: Time, tickMarkType: number, locale: string) => {
        const timestamp = typeof time === 'number' ? time : parseInt(time as string)
        const date = new Date(timestamp * 1000)
        const minutes = date.getMinutes().toString().padStart(2, '0')
        const seconds = date.getSeconds().toString().padStart(2, '0')
        
        // For different tick mark types, show different levels of detail
        switch (tickMarkType) {
          case 0: // Year
          case 1: // Month  
          case 2: // Day
            return `${minutes}:${seconds}`
          case 3: // Hour
            return `${date.getHours()}:${minutes}`
          case 4: // Minute
            return `${minutes}:${seconds}`
          default:
            return `${minutes}:${seconds}`
        }
      }
    }
  }

  return baseOptions
}

/**
 * CHART WATERMARK CONFIGURATION
 */
export const watermarkConfig = {
  horzAlign: 'left' as const,
  vertAlign: 'bottom' as const,
  lines: [{
    text: '',
    color: 'rgba(42, 171, 78, 0.5)',
    fontSize: 10,
  }],
};

/**
 * CHART SERIES STYLING
 * Configuration for the YES/NO series appearance using theme colors
 */
export const seriesOptions = {
  yes: { 
    color: CHART_THEME.colors.accent.green, 
    priceLineColor: CHART_THEME.colors.accent.green 
  },
  no: { 
    color: CHART_THEME.colors.accent.red, 
    priceLineColor: CHART_THEME.colors.accent.red 
  }
};

/**
 * CHART CONTAINER RETRY CONFIGURATION
 * Settings for waiting for the DOM element to be ready
 */
export const CHART_RETRY_CONFIG = {
  maxRetries: 20, // Try for up to 1 second (20 * 50ms)
  retryDelay: 50 // 50ms between retries
};

/**
 * UTILITY: Update chart time scale for range changes
 * Allows dynamic reconfiguration of time formatting
 */
export const updateChartTimeScale = (chart: any, timeRange: string) => {
  const timeScaleOptions = getTimeScaleOptions(timeRange)
  chart.timeScale().applyOptions(timeScaleOptions)
  console.log(`⏰ Updated chart time scale for range: ${timeRange}`)
}
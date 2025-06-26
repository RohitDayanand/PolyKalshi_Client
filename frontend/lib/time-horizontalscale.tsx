import { TimeRange, TIME_RANGES } from './ChartStuff/chart-types'

/**
 * TIME HORIZONTAL SCALE UTILITIES
 * Helper functions for calculating visible time ranges and handling timestamp conversions
 */

// Type union for different timestamp formats used in the system
export type TimestampType = number | string | Date

// Configuration for visible range offsets based on time ranges
const VISIBLE_RANGE_MULTIPLIERS: Record<TimeRange, number> = {
  '1H': 1.5,     // Show 1.5 hours back from last timestamp for 1H view
  '1W': 1.2,     // Show 1.2 weeks back from last timestamp for 1W view
  '1M': 1.5,     // Show 1.5 months back from last timestamp for 1M view  
  '1Y': 1.3,     // Show 1.3 years back from last timestamp for 1Y view
}

// Time conversion constants (in milliseconds)
const TIME_UNITS = {
  HOUR: 60 * 60 * 1000,
  DAY: 24 * 60 * 60 * 1000,
  WEEK: 7 * 24 * 60 * 60 * 1000,
  MONTH: 30 * 24 * 60 * 60 * 1000, // Approximate month
  YEAR: 365 * 24 * 60 * 60 * 1000, // Approximate year
} as const

/**
 * Convert various timestamp formats to milliseconds
 */
function normalizeTimestamp(timestamp: TimestampType): number {
  if (typeof timestamp === 'number') {
    // Check if it's seconds (< 10^10) or milliseconds (>= 10^10)
    return timestamp < 10000000000 ? timestamp * 1000 : timestamp
  } else if (typeof timestamp === 'string') {
    return new Date(timestamp).getTime()
  } else if (timestamp instanceof Date) {
    return timestamp.getTime()
  }
  throw new Error(`Invalid timestamp type: ${typeof timestamp}`)
}

/**
 * Convert milliseconds back to the original timestamp format
 */
function denormalizeTimestamp(milliseconds: number, originalType: TimestampType): TimestampType {
  if (typeof originalType === 'number') {
    // Return in same format as original - seconds or milliseconds
    return originalType < 10000000000 ? milliseconds / 1000 : milliseconds
  } else if (typeof originalType === 'string') {
    return new Date(milliseconds).toISOString()
  } else if (originalType instanceof Date) {
    return new Date(milliseconds)
  }
  throw new Error(`Invalid original timestamp type: ${typeof originalType}`)
}

/**
 * Calculate the visible range duration in milliseconds for a given time range
 */
function getVisibleRangeDuration(timeRange: TimeRange): number {
  const multiplier = VISIBLE_RANGE_MULTIPLIERS[timeRange]
  
  switch (timeRange) {
    case '1H':
      return TIME_UNITS.HOUR * multiplier
    case '1W':
      return TIME_UNITS.WEEK * multiplier
    case '1M':
      return TIME_UNITS.MONTH * multiplier
    case '1Y':
      return TIME_UNITS.YEAR * multiplier
    default:
      throw new Error(`Unknown time range: ${timeRange}`)
  }
}

/**
 * MAIN HELPER FUNCTION
 * 
 * Calculate the start of visible range based on last timestamp and time range.
 * Preserves the original timestamp format (number, string, or Date).
 * 
 * @param lastTimestamp - The most recent timestamp in any supported format
 * @param timeRange - The current time range view ('1H', '1W', '1M', '1Y')
 * @param currentDate - Optional current date override (defaults to Date.now())
 * @returns Start timestamp in the same format as the input lastTimestamp
 * 
 * @example
 * // With number timestamp (seconds)
 * const start = getVisibleRangeStart(1750039691, '1H')
 * // Returns: 1750034291 (1.5 hours earlier)
 * 
 * @example
 * // With Date object
 * const start = getVisibleRangeStart(new Date(), '1W')
 * // Returns: Date object 1.2 weeks earlier
 * 
 * @example
 * // With ISO string
 * const start = getVisibleRangeStart('2025-06-16T10:30:00Z', '1M')
 * // Returns: ISO string 1.5 months earlier
 */
export function getVisibleRangeStart<T extends TimestampType>(
  lastTimestamp: T,
  timeRange: TimeRange,
  currentDate?: Date
): T {
  // Normalize inputs to milliseconds
  const lastMs = normalizeTimestamp(lastTimestamp)
  const currentMs = currentDate ? currentDate.getTime() : Date.now()
  
  // Use the later of lastTimestamp or currentDate as the reference point
  const referenceMs = Math.max(lastMs, currentMs)
  
  // Calculate how far back to go
  const rangeDuration = getVisibleRangeDuration(timeRange)
  
  // Calculate start time
  const startMs = referenceMs - rangeDuration
  
  // Convert back to original format and return
  return denormalizeTimestamp(startMs, lastTimestamp) as T
}

/**
 * UTILITY: Get visible range duration in human-readable format
 */
export function getVisibleRangeDurationText(timeRange: TimeRange): string {
  const multiplier = VISIBLE_RANGE_MULTIPLIERS[timeRange]
  
  switch (timeRange) {
    case '1H':
      return `${multiplier} hours`
    case '1W':
      return `${multiplier} weeks`
    case '1M':
      return `${multiplier} months`
    case '1Y':
      return `${multiplier} years`
    default:
      return 'Unknown range'
  }
}

/**
 * UTILITY: Validate time range
 */
export function isValidTimeRange(range: string): range is TimeRange {
  return TIME_RANGES.includes(range as TimeRange)
}

/**
 * UTILITY: Get all supported time ranges with their visible durations
 */
export function getTimeRangeInfo() {
  return TIME_RANGES.map(range => ({
    range,
    multiplier: VISIBLE_RANGE_MULTIPLIERS[range],
    durationText: getVisibleRangeDurationText(range),
    durationMs: getVisibleRangeDuration(range)
  }))
}

// Type for LightweightCharts BusinessDay
interface BusinessDay {
  year: number
  month: number
  day: number
}

// Union type for all supported input formats
export type DateInputType = BusinessDay | string | number | Date | null | undefined

/**
 * UNIVERSAL DATE TO UTC TIMESTAMP CONVERTER
 * 
 * Converts various date formats to UTC timestamps (milliseconds since epoch).
 * Returns null if the input doesn't match supported formats.
 * 
 * Supported formats:
 * 1. BusinessDay objects: { year: 2021, month: 2, day: 3 }
 * 2. Date string literals: '2021-02-03', '2021-02-03T10:30:00Z', etc.
 * 3. UTC timestamps: numbers (seconds or milliseconds)
 * 4. Date objects
 * 
 * @param input - Any date-like input
 * @returns UTC timestamp in milliseconds, or null if invalid
 * 
 * @example
 * // BusinessDay object
 * toUtcTimestamp({ year: 2021, month: 2, day: 3 }) // 1612310400000
 * 
 * @example  
 * // Date string
 * toUtcTimestamp('2021-02-03') // 1612310400000
 * toUtcTimestamp('2021-02-03T10:30:00Z') // 1612348200000
 * 
 * @example
 * // UTC timestamp (auto-detects seconds vs milliseconds)
 * toUtcTimestamp(1612310400) // 1612310400000 (seconds → milliseconds)
 * toUtcTimestamp(1612310400000) // 1612310400000 (already milliseconds)
 * 
 * @example
 * // Invalid inputs
 * toUtcTimestamp('invalid-date') // null
 * toUtcTimestamp({}) // null
 * toUtcTimestamp(null) // null
 */
import { UTCTimestamp } from 'lightweight-charts';

export function toUtcTimestamp(input: unknown): UTCTimestamp | null {
  try {
    // 1. Handle null/undefined
    if (input == null) return null;

    // 2. BusinessDay object
    if (
      typeof input === 'object' &&
      input !== null &&
      !Array.isArray(input) &&
      !(input instanceof Date)
    ) {
      const maybeBD = input as { year: number; month: number; day: number };
      if (
        typeof maybeBD.year === 'number' &&
        typeof maybeBD.month === 'number' &&
        typeof maybeBD.day === 'number'
      ) {
        const { year, month, day } = maybeBD;
        if (year < 1900 || year > 3000 || month < 1 || month > 12 || day < 1 || day > 31) {
          return null;
        }
        const date = new Date(Date.UTC(year, month - 1, day));
        return Math.floor(date.getTime() / 1000) as UTCTimestamp;
      }
    }

    // 3. Date object
    if (input instanceof Date) {
      const ms = input.getTime();
      return isNaN(ms) ? null : Math.floor(ms / 1000) as UTCTimestamp;
    }

    // 4. String (attempt to parse as date)
    if (typeof input === 'string') {
      const parsed = new Date(input.trim());
      return isNaN(parsed.getTime()) ? null : Math.floor(parsed.getTime() / 1000) as UTCTimestamp;
    }

    // 5. Number (milliseconds or seconds)
    if (typeof input === 'number') {
      if (!isFinite(input) || input < 0) return null;
      const seconds = input < 1e10 ? input : input / 1000;
      return Math.floor(seconds) as UTCTimestamp;
    }

    // 6. Fallback
    return null;
  } catch {
    return null;
  }
}


/**
 * UTILITY: Check if input is a valid BusinessDay object
 */
export function isBusinessDay(input: any): input is BusinessDay {
  return typeof input === 'object' && 
         input !== null && 
         typeof input.year === 'number' && 
         typeof input.month === 'number' && 
         typeof input.day === 'number' &&
         input.year >= 1900 && input.year <= 3000 &&
         input.month >= 1 && input.month <= 12 &&
         input.day >= 1 && input.day <= 31
}

/**
 * UTILITY: Check if string looks like a date
 */
export function isDateString(input: string): boolean {
  const trimmed = input.trim()
  const dateRegex = /^\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}:\d{2}(?:\.\d{3})?(?:Z|[+-]\d{2}:?\d{2})?)?$/
  return dateRegex.test(trimmed) && !isNaN(new Date(trimmed).getTime())
}

/**
 * UTILITY: Get input type description for debugging
 */
export function getDateInputType(input: DateInputType): string {
  if (input == null) return 'null/undefined'
  if (input instanceof Date) return 'Date object'
  if (typeof input === 'number') return 'number (timestamp)'
  if (typeof input === 'string') return 'string (date literal)'
  if (isBusinessDay(input)) return 'BusinessDay object'
  return 'unknown/unsupported'
}

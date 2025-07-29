/**
 * Timestamp rounding utility for Polymarket API calls
 * Rounds end_ts to appropriate intervals based on range to prevent append errors
 */

interface TimeRange {
  startTs: number;
  endTs: number;
}

/**
 * Rounds a timestamp down to the specified interval in seconds
 */
function roundDownToInterval(timestamp: number, intervalSeconds: number): number {
  return Math.floor(timestamp / intervalSeconds) * intervalSeconds;
}

/**
 * Calculates properly rounded timestamp ranges for Polymarket API calls
 * 
 * @param range - Time range (1H, 1W, 1M, 1Y)
 * @param currTimestamp - Current timestamp in seconds (UNIX)
 * @returns Rounded start and end timestamps
 */
export function calculatePolymarketTimeRange(range: string, currTimestamp: number): TimeRange {
  const nowTs = Math.floor(currTimestamp);
  let endTs: number;
  let startTs: number;

  switch (range) {
    case '1H':
      // Round to last minute for hourly range
      endTs = roundDownToInterval(nowTs, 60); // Round down to last minute
      startTs = endTs - (60 * 60 * 6); // 6 hours back from rounded end
      break;
      
    case '1W':
      // Round to last hour for weekly range
      endTs = roundDownToInterval(nowTs, 3600); // Round down to last hour
      startTs = endTs - (7 * 24 * 60 * 60 * 2); // 2 weeks back from rounded end
      break;
      
    case '1M':
      // Round to last day for monthly range
      endTs = roundDownToInterval(nowTs, 86400); // Round down to last day (24 * 60 * 60)
      startTs = endTs - (30 * 24 * 60 * 60 * 6); // 6 months back from rounded end
      break;
      
    case '1Y':
      // Round to last day for yearly range
      endTs = roundDownToInterval(nowTs, 86400); // Round down to last day
      startTs = endTs - (365 * 24 * 60 * 60); // 1 year back from rounded end
      break;
      
    default:
      console.warn(`Unknown range ${range}, defaulting to 1 hour with minute rounding`);
      endTs = roundDownToInterval(nowTs, 60); // Round down to last minute
      startTs = endTs - (60 * 60); // 1 hour back from rounded end
  }

  return { startTs, endTs };
}

/**
 * Standard time range calculation for platforms that don't need rounding (like Kalshi)
 */
export function calculateStandardTimeRange(range: string, currTimestamp: number): TimeRange {
  const nowTs = Math.floor(currTimestamp);
  const endTs = nowTs; // No rounding for standard calculation
  
  let startTs: number;
  
  switch (range) {
    case '1H':
      startTs = nowTs - (60 * 60 * 6);
      break;
    case '1W':
      startTs = nowTs - (7 * 24 * 60 * 60 * 2);
      break;
    case '1M':
      startTs = nowTs - (30 * 24 * 60 * 60 * 6);
      break;
    case '1Y':
      startTs = nowTs - (365 * 24 * 60 * 60);
      break;
    default:
      console.warn(`Unknown range ${range}, defaulting to 1 hour`);
      startTs = nowTs - (60 * 60);
  }
  
  return { startTs, endTs };
}
// Mock: Polymarket end_ts rounding with real timestamps
// All timestamps are before current time and in chronological order

const currentTime = new Date('2024-01-15T14:30:00Z') // Mock current time
const nowTs = Math.floor(currentTime.getTime() / 1000) // 1705326600

console.log('Current Time:', currentTime.toISOString(), '(Unix:', nowTs, ')')
console.log('---')

// Historical timestamps in chronological order (all before current time)
const mockTimestamps = [
  { label: 'Market Created', time: new Date('2024-01-01T00:00:00Z') },
  { label: 'First Major Trade', time: new Date('2024-01-05T09:15:30Z') },
  { label: 'Price Peak', time: new Date('2024-01-08T16:45:22Z') },
  { label: 'Volume Spike', time: new Date('2024-01-12T11:23:45Z') },
  { label: 'Recent Activity', time: new Date('2024-01-15T13:15:12Z') }, // 1 hour 15 min ago
  { label: 'Last Trade', time: new Date('2024-01-15T14:25:33Z') }       // 4 min 27 sec ago
]

console.log('Historical Timestamps (chronological order, all before current):')
mockTimestamps.forEach((ts, i) => {
  const unixTs = Math.floor(ts.time.getTime() / 1000)
  const minutesAgo = Math.round((nowTs - unixTs) / 60)
  console.log(`${i + 1}. ${ts.label}: ${ts.time.toISOString()} (${unixTs}) - ${minutesAgo} min ago`)
})

console.log('\n---')

// Mock the calculateTimeRange function behavior
function mockCalculateTimeRange(range, type = 'initial', since) {
  const endTs = nowTs // Always current time
  let startTs
  
  if (type === 'update' && since) {
    startTs = Math.floor(since / 1000)
  } else {
    switch (range) {
      case '1H':
        startTs = nowTs - (60 * 60 * 6) // 6 hours back
        break
      case '1W':
        startTs = nowTs - (7 * 24 * 60 * 60 * 2) // 2 weeks back
        break
      case '1M':
        startTs = nowTs - (30 * 24 * 60 * 60 * 6) // 6 months back
        break
      case '1Y':
        startTs = nowTs - (365 * 24 * 60 * 60) // 1 year back
        break
      default:
        startTs = nowTs - (60 * 60) // 1 hour back
    }
  }
  
  return { startTs, endTs }
}

// Test different ranges
const ranges = ['1H', '1W', '1M', '1Y']
console.log('Range Calculations (all end at current time):')
ranges.forEach(range => {
  const { startTs, endTs } = mockCalculateTimeRange(range)
  const startDate = new Date(startTs * 1000)
  const endDate = new Date(endTs * 1000)
  const hoursBack = Math.round((endTs - startTs) / 3600)
  
  console.log(`${range}: start=${startDate.toISOString()} (${startTs}), end=${endDate.toISOString()} (${endTs}) - ${hoursBack}h range`)
})

console.log('\n---')

// Mock API URL generation
function mockBuildApiUrl(marketId, side, range) {
  const { startTs, endTs } = mockCalculateTimeRange(range)
  const marketStringId = `${marketId}&${side}&${range}`
  
  return `http://localhost:8000/api/polymarket/timeseries?market_string_id=${marketStringId}&start_ts=${startTs}&end_ts=${endTs}`
}

console.log('Sample API URLs:')
console.log('1H Range:', mockBuildApiUrl('POLY-123', 'yes', '1H'))
console.log('1W Range:', mockBuildApiUrl('POLY-123', 'yes', '1W'))
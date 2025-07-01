//Time aware rounding for the individual timestamp
import { DataPoint } from "./types"

export function chooseTimestamp(range: string, dataPoint: DataPoint): DataPoint {
    if (!dataPoint) {
      return dataPoint
    }

    const date = new Date(dataPoint.time * 1000)
  
    let flooredTime: number
  
    switch (range) {
    case '1H':
      // Floor to the minute (remove seconds and milliseconds)
      // e.g., 13:53:24.56 -> 13:53:00.00
      date.setSeconds(0, 0)
      flooredTime = Math.floor(date.getTime() / 1000) // Convert back to seconds
      break
      
    case '1W':
      // Floor to the hour (remove minutes, seconds, milliseconds)
      // e.g., 13:53:24.56 -> 13:00:00.00
      date.setMinutes(0, 0, 0)
      flooredTime = Math.floor(date.getTime() / 1000)
      break
      
    case '1M':
      // Floor to the day (remove hours, minutes, seconds, milliseconds)
      // e.g., 2025-06-30 13:53:24.56 -> 2025-06-30 00:00:00.00
      date.setHours(0, 0, 0, 0)
      flooredTime = Math.floor(date.getTime() / 1000)
      break
      
    case '1Y':
      // Floor to the week (Monday of the current week)
      // Get the day of week (0 = Sunday, 1 = Monday, etc.)
      const dayOfWeek = date.getDay()
      const daysToMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1 // Convert Sunday = 0 to Sunday = 6
      date.setDate(date.getDate() - daysToMonday)
      date.setHours(0, 0, 0, 0)
      flooredTime = Math.floor(date.getTime() / 1000)
      break
      
    default:
      // No flooring for unknown ranges
      flooredTime = Math.floor(dataPoint.time / 1000)
      console.warn(`Unknown time range: ${range}, using original timestamp`)
      break
  }

    return {
      ...dataPoint,
      time: flooredTime
    }
  }

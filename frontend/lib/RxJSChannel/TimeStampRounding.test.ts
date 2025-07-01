// Helper to convert ISO string to seconds
function toUnixSeconds(isoString: string): number {
  return Math.floor(new Date(isoString).getTime() / 1000)
}

import { chooseTimestamp } from "./util";
import { DataPoint } from "./types";

test('Seconds config', () => {
  const input: DataPoint = {
    time: toUnixSeconds("2025-06-30T13:53:54Z"),
    value: 0.5,
    volume: 100
  }
  const result = chooseTimestamp("1H", input)
  expect(result.time).toBe(toUnixSeconds("2025-06-30T13:53:00Z")) // Floored to the minute
})

test('Week/minutes config', () => {
  const input: DataPoint = {
    time: toUnixSeconds("2025-06-30T13:53:24Z"),
    value: 0.5,
    volume: 100
  }
  const result = chooseTimestamp("1W", input)
  expect(result.time).toBe(toUnixSeconds("2025-06-30T13:00:00Z")) // Floored to the minute
})
/**
 * Utility functions for consistent number formatting across server and client
 * to prevent hydration mismatches
 */

/**
 * Format a number as currency with consistent formatting
 */
export function formatCurrency(value: number): string {
  return value.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
}

/**
 * Format a number with commas as thousands separator
 */
export function formatNumber(value: number): string {
  return Math.round(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")
}

/**
 * Format a price as cents (multiply by 100 and round)
 */
export function formatCents(value: number): string {
  return Math.round(value * 100).toString()
}

/**
 * Format a decimal number with fixed decimal places
 */
export function formatDecimal(value: number, decimals: number = 2): string {
  return value.toFixed(decimals)
}

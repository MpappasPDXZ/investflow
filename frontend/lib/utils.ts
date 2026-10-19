import { type ClassValue, clsx } from "clsx"
import { format } from "date-fns"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Parse date using Midday Strategy to prevent timezone shifting.
 * Sets time to 12:00:00 (noon) to provide buffer against timezone offsets.
 * 
 * @param dateStr - Date string in format 'YYYY-MM-DD'
 * @returns ISO string with time set to 12:00:00 UTC
 */
export function formatDateMidday(dateStr: string): string {
  if (!dateStr) return '';
  
  // Parse the date string (YYYY-MM-DD format)
  const [year, month, day] = dateStr.split('-').map(Number);
  
  // Create the date at 12:00 PM UTC specifically
  const middayDate = new Date(Date.UTC(year, month - 1, day, 12, 0, 0));
  
  return middayDate.toISOString();
}

/**
 * Convert Date object or ISO string to YYYY-MM-DD format for input fields.
 * Handles timezone-aware dates by extracting just the date portion.
 * 
 * @param date - Date object or ISO string
 * @returns Date string in YYYY-MM-DD format
 */
export function toDateInputValue(date: Date | string): string {
  if (!date) return '';

  if (typeof date === 'string') {
    const match = date.match(/^(\d{4}-\d{2}-\d{2})/);
    if (match) return match[1];
  }

  const dateObj = typeof date === 'string' ? new Date(date) : date;
  const year = dateObj.getUTCFullYear();
  const month = String(dateObj.getUTCMonth() + 1).padStart(2, '0');
  const day = String(dateObj.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/** Local noon on the calendar day in the string, so comparisons do not shift a day. */
export function calendarDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  const raw = typeof value === 'string' ? value : value.toISOString();
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12, 0, 0);
}

/** Format a calendar date without shifting the day across timezones. */
export function formatCalendarDate(
  value: string | Date | null | undefined,
  pattern = 'MMM d, yyyy'
): string {
  if (!value) return '';
  const raw = typeof value === 'string' ? value : value.toISOString();
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return '';
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  return format(new Date(year, month - 1, day), pattern);
}


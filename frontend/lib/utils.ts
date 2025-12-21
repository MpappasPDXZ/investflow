import { type ClassValue, clsx } from "clsx"
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
  
  let dateObj: Date;
  
  if (typeof date === 'string') {
    dateObj = new Date(date);
  } else {
    dateObj = date;
  }
  
  // Extract year, month, day in UTC to avoid timezone issues
  const year = dateObj.getUTCFullYear();
  const month = String(dateObj.getUTCMonth() + 1).padStart(2, '0');
  const day = String(dateObj.getUTCDate()).padStart(2, '0');
  
  return `${year}-${month}-${day}`;
}


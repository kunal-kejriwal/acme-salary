/**
 * Display formatting for money.
 *
 * The API sends money as strings so it never passes through a float. These
 * helpers format for display only — nothing here feeds a value back to the
 * API, so the string stays the source of truth.
 *
 * The locale is pinned rather than left to the browser. Passing `undefined`
 * takes the viewer's locale, which on an en-IN machine renders 2,400,000 as
 * 24,00,000 — so the same salary would read differently for different people,
 * and a table mixing currencies would mix grouping conventions row by row.
 * One figure, one rendering, everywhere.
 */

const LOCALE = 'en-US'

export function money(value: string | number | undefined): string {
  if (value === undefined || value === null || value === '') return '—'
  const asNumber = Number(value)
  if (Number.isNaN(asNumber)) return String(value)
  return asNumber.toLocaleString(LOCALE, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function usd(value: string | number | undefined): string {
  const formatted = money(value)
  return formatted === '—' ? formatted : `$${formatted}`
}

export function compactUsd(value: string | number | undefined): string {
  if (value === undefined || value === null || value === '') return '—'
  const asNumber = Number(value)
  if (Number.isNaN(asNumber)) return String(value)
  return `$${asNumber.toLocaleString(LOCALE, {
    notation: 'compact',
    maximumFractionDigits: 1,
  })}`
}

export function dateTime(value: string | undefined): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

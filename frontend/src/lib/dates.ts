/**
 * Calendar dates as the API exchanges them: `YYYY-MM-DD`, in the user's own
 * timezone.
 *
 * Never build one with `toISOString()`: that is the UTC date, which east of
 * Greenwich is the day before at local midnight, and west of it the day after
 * late in the evening. A week then starts a day early and its first day shows
 * up empty.
 */

/** The local calendar date of `date`. */
export function toIsoDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

/** Local midnight on `iso`, or an invalid date if `iso` is not a date. */
export function fromIsoDate(iso: string): Date {
  return new Date(`${iso}T00:00:00`)
}

/** Today, `offsetDays` days on. */
export function todayIso(offsetDays = 0): string {
  const date = new Date()
  date.setDate(date.getDate() + offsetDays)
  return toIsoDate(date)
}

/** `count` consecutive dates from `start`; empty if `start` is not a date. */
export function datesFrom(start: string, count: number): string[] {
  const first = fromIsoDate(start)
  if (Number.isNaN(first.getTime())) return []
  return Array.from({ length: count }, (_, i) => {
    const day = new Date(first)
    day.setDate(first.getDate() + i)
    return toIsoDate(day)
  })
}

/** Every date from `start` to `end`, both included. */
export function datesBetween(start: string, end: string): string[] {
  const days: string[] = []
  const cursor = fromIsoDate(start)
  const last = fromIsoDate(end)
  while (cursor <= last) {
    days.push(toIsoDate(cursor))
    cursor.setDate(cursor.getDate() + 1)
  }
  return days
}

import { useEffect, useState } from "react"

/**
 * `value`, once it has stopped changing for `delayMs`. Lets a search box
 * query the server per pause rather than per keystroke.
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

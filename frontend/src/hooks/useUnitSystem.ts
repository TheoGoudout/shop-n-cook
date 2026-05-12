import { useCallback, useEffect, useState } from "react"
import {
  type ConvertedQuantity,
  type UnitSystem,
  UNIT_SYSTEM_KEY,
  convertUnit,
  getSavedUnitSystem,
} from "@/lib/units"

export function useUnitSystem() {
  const [unitSystem, setUnitSystemState] = useState<UnitSystem>(
    getSavedUnitSystem,
  )

  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === UNIT_SYSTEM_KEY) {
        setUnitSystemState(e.newValue === "imperial" ? "imperial" : "metric")
      }
    }
    window.addEventListener("storage", handler)
    return () => window.removeEventListener("storage", handler)
  }, [])

  const setUnitSystem = useCallback((system: UnitSystem) => {
    localStorage.setItem(UNIT_SYSTEM_KEY, system)
    setUnitSystemState(system)
  }, [])

  const convert = useCallback(
    (quantity: number, unit: string): ConvertedQuantity => {
      return convertUnit(quantity, unit, unitSystem)
    },
    [unitSystem],
  )

  return { unitSystem, setUnitSystem, convert }
}

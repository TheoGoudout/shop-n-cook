export type UnitSystem = "metric" | "imperial"

export const UNIT_SYSTEM_KEY = "unit-system"

/** Units that belong to the metric system and can be converted */
const METRIC_UNITS = new Set(["g", "kg", "ml", "L"])

/** Units that belong to the imperial system and can be converted */
const IMPERIAL_UNITS = new Set(["oz", "lb", "cup", "tbsp", "tsp"])

/** Conversion map: metric → imperial */
const TO_IMPERIAL: Record<string, { unit: string; factor: number }> = {
  g: { unit: "oz", factor: 0.035274 },
  kg: { unit: "lb", factor: 2.20462 },
  ml: { unit: "fl oz", factor: 0.033814 },
  L: { unit: "cup", factor: 4.22675 },
}

/** Conversion map: imperial → metric */
const TO_METRIC: Record<string, { unit: string; factor: number }> = {
  oz: { unit: "g", factor: 28.3495 },
  lb: { unit: "kg", factor: 0.453592 },
  cup: { unit: "ml", factor: 236.588 },
  tbsp: { unit: "ml", factor: 14.7868 },
  tsp: { unit: "ml", factor: 4.92892 },
}

/**
 * Round a number to a sensible number of significant digits for display.
 * - Values >= 100 → round to nearest integer
 * - Values >= 10 → 1 decimal place
 * - Values >= 1 → 2 decimal places
 * - Values < 1 → 3 decimal places
 */
function roundSmart(value: number): number {
  if (value >= 100) return Math.round(value)
  if (value >= 10) return Math.round(value * 10) / 10
  if (value >= 1) return Math.round(value * 100) / 100
  return Math.round(value * 1000) / 1000
}

export interface ConvertedQuantity {
  quantity: number
  unit: string
}

/**
 * Convert a quantity+unit to the preferred unit system.
 * If no conversion is needed (unit is already in target system, or unit is
 * universal like "piece", "bunch" etc.), returns the original values unchanged.
 */
export function convertUnit(
  quantity: number,
  unit: string,
  targetSystem: UnitSystem,
): ConvertedQuantity {
  if (targetSystem === "imperial" && METRIC_UNITS.has(unit)) {
    const conv = TO_IMPERIAL[unit]
    if (conv) {
      return { quantity: roundSmart(quantity * conv.factor), unit: conv.unit }
    }
  }

  if (targetSystem === "metric" && IMPERIAL_UNITS.has(unit)) {
    const conv = TO_METRIC[unit]
    if (conv) {
      return { quantity: roundSmart(quantity * conv.factor), unit: conv.unit }
    }
  }

  // Unit is already in target system, or is universal (piece, bunch, etc.)
  return { quantity, unit }
}

/** Read the saved unit system preference from localStorage */
export function getSavedUnitSystem(): UnitSystem {
  const saved = localStorage.getItem(UNIT_SYSTEM_KEY)
  return saved === "imperial" ? "imperial" : "metric"
}

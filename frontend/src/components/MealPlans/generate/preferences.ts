import { useEffect, useState } from "react"

import type { GenerateMenuRequest, MealType } from "@/client"

/** The four dietary switches, which map one-to-one onto request flags. */
export const DIETS = [
  ["require_vegan", "vegan"],
  ["require_vegetarian", "vegetarian"],
  ["require_gluten_free", "gluten_free"],
  ["require_dairy_free", "dairy_free"],
] as const

export type DietKey = (typeof DIETS)[number][0]

/** The meals a menu can plan on a day. */
export const PLANNED_MEALS = ["lunch", "dinner"] as const

export type PlannedMeal = (typeof PLANNED_MEALS)[number]

/** Which meals to plan on one weekday. */
export type DaySchedule = Record<PlannedMeal, boolean>

/** One entry per weekday, Monday first — the order the backend expects. */
export type WeeklySchedule = DaySchedule[]

/** Batch cooking: how many meals one cooking covers. 1 means no batching. */
export const BATCH_PORTIONS = [1, 2, 3] as const

export type BatchPortions = (typeof BATCH_PORTIONS)[number]

export interface MenuPreferences {
  name: string
  start: string
  days: number
  /** Blank means "from my household settings". */
  servings: string
  /** Blank means "from my settings". */
  budget: string
  /** Blank means no limit. */
  maxPrep: string
  schedule: WeeklySchedule
  batch: BatchPortions
  diets: Record<DietKey, boolean>
  matchSeason: boolean
  includePublic: boolean
}

export const SCHEDULE_PRESETS = {
  dinners: () => weekOf({ lunch: false, dinner: true }),
  every_meal: () => weekOf({ lunch: true, dinner: true }),
  weekend_lunches: () =>
    weekOf({ lunch: false, dinner: true }).map((day, i) =>
      i >= 5 ? { ...day, lunch: true } : day,
    ),
} as const

function weekOf(day: DaySchedule): WeeklySchedule {
  return Array.from({ length: 7 }, () => ({ ...day }))
}

function today(): string {
  const now = new Date()
  // Local date, not UTC: late in the evening UTC is already tomorrow.
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10)
}

export function defaultPreferences(): MenuPreferences {
  return {
    name: "",
    start: today(),
    days: 7,
    servings: "",
    budget: "",
    maxPrep: "",
    schedule: SCHEDULE_PRESETS.dinners(),
    batch: 1,
    diets: {
      require_vegan: false,
      require_vegetarian: false,
      require_gluten_free: false,
      require_dairy_free: false,
    },
    matchSeason: true,
    includePublic: true,
  }
}

const STORAGE_KEY = "menu-preferences"

/** What is remembered between visits: everything but this menu's dates and name. */
type Remembered = Omit<MenuPreferences, "name" | "start">

function load(): MenuPreferences {
  const defaults = defaultPreferences()
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaults
    const saved = JSON.parse(raw) as Partial<Remembered>
    const schedule =
      Array.isArray(saved.schedule) && saved.schedule.length === 7
        ? saved.schedule.map((day) => ({
            lunch: Boolean(day?.lunch),
            dinner: Boolean(day?.dinner),
          }))
        : defaults.schedule
    return {
      ...defaults,
      days: typeof saved.days === "number" ? saved.days : defaults.days,
      servings: typeof saved.servings === "string" ? saved.servings : "",
      budget: typeof saved.budget === "string" ? saved.budget : "",
      maxPrep: typeof saved.maxPrep === "string" ? saved.maxPrep : "",
      schedule,
      batch: BATCH_PORTIONS.includes(saved.batch as BatchPortions)
        ? (saved.batch as BatchPortions)
        : defaults.batch,
      diets: { ...defaults.diets, ...(saved.diets ?? {}) },
      matchSeason: saved.matchSeason ?? defaults.matchSeason,
      includePublic: saved.includePublic ?? defaults.includePublic,
    }
  } catch {
    return defaults
  }
}

/**
 * The generation form, remembered on this device between visits.
 *
 * A household tends to eat the same way every week, so the diet, the meals
 * planned each day and the batch cooking choice should not have to be set
 * again each time. The dates and the name are about one menu and are not kept.
 */
export function useMenuPreferences() {
  const [preferences, setPreferences] = useState<MenuPreferences>(load)

  useEffect(() => {
    const { name: _name, start: _start, ...remembered } = preferences
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(remembered))
    } catch {
      // Storage can be unavailable (private mode); remembering is a nicety.
    }
  }, [preferences])

  const update = (patch: Partial<MenuPreferences>) =>
    setPreferences((prev) => ({ ...prev, ...patch }))

  return { preferences, update }
}

const optionalNumber = (value: string) =>
  value.trim() === "" ? null : Number(value)

type MealsByWeekday = NonNullable<GenerateMenuRequest["meals_by_weekday"]>

/** The API request the preferences describe; the same for every call. */
export function toRequest(preferences: MenuPreferences): GenerateMenuRequest {
  return {
    name: preferences.name.trim() || null,
    start_date: preferences.start,
    days: preferences.days,
    servings: optionalNumber(preferences.servings),
    budget: preferences.budget.trim() === "" ? null : preferences.budget,
    max_prep_minutes: optionalNumber(preferences.maxPrep),
    match_season: preferences.matchSeason,
    include_public: preferences.includePublic,
    // `map` forgets the tuple length; a schedule always has seven days.
    meals_by_weekday: preferences.schedule.map((day) =>
      PLANNED_MEALS.filter((meal) => day[meal]),
    ) as MealType[][] as MealsByWeekday,
    batch_portions: preferences.batch,
    ...preferences.diets,
  }
}

/** Whether any day in the plan has a meal to plan at all. */
export function plansAnyMeal(preferences: MenuPreferences): boolean {
  const first = new Date(`${preferences.start}T00:00:00`)
  if (Number.isNaN(first.getTime())) return false
  for (let i = 0; i < Math.min(preferences.days, 7); i++) {
    const day = new Date(first)
    day.setDate(first.getDate() + i)
    // getDay() is Sunday-first; the schedule is Monday-first.
    const { lunch, dinner } = preferences.schedule[(day.getDay() + 6) % 7]
    if (lunch || dinner) return true
  }
  return false
}

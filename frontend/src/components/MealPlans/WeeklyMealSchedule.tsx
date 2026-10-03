import { useTranslation } from "react-i18next"

import type { GenerateMenuRequest, MealType } from "@/client"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

/** What can be planned on one day of the week. */
export const DAY_CHOICES = ["dinner", "lunch", "both", "none"] as const

export type DayChoice = (typeof DAY_CHOICES)[number]

/** One choice per weekday, Monday first — the order the backend expects. */
export type WeeklySchedule = DayChoice[]

export const DEFAULT_SCHEDULE: WeeklySchedule = Array(7).fill("dinner")

const MEALS_FOR_CHOICE: Record<DayChoice, MealType[]> = {
  dinner: ["dinner"],
  lunch: ["lunch"],
  both: ["lunch", "dinner"],
  none: [],
}

type MealsByWeekday = NonNullable<GenerateMenuRequest["meals_by_weekday"]>

/** The `meals_by_weekday` request field for a schedule. */
export function scheduleToMealsByWeekday(
  schedule: WeeklySchedule,
): MealsByWeekday {
  // `map` forgets the tuple length; a schedule always has seven days.
  return schedule.map((choice) => MEALS_FOR_CHOICE[choice]) as MealsByWeekday
}

// 1 January 2024 was a Monday; the six days after it name the rest of the week.
const MONDAY = new Date(2024, 0, 1)

interface WeeklyMealScheduleProps {
  value: WeeklySchedule
  onChange: (value: WeeklySchedule) => void
}

/** Pick, for each day of the week, which meals the generated menu covers. */
export function WeeklyMealSchedule({
  value,
  onChange,
}: WeeklyMealScheduleProps) {
  const { t, i18n } = useTranslation("mealPlans")

  const weekdayName = (index: number) => {
    const day = new Date(MONDAY)
    day.setDate(MONDAY.getDate() + index)
    return day.toLocaleDateString(i18n.language, { weekday: "long" })
  }

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{t("generate.schedule_label")}</p>
      <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
        {value.map((choice, index) => {
          const id = `gen-schedule-${index}`
          return (
            <div key={index} className="flex items-center gap-2">
              <Label htmlFor={id} className="w-24 shrink-0 capitalize">
                {weekdayName(index)}
              </Label>
              <Select
                value={choice}
                onValueChange={(next) =>
                  onChange(
                    value.map((c, i) =>
                      i === index ? (next as DayChoice) : c,
                    ),
                  )
                }
              >
                <SelectTrigger id={id} size="sm" className="min-w-0 flex-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DAY_CHOICES.map((option) => (
                    <SelectItem key={option} value={option}>
                      {t(`generate.schedule_${option}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )
        })}
      </div>
    </div>
  )
}

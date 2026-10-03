import { Check } from "lucide-react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import {
  BATCH_PORTIONS,
  DIETS,
  type MenuPreferences,
  PLANNED_MEALS,
  SCHEDULE_PRESETS,
  type WeeklySchedule,
} from "./preferences"

// 1 January 2024 was a Monday; the six days after it name the rest of the week.
const MONDAY = new Date(2024, 0, 1)

function weekdayName(index: number, locale: string, format: "short" | "long") {
  const day = new Date(MONDAY)
  day.setDate(MONDAY.getDate() + index)
  return day.toLocaleDateString(locale, { weekday: format })
}

function Section({
  title,
  hint,
  children,
}: {
  title: string
  hint?: string
  children: ReactNode
}) {
  return (
    <section className="space-y-2.5">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </section>
  )
}

/** A button that stays pressed: the building block of chips and segments. */
function Toggle({
  pressed,
  onClick,
  children,
  className,
  label,
}: {
  pressed: boolean
  onClick: () => void
  children: ReactNode
  className?: string
  label?: string
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      aria-label={label}
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center gap-1 rounded-md border text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        pressed
          ? "border-primary bg-primary text-primary-foreground"
          : "bg-background hover:bg-accent hover:text-accent-foreground",
        className,
      )}
    >
      {children}
    </button>
  )
}

/** Tap a cell to plan (or skip) that meal on that weekday. */
function MealGrid({
  value,
  onChange,
}: {
  value: WeeklySchedule
  onChange: (value: WeeklySchedule) => void
}) {
  const { t, i18n } = useTranslation("mealPlans")

  const toggle = (dayIndex: number, meal: (typeof PLANNED_MEALS)[number]) =>
    onChange(
      value.map((day, i) =>
        i === dayIndex ? { ...day, [meal]: !day[meal] } : day,
      ),
    )

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-[auto_repeat(7,minmax(0,1fr))] items-center gap-1">
        <span />
        {value.map((_, i) => (
          <span
            key={i}
            className="text-center text-[11px] font-medium uppercase text-muted-foreground"
          >
            {weekdayName(i, i18n.language, "short")}
          </span>
        ))}
        {PLANNED_MEALS.map((meal) => (
          <div key={meal} className="contents">
            <span className="pr-1 text-xs text-muted-foreground">
              {t(`meal_types.${meal}`)}
            </span>
            {value.map((day, i) => (
              <Toggle
                key={i}
                pressed={day[meal]}
                onClick={() => toggle(i, meal)}
                className="h-8"
                label={t("generate.meal_cell", {
                  meal: t(`meal_types.${meal}`),
                  day: weekdayName(i, i18n.language, "long"),
                })}
              >
                {day[meal] && <Check className="h-3.5 w-3.5" />}
              </Toggle>
            ))}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {(
          Object.keys(SCHEDULE_PRESETS) as (keyof typeof SCHEDULE_PRESETS)[]
        ).map((preset) => (
          <button
            key={preset}
            type="button"
            className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            onClick={() => onChange(SCHEDULE_PRESETS[preset]())}
          >
            {t(`generate.preset_${preset}`)}
          </button>
        ))}
      </div>
    </div>
  )
}

/** Everything the generated menu must respect, in the order people think of it. */
export function PreferencesPanel({
  value,
  onChange,
}: {
  value: MenuPreferences
  onChange: (patch: Partial<MenuPreferences>) => void
}) {
  const { t } = useTranslation("mealPlans")

  return (
    <div className="space-y-6">
      <Section title={t("generate.section_when")}>
        <div className="grid grid-cols-[1fr_auto] gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="gen-start">{t("add.start_label")}</Label>
            <Input
              id="gen-start"
              type="date"
              value={value.start}
              onChange={(e) => onChange({ start: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="gen-days">{t("generate.days_label")}</Label>
            <Input
              id="gen-days"
              type="number"
              min="1"
              max="31"
              className="w-20"
              value={value.days}
              onChange={(e) =>
                onChange({
                  days: Math.min(31, Math.max(1, Number(e.target.value) || 1)),
                })
              }
            />
          </div>
        </div>
      </Section>

      <Section
        title={t("generate.section_meals")}
        hint={t("generate.section_meals_hint")}
      >
        <MealGrid
          value={value.schedule}
          onChange={(schedule) => onChange({ schedule })}
        />
      </Section>

      <Section
        title={t("generate.batch_label")}
        hint={t(`generate.batch_help_${value.batch}`)}
      >
        <div className="grid grid-cols-3 gap-1">
          {BATCH_PORTIONS.map((portions) => (
            <Toggle
              key={portions}
              pressed={value.batch === portions}
              onClick={() => onChange({ batch: portions })}
              className="h-9"
            >
              {t(`generate.batch_${portions}`)}
            </Toggle>
          ))}
        </div>
      </Section>

      <Section title={t("generate.section_who")}>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="gen-servings">{t("generate.servings_label")}</Label>
            <Input
              id="gen-servings"
              type="number"
              min="1"
              value={value.servings}
              placeholder={t("generate.servings_placeholder")}
              onChange={(e) => onChange({ servings: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="gen-budget">{t("generate.budget_label")}</Label>
            <Input
              id="gen-budget"
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={value.budget}
              placeholder={t("generate.budget_placeholder")}
              onChange={(e) => onChange({ budget: e.target.value })}
            />
          </div>
        </div>
      </Section>

      <Section title={t("generate.diet_label")}>
        <div className="flex flex-wrap gap-1.5">
          {DIETS.map(([key, label]) => (
            <Toggle
              key={key}
              pressed={value.diets[key]}
              onClick={() =>
                onChange({
                  diets: { ...value.diets, [key]: !value.diets[key] },
                })
              }
              className="h-8 rounded-full px-3"
            >
              {value.diets[key] && <Check className="h-3.5 w-3.5" />}
              {t(`generate.${label}`)}
            </Toggle>
          ))}
        </div>
      </Section>

      <Section title={t("generate.section_more")}>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="gen-prep">{t("generate.max_prep_label")}</Label>
            <Input
              id="gen-prep"
              type="number"
              min="0"
              value={value.maxPrep}
              placeholder={t("generate.max_prep_placeholder")}
              onChange={(e) => onChange({ maxPrep: e.target.value })}
            />
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="gen-season"
              checked={value.matchSeason}
              onCheckedChange={(c) => onChange({ matchSeason: Boolean(c) })}
            />
            <Label htmlFor="gen-season" className="cursor-pointer font-normal">
              {t("generate.season_label")}
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="gen-public"
              checked={value.includePublic}
              onCheckedChange={(c) => onChange({ includePublic: Boolean(c) })}
            />
            <Label htmlFor="gen-public" className="cursor-pointer font-normal">
              {t("generate.public_label")}
            </Label>
          </div>
        </div>
      </Section>
    </div>
  )
}

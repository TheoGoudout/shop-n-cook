import { Link } from "@tanstack/react-router"
import {
  CookingPot,
  ExternalLink,
  Pencil,
  Repeat2,
  Shuffle,
} from "lucide-react"
import { useTranslation } from "react-i18next"

import type { MenuPreview, MenuSlot, ProposedMeal } from "@/client"
import { ServingsStepper } from "@/components/Common/ServingsStepper"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { formatMoney } from "@/lib/money"
import { cn } from "@/lib/utils"

/** Order the slots of a day are shown in — how a day is actually eaten. */
const MEAL_ORDER = ["breakfast", "lunch", "dinner", "snack", "dessert"]

/** One slot of the menu, and which cooking (and which of its meals) fills it. */
export interface SlotRef {
  meal: number
  /** 0 for the meal where the dish is cooked, then 1, 2… for its leftovers. */
  portion: number
}

function rowsForDay(preview: MenuPreview, day: string) {
  const rows: (SlotRef & { slot: MenuSlot })[] = []
  preview.meals.forEach((meal, mealIndex) => {
    meal.slots.forEach((slot, portion) => {
      if (slot.entry_date === day) rows.push({ slot, meal: mealIndex, portion })
    })
  })
  const rank = (row: { slot: MenuSlot }) =>
    MEAL_ORDER.indexOf(row.slot.meal_type ?? "")
  return rows.sort((a, b) => rank(a) - rank(b))
}

interface MenuBoardProps {
  preview: MenuPreview
  /** Every date of the plan, including days with nothing planned. */
  days: string[]
  selected: Set<number>
  busy: boolean
  onToggleSelect: (meal: number, selected: boolean) => void
  onSwap: (meal: number) => void
  onChoose: (meal: number) => void
  onServings: (ref: SlotRef, servings: number) => void
}

function MealRow({
  meal,
  slot,
  portion,
  selected,
  busy,
  currency,
  onToggleSelect,
  onSwap,
  onChoose,
  onServings,
}: {
  meal: ProposedMeal
  slot: MenuSlot
  portion: number
  selected: boolean
  busy: boolean
  currency: string | undefined
  onToggleSelect: (selected: boolean) => void
  onSwap: () => void
  onChoose: () => void
  onServings: (servings: number) => void
}) {
  const { t, i18n } = useTranslation("mealPlans")
  const isLeftover = portion > 0
  const isBatch = meal.slots.length > 1
  const mealLabel = t(`meal_types.${slot.meal_type}`, {
    defaultValue: slot.meal_type ?? "",
  })
  const cost = isLeftover
    ? null
    : formatMoney(meal.estimated_cost, currency, i18n.language)
  const cookedOn = new Date(
    `${meal.slots[0].entry_date}T00:00:00`,
  ).toLocaleDateString(i18n.language, { weekday: "long" })

  return (
    <div
      className={cn(
        "rounded-md border p-2 transition-colors",
        isLeftover && "border-dashed bg-muted/40",
        selected && "border-primary ring-1 ring-primary",
      )}
    >
      <div className="flex items-start gap-2">
        <Checkbox
          className="mt-0.5"
          checked={selected}
          aria-label={t("review.select", { title: meal.recipe_title })}
          onCheckedChange={(c) => onToggleSelect(Boolean(c))}
        />
        <div className="min-w-0 flex-1 space-y-0.5">
          <div className="flex flex-wrap items-center gap-1">
            <Badge variant="secondary" className="px-1.5 py-0 text-[11px]">
              {mealLabel}
            </Badge>
            {isBatch && !isLeftover && (
              <Badge variant="outline" className="px-1.5 py-0 text-[11px]">
                <CookingPot className="h-3 w-3" />
                {t("review.batch_badge", { count: meal.slots.length })}
              </Badge>
            )}
            {isLeftover && (
              <Badge variant="outline" className="px-1.5 py-0 text-[11px]">
                <Repeat2 className="h-3 w-3" />
                {t("review.leftovers_badge")}
              </Badge>
            )}
          </div>
          <Link
            to="/recipes/$id"
            params={{ id: meal.recipe_id }}
            target="_blank"
            rel="noreferrer"
            className="group inline-flex max-w-full items-center gap-1 text-sm font-medium hover:underline"
            title={t("review.open_recipe")}
          >
            <span className="truncate">{meal.recipe_title}</span>
            <ExternalLink className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-60" />
          </Link>
          <p className="text-xs text-muted-foreground">
            {isLeftover
              ? t("review.leftovers", { day: cookedOn })
              : isBatch
                ? t("review.batch", {
                    count: meal.slots.length,
                    servings: meal.total_servings,
                  })
                : null}
            {cost && (
              <span className="tabular-nums">
                {isBatch ? " · " : ""}
                {cost}
              </span>
            )}
          </p>
        </div>
      </div>
      <div className="mt-1.5 flex items-center justify-between gap-2 pl-6">
        <ServingsStepper
          value={slot.servings ?? meal.servings}
          onChange={onServings}
          label={t("review.servings_for", {
            meal: mealLabel,
            title: meal.recipe_title,
          })}
        />
        <div className="flex">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            title={isBatch ? t("review.swap_batch") : t("generate.swap")}
            aria-label={isBatch ? t("review.swap_batch") : t("generate.swap")}
            disabled={busy}
            onClick={onSwap}
          >
            <Shuffle className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            title={t("review.choose")}
            aria-label={t("review.choose")}
            disabled={busy}
            onClick={onChoose}
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

/** The proposed menu as a week of day cards, every meal editable in place. */
export function MenuBoard({
  preview,
  days,
  selected,
  busy,
  onToggleSelect,
  onSwap,
  onChoose,
  onServings,
}: MenuBoardProps) {
  const { t, i18n } = useTranslation("mealPlans")

  return (
    <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
      {days.map((day) => {
        const rows = rowsForDay(preview, day)
        return (
          <Card key={day} className="gap-0 py-0">
            <CardHeader className="px-3 pt-3 pb-2">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {new Date(`${day}T00:00:00`).toLocaleDateString(i18n.language, {
                  weekday: "long",
                  day: "numeric",
                  month: "short",
                })}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 px-3 pb-3">
              {rows.length === 0 ? (
                <p className="text-xs italic text-muted-foreground">
                  {t("review.nothing_planned")}
                </p>
              ) : (
                rows.map((row) => (
                  <MealRow
                    key={`${row.meal}-${row.portion}`}
                    meal={preview.meals[row.meal]}
                    slot={row.slot}
                    portion={row.portion}
                    selected={selected.has(row.meal)}
                    busy={busy}
                    currency={preview.currency}
                    onToggleSelect={(on) => onToggleSelect(row.meal, on)}
                    onSwap={() => onSwap(row.meal)}
                    onChoose={() => onChoose(row.meal)}
                    onServings={(n) => onServings(row, n)}
                  />
                ))
              )}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

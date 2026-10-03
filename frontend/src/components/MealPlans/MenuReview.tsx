import { useQuery } from "@tanstack/react-query"
import { Pencil, Shuffle, X } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import {
  type GenerateMenuRequest,
  MealPlansService,
  type MenuPreview,
  type MenuSlot,
  type ProposedMealIn,
} from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { useCrudMutation } from "@/hooks/useCrudMutation"
import { formatMoney } from "@/lib/money"

/** Order the slots of a day are shown in — how a day is actually eaten. */
const MEAL_ORDER = ["breakfast", "lunch", "dinner", "snack", "dessert"]

function randomSeed(): number {
  return Math.floor(Math.random() * 1_000_000)
}

/** One slot of the menu, and which cooking (and which of its meals) fills it. */
interface Row {
  slot: MenuSlot
  meal: number
  /** 0 for the meal where the dish is cooked, then 1, 2… for its leftovers. */
  portion: number
}

function rowsByDay(preview: MenuPreview): [string, Row[]][] {
  const days = new Map<string, Row[]>()
  preview.meals.forEach((meal, mealIndex) => {
    meal.slots.forEach((slot, portion) => {
      const rows = days.get(slot.entry_date) ?? []
      rows.push({ slot, meal: mealIndex, portion })
      days.set(slot.entry_date, rows)
    })
  })
  const rank = (row: Row) => MEAL_ORDER.indexOf(row.slot.meal_type ?? "")
  return [...days.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, rows]) => [day, rows.sort((a, b) => rank(a) - rank(b))])
}

/** Pick a recipe by hand, among those matching the menu's preferences. */
function RecipePicker({
  request,
  slot,
  onPick,
  onClose,
}: {
  request: GenerateMenuRequest
  slot: MenuSlot
  onPick: (recipeId: string) => void
  onClose: () => void
}) {
  const { t } = useTranslation("mealPlans")
  const [search, setSearch] = useState("")

  const { data: options, isLoading } = useQuery({
    queryKey: ["menu-options", request, slot.meal_type, search],
    queryFn: () =>
      MealPlansService.menuRecipeOptions({
        requestBody: {
          ...request,
          meal_type: slot.meal_type,
          search: search || null,
        },
      }),
  })

  return (
    <div className="mt-2 space-y-2 rounded-md border bg-muted/40 p-2">
      <div className="flex items-center gap-2">
        <Input
          autoFocus
          value={search}
          placeholder={t("review.search_placeholder")}
          onChange={(e) => setSearch(e.target.value)}
          className="h-8"
        />
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          title={t("review.close_picker")}
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="max-h-40 overflow-y-auto">
        {!isLoading && (options ?? []).length === 0 ? (
          <p className="px-2 py-1 text-xs text-muted-foreground italic">
            {t("review.no_options")}
          </p>
        ) : (
          (options ?? []).map((option) => (
            <button
              type="button"
              key={option.id}
              className="block w-full truncate rounded px-2 py-1 text-left text-sm hover:bg-accent"
              onClick={() => onPick(option.id)}
            >
              {option.title}
            </button>
          ))
        )}
      </div>
    </div>
  )
}

/**
 * Review a proposed menu before it is saved.
 *
 * Every change goes back through the preview endpoint, so swaps and recipes
 * chosen by hand obey the same preferences as the generated menu, and costs
 * stay computed server-side.
 */
export function MenuReview({
  preview,
  request,
  onPreviewChange,
}: {
  preview: MenuPreview
  request: GenerateMenuRequest
  onPreviewChange: (preview: MenuPreview) => void
}) {
  const { t, i18n } = useTranslation("mealPlans")
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [picking, setPicking] = useState<string | null>(null)

  const rework = useCrudMutation({
    mutationFn: ({
      meals,
      replace,
    }: {
      meals: ProposedMealIn[]
      replace: number[]
    }) =>
      MealPlansService.previewMenu({
        requestBody: { ...request, seed: randomSeed(), meals, replace },
      }),
    onSuccess: (next) => {
      onPreviewChange(next)
      setSelected(new Set())
      setPicking(null)
    },
  })

  const currentMeals = (): ProposedMealIn[] =>
    preview.meals.map(({ recipe_id, slots }) => ({ recipe_id, slots }))

  const swap = (meals: number[]) =>
    rework.mutate({ meals: currentMeals(), replace: meals })

  const choose = (meal: number, recipeId: string) =>
    rework.mutate({
      meals: currentMeals().map((m, i) =>
        i === meal ? { ...m, recipe_id: recipeId } : m,
      ),
      replace: [],
    })

  const toggle = (meal: number, checked: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (checked) next.add(meal)
      else next.delete(meal)
      return next
    })

  const formatDay = (day: string, weekday: "long" | "short") =>
    new Date(`${day}T00:00:00`).toLocaleDateString(i18n.language, {
      weekday,
      ...(weekday === "short" ? { day: "numeric", month: "short" } : {}),
    })

  const total = formatMoney(
    preview.estimated_total,
    preview.currency,
    i18n.language,
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {t("review.summary", { count: preview.meals.length })}
          {total ? ` · ${t("review.total", { total })}` : ""}
          {preview.unpriced_meal_count
            ? ` · ${t("review.unpriced", { count: preview.unpriced_meal_count })}`
            : ""}
        </p>
        <Button
          variant="outline"
          size="sm"
          disabled={selected.size === 0 || rework.isPending}
          onClick={() => swap([...selected])}
        >
          <Shuffle />
          {t("review.swap_selected", { count: selected.size })}
        </Button>
      </div>

      <div className="space-y-3">
        {rowsByDay(preview).map(([day, rows]) => (
          <div key={day} className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {formatDay(day, "short")}
            </p>
            {rows.map((row) => {
              const meal = preview.meals[row.meal]
              const key = `${day}-${row.slot.meal_type}-${row.meal}`
              const portions = meal.slots.length
              const cost =
                row.portion === 0
                  ? formatMoney(
                      meal.estimated_cost,
                      preview.currency,
                      i18n.language,
                    )
                  : null
              const detail =
                row.portion > 0
                  ? t("review.leftovers", {
                      day: formatDay(meal.slots[0].entry_date, "long"),
                    })
                  : portions > 1
                    ? t("review.batch", {
                        count: portions,
                        servings: meal.servings * portions,
                      })
                    : null
              return (
                <div key={key} className="rounded-md border px-2 py-1.5">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      checked={selected.has(row.meal)}
                      aria-label={t("review.select", {
                        title: meal.recipe_title,
                      })}
                      onCheckedChange={(c) => toggle(row.meal, Boolean(c))}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {meal.recipe_title}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {t(`meal_types.${row.slot.meal_type}`, {
                          defaultValue: row.slot.meal_type ?? "",
                        })}
                        {detail ? ` · ${detail}` : ""}
                        {cost ? ` · ${cost}` : ""}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      title={t("generate.swap")}
                      disabled={rework.isPending}
                      onClick={() => swap([row.meal])}
                    >
                      <Shuffle className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      title={t("review.choose")}
                      disabled={rework.isPending}
                      onClick={() => setPicking(picking === key ? null : key)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  {picking === key && (
                    <RecipePicker
                      request={request}
                      slot={meal.slots[0]}
                      onPick={(recipeId) => choose(row.meal, recipeId)}
                      onClose={() => setPicking(null)}
                    />
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

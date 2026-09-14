import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ArrowLeft, ShoppingCart, Trash2 } from "lucide-react"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"

import {
  type MealPlanEntryPublic,
  type MealPlanPublic,
  MealPlansService,
} from "@/client"
import { AddEntryDialog } from "@/components/MealPlans/AddEntryDialog"
import PendingItems from "@/components/Pending/PendingItems"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useCrudMutation } from "@/hooks/useCrudMutation"
import { APP_NAME } from "@/lib/config"
import { formatMoney } from "@/lib/money"

/** Order the slots are shown in — how a day is actually eaten. */
const MEAL_ORDER = [
  "breakfast",
  "lunch",
  "dinner",
  "snack",
  "dessert",
  "drink",
  "other",
] as const

function getPlanQueryOptions(id: string) {
  return {
    queryFn: () => MealPlansService.readMealPlan({ id }),
    queryKey: ["meal-plan", id],
  }
}

export const Route = createFileRoute("/_layout/meal-plans/$id")({
  component: MealPlanDetail,
  head: () => ({
    meta: [{ title: `Meal Plan - ${APP_NAME}` }],
  }),
})

/** Every date the plan spans, inclusive. */
function daysBetween(start: string, end: string): string[] {
  const days: string[] = []
  const cursor = new Date(`${start}T00:00:00`)
  const last = new Date(`${end}T00:00:00`)
  while (cursor <= last) {
    days.push(cursor.toISOString().slice(0, 10))
    cursor.setDate(cursor.getDate() + 1)
  }
  return days
}

function EntryRow({
  entry,
  planId,
  currency,
}: {
  entry: MealPlanEntryPublic
  planId: string
  currency: string | undefined
}) {
  const { t } = useTranslation("mealPlans")
  const { i18n } = useTranslation("common")

  const remove = useCrudMutation({
    mutationFn: () =>
      MealPlansService.deleteEntry({ id: planId, entryId: entry.id }),
    invalidateKeys: [["meal-plan", planId], ["meal-plans"]],
  })

  const cost = formatMoney(entry.estimated_cost, currency, i18n.language)

  return (
    <div className="group flex items-start gap-2">
      <div className="flex-1 min-w-0">
        <Link
          to="/recipes/$id"
          params={{ id: entry.recipe_id }}
          className="text-sm font-medium hover:underline line-clamp-2"
        >
          {entry.recipe_title}
        </Link>
        <p className="text-xs text-muted-foreground">
          {t(`meal_types.${entry.meal_type}`, {
            defaultValue: entry.meal_type ?? "",
          })}
          {" · "}
          {t("detail.servings", { count: entry.servings })}
          {cost ? ` · ${cost}` : ""}
        </p>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 opacity-0 group-hover:opacity-100 shrink-0"
        title={t("detail.remove")}
        onClick={() => remove.mutate()}
      >
        <Trash2 className="h-3 w-3" />
      </Button>
    </div>
  )
}

function WeekGrid({ plan }: { plan: MealPlanPublic }) {
  const { t } = useTranslation("mealPlans")
  const { i18n } = useTranslation("common")
  const days = daysBetween(plan.start_date, plan.end_date)
  const entries = plan.entries ?? []

  const rank = (type: string | null | undefined) => {
    const index = MEAL_ORDER.indexOf(type as (typeof MEAL_ORDER)[number])
    return index === -1 ? MEAL_ORDER.length : index
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
      {days.map((day) => {
        const forDay = entries
          .filter((e) => e.entry_date === day)
          .sort((a, b) => rank(a.meal_type) - rank(b.meal_type))
        const date = new Date(`${day}T00:00:00`)
        return (
          <Card key={day} className="flex flex-col">
            <CardHeader className="py-3 px-3">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {date.toLocaleDateString(i18n.language, {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                })}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-3 pb-3 space-y-3 flex-1 flex flex-col">
              <div className="space-y-3 flex-1">
                {forDay.length === 0 ? (
                  <p className="text-xs text-muted-foreground italic">
                    {t("detail.empty_day")}
                  </p>
                ) : (
                  forDay.map((entry) => (
                    <EntryRow
                      key={entry.id}
                      entry={entry}
                      planId={plan.id}
                      currency={plan.currency}
                    />
                  ))
                )}
              </div>
              <AddEntryDialog planId={plan.id} date={day} />
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

function MealPlanDetailContent() {
  const { t } = useTranslation("mealPlans")
  const { t: tCommon, i18n } = useTranslation("common")
  const { id } = Route.useParams()
  const navigate = useNavigate()
  const { data: plan } = useSuspenseQuery(getPlanQueryOptions(id))

  const generate = useCrudMutation({
    mutationFn: () => MealPlansService.generateShoppingList({ id }),
    successMessage: t("detail.generated"),
    invalidateKeys: [["meal-plan", id], ["shopping-lists"]],
    onSuccess: (list) => {
      navigate({ to: "/shopping-lists/$id", params: { id: list.id } })
    },
  })

  const remove = useCrudMutation({
    mutationFn: () => MealPlansService.deleteMealPlan({ id }),
    successMessage: t("detail.deleted"),
    invalidateKeys: [["meal-plans"]],
    onSuccess: () => navigate({ to: "/meal-plans" }),
  })

  const total = formatMoney(plan.estimated_total, plan.currency, i18n.language)
  const hasEntries = (plan.entries?.length ?? 0) > 0

  return (
    <div className="w-full space-y-6">
      <Link
        to="/meal-plans"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {tCommon("back")}
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{plan.name}</h1>
          <p className="text-muted-foreground">
            {t("detail.entries", { count: plan.entries?.length ?? 0 })}
            {total ? ` · ${t("detail.week_total")}: ${total}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {plan.shopping_list_id && (
            <Button variant="outline" asChild>
              <Link
                to="/shopping-lists/$id"
                params={{ id: plan.shopping_list_id }}
              >
                <ShoppingCart />
                {t("detail.open_list")}
              </Link>
            </Button>
          )}
          <Button
            disabled={!hasEntries || generate.isPending}
            onClick={() => generate.mutate()}
          >
            <ShoppingCart />
            {plan.shopping_list_id
              ? t("detail.regenerate")
              : t("detail.generate")}
          </Button>
          <Button
            variant="outline"
            size="icon"
            title={t("detail.delete_title")}
            onClick={() => remove.mutate()}
          >
            <Trash2 />
          </Button>
        </div>
      </div>

      <WeekGrid plan={plan} />
    </div>
  )
}

function MealPlanDetail() {
  return (
    <Suspense fallback={<PendingItems />}>
      <MealPlanDetailContent />
    </Suspense>
  )
}

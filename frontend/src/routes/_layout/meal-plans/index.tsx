import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { CalendarDays } from "lucide-react"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"

import { MealPlansService } from "@/client"
import { AddMealPlan } from "@/components/MealPlans/AddMealPlan"
import PendingItems from "@/components/Pending/PendingItems"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { APP_NAME } from "@/lib/config"
import { formatMoney } from "@/lib/money"

function getMealPlansQueryOptions() {
  return {
    queryFn: () => MealPlansService.readMealPlans({ limit: 100 }),
    queryKey: ["meal-plans"],
  }
}

export const Route = createFileRoute("/_layout/meal-plans/")({
  component: MealPlans,
  head: () => ({
    meta: [{ title: `Meal Plans - ${APP_NAME}` }],
  }),
})

function MealPlansContent() {
  const { t } = useTranslation("mealPlans")
  const { i18n } = useTranslation("common")
  const { data } = useSuspenseQuery(getMealPlansQueryOptions())

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <CalendarDays className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">{t("page.empty_title")}</h3>
        <p className="text-muted-foreground">{t("page.empty_subtitle")}</p>
      </div>
    )
  }

  const formatRange = (start: string, end: string) =>
    `${new Date(start).toLocaleDateString(i18n.language, {
      day: "numeric",
      month: "short",
    })} – ${new Date(end).toLocaleDateString(i18n.language, {
      day: "numeric",
      month: "short",
    })}`

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.data.map((plan) => {
        const total = formatMoney(
          plan.estimated_total,
          plan.currency,
          i18n.language,
        )
        return (
          <Link key={plan.id} to="/meal-plans/$id" params={{ id: plan.id }}>
            <Card className="h-full transition-colors hover:border-primary">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{plan.name}</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {formatRange(plan.start_date, plan.end_date)}
                </p>
              </CardHeader>
              <CardContent className="flex items-baseline justify-between">
                <span className="text-sm text-muted-foreground">
                  {t("detail.entries", { count: plan.entries?.length ?? 0 })}
                </span>
                {total && (
                  <span className="text-sm font-medium tabular-nums">
                    {total}
                  </span>
                )}
              </CardContent>
            </Card>
          </Link>
        )
      })}
    </div>
  )
}

function MealPlans() {
  const { t } = useTranslation("mealPlans")
  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("page.title")}
          </h1>
          <p className="text-muted-foreground">{t("page.subtitle")}</p>
        </div>
        <AddMealPlan />
      </div>
      <Suspense fallback={<PendingItems />}>
        <MealPlansContent />
      </Suspense>
    </div>
  )
}

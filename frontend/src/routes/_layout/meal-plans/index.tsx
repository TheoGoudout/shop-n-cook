import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { CalendarDays, Sparkles } from "lucide-react"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"
import { MealPlansService } from "@/client"
import { EmptyListState } from "@/components/Common/EmptyListState"
import { PageHeader } from "@/components/Common/PageHeader"
import { AddMealPlan } from "@/components/MealPlans/AddMealPlan"
import PendingItems from "@/components/Pending/PendingItems"
import { Button } from "@/components/ui/button"
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
      <EmptyListState
        icon={CalendarDays}
        title={t("page.empty_title")}
        subtitle={t("page.empty_subtitle")}
      >
        <Button className="mt-4" asChild>
          <Link to="/meal-plans/generate">
            <Sparkles />
            {t("generate.trigger")}
          </Link>
        </Button>
      </EmptyListState>
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
      <PageHeader title={t("page.title")} subtitle={t("page.subtitle")}>
        <AddMealPlan />
        <Button asChild>
          <Link to="/meal-plans/generate">
            <Sparkles />
            {t("generate.trigger")}
          </Link>
        </Button>
      </PageHeader>
      <Suspense fallback={<PendingItems />}>
        <MealPlansContent />
      </Suspense>
    </div>
  )
}

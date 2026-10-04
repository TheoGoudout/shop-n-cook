import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useTranslation } from "react-i18next"

import { RecipesService, ShoppingListsService } from "@/client"
import { PantryPattern } from "@/components/Common/PantryPattern"
import { ActiveShoppingList } from "@/components/Dashboard/ActiveShoppingList"
import { BudgetSummary } from "@/components/Dashboard/BudgetSummary"
import { EmptyState } from "@/components/Dashboard/EmptyState"
import { QuickActions } from "@/components/Dashboard/QuickActions"
import { RecentRecipes } from "@/components/Dashboard/RecentRecipes"
import useAuth from "@/hooks/useAuth"
import { APP_NAME } from "@/lib/config"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: `Dashboard - ${APP_NAME}`,
      },
    ],
  }),
})

function Dashboard() {
  const { t } = useTranslation("dashboard")
  const { user: currentUser } = useAuth()

  const { data: recipesData } = useQuery({
    queryKey: ["recipes"],
    queryFn: () => RecipesService.readRecipes({ limit: 100 }),
  })

  const { data: listsData } = useQuery({
    queryKey: ["shopping-lists"],
    queryFn: () => ShoppingListsService.readShoppingLists({ limit: 100 }),
  })

  const isEmpty =
    (recipesData?.count ?? 0) === 0 && (listsData?.count ?? 0) === 0

  return (
    <div className="flex flex-col gap-8">
      <section className="relative overflow-hidden rounded-3xl border bg-[color-mix(in_oklch,var(--saffron)_20%,var(--card))] p-6 md:p-10">
        <PantryPattern className="left-[66%] hidden md:block" opacity={0.45} />
        <div className="relative flex max-w-2xl flex-col gap-6">
          <div>
            <h1 className="truncate text-3xl font-bold tracking-tight md:text-5xl">
              {t("greeting", {
                name: currentUser?.full_name || currentUser?.email,
              })}
            </h1>
            <p className="mt-2 text-lg text-muted-foreground">{t("welcome")}</p>
          </div>
          <QuickActions />
        </div>
      </section>

      {isEmpty && recipesData !== undefined && listsData !== undefined ? (
        <EmptyState />
      ) : (
        <>
          <BudgetSummary />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <RecentRecipes data={recipesData} />
            </div>
            <div className="lg:col-span-2">
              <ActiveShoppingList data={listsData} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}

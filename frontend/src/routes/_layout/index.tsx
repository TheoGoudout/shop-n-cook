import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useTranslation } from "react-i18next"

import { RecipesService, ShoppingListsService } from "@/client"
import { ActiveShoppingList } from "@/components/Dashboard/ActiveShoppingList"
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
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight truncate max-w-sm">
          {t("greeting", {
            name: currentUser?.full_name || currentUser?.email,
          })}
        </h1>
        <p className="text-muted-foreground">{t("welcome")}</p>
      </div>

      <QuickActions />

      {isEmpty && recipesData !== undefined && listsData !== undefined ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <RecentRecipes data={recipesData} />
          <ActiveShoppingList data={listsData} />
        </div>
      )}
    </div>
  )
}

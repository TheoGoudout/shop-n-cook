import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ChefHat } from "lucide-react"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import { APP_NAME } from "@/lib/config"
import { DataTable } from "@/components/Common/DataTable"
import PendingItems from "@/components/Pending/PendingItems"
import AddRecipe from "@/components/Recipes/AddRecipe"
import { useColumns } from "@/components/Recipes/columns"

function getRecipesQueryOptions() {
  return {
    queryFn: () => RecipesService.readRecipes({ limit: 100 }),
    queryKey: ["recipes"],
  }
}

export const Route = createFileRoute("/_layout/recipes/")({
  component: Recipes,
  head: () => ({
    meta: [{ title: `Recipes - ${APP_NAME}` }],
  }),
})

function RecipesTableContent() {
  const { t } = useTranslation("recipes")
  const { data } = useSuspenseQuery(getRecipesQueryOptions())
  const columns = useColumns()

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ChefHat className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">{t("page.empty_title")}</h3>
        <p className="text-muted-foreground">
          {t("page.empty_subtitle")}
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={data.data} />
}

function Recipes() {
  const { t } = useTranslation("recipes")

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("page.title")}</h1>
          <p className="text-muted-foreground">
            {t("page.subtitle")}
          </p>
        </div>
        <AddRecipe />
      </div>
      <Suspense fallback={<PendingItems />}>
        <RecipesTableContent />
      </Suspense>
    </div>
  )
}

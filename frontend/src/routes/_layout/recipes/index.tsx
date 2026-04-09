import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ChefHat } from "lucide-react"
import { Suspense } from "react"

import { RecipesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingItems from "@/components/Pending/PendingItems"
import AddRecipe from "@/components/Recipes/AddRecipe"
import { columns } from "@/components/Recipes/columns"
import { APP_NAME } from "@/lib/config"

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
  const { data } = useSuspenseQuery(getRecipesQueryOptions())

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ChefHat className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No recipes yet</h3>
        <p className="text-muted-foreground">
          Add your first recipe to get started
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={data.data} />
}

function Recipes() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Recipes</h1>
          <p className="text-muted-foreground">
            Manage your personal recipe collection
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

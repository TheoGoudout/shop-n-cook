import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { FlaskConical } from "lucide-react"
import { Suspense } from "react"

import { IngredientsService } from "@/client"
import { APP_NAME } from "@/lib/config"
import { DataTable } from "@/components/Common/DataTable"
import AddIngredient from "@/components/Ingredients/AddIngredient"
import { useColumns } from "@/components/Ingredients/columns"
import PendingItems from "@/components/Pending/PendingItems"
import useAuth from "@/hooks/useAuth"

function getIngredientsQueryOptions() {
  return {
    queryFn: () => IngredientsService.readIngredients({ limit: 500 }),
    queryKey: ["ingredients"],
  }
}

export const Route = createFileRoute("/_layout/ingredients")({
  component: Ingredients,
  head: () => ({
    meta: [{ title: `Ingredients - ${APP_NAME}` }],
  }),
})

function IngredientsTableContent() {
  const { data } = useSuspenseQuery(getIngredientsQueryOptions())
  const columns = useColumns()

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <FlaskConical className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No ingredients yet</h3>
        <p className="text-muted-foreground">
          Add the first ingredient to the catalog
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={data.data} />
}

function Ingredients() {
  const { user } = useAuth()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Ingredients</h1>
          <p className="text-muted-foreground">
            Browse and manage the ingredient catalog
          </p>
        </div>
        {user?.is_superuser && <AddIngredient />}
      </div>
      <Suspense fallback={<PendingItems />}>
        <IngredientsTableContent />
      </Suspense>
    </div>
  )
}

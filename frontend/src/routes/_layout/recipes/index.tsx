import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ChefHat, Search } from "lucide-react"
import { Suspense, useMemo, useState } from "react"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingItems from "@/components/Pending/PendingItems"
import AddRecipe from "@/components/Recipes/AddRecipe"
import { useColumns } from "@/components/Recipes/columns"
import {
  defaultFilters,
  RecipeFilterBar,
  type RecipeFilters,
} from "@/components/Recipes/RecipeFilterBar"
import { Input } from "@/components/ui/input"
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

function RecipesTableContent({
  search,
  filters,
}: {
  search: string
  filters: RecipeFilters
}) {
  const { t } = useTranslation("recipes")
  const { data } = useSuspenseQuery(getRecipesQueryOptions())
  const columns = useColumns()

  const filtered = useMemo(() => {
    return data.data.filter((r) => {
      if (search.trim()) {
        const q = search.toLowerCase()
        if (
          !r.title.toLowerCase().includes(q) &&
          !(r.description ?? "").toLowerCase().includes(q)
        )
          return false
      }
      if (
        filters.seasons.length > 0 &&
        !filters.seasons.some((s) => (r.seasons ?? []).includes(s))
      )
        return false
      if (filters.is_vegan && !r.is_vegan) return false
      if (filters.is_vegetarian && !r.is_vegetarian) return false
      if (filters.is_gluten_free && !r.is_gluten_free) return false
      if (filters.is_dairy_free && !r.is_dairy_free) return false
      if (filters.difficulty && r.difficulty !== filters.difficulty)
        return false
      if (filters.meal_type && r.meal_type !== filters.meal_type) return false
      if (
        filters.cuisine_type &&
        !(r.cuisine_type ?? "")
          .toLowerCase()
          .includes(filters.cuisine_type.toLowerCase())
      )
        return false
      return true
    })
  }, [data.data, search, filters])

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ChefHat className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">{t("page.empty_title")}</h3>
        <p className="text-muted-foreground">{t("page.empty_subtitle")}</p>
      </div>
    )
  }

  return <DataTable columns={columns} data={filtered} />
}

function Recipes() {
  const { t } = useTranslation("recipes")
  const [search, setSearch] = useState("")
  const [filters, setFilters] = useState<RecipeFilters>(defaultFilters)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("page.title")}
          </h1>
          <p className="text-muted-foreground">{t("page.subtitle")}</p>
        </div>
        <AddRecipe />
      </div>
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t("page.search_placeholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>
      <RecipeFilterBar
        filters={filters}
        onChange={setFilters}
        onClear={() => setFilters(defaultFilters)}
      />
      <Suspense fallback={<PendingItems />}>
        <RecipesTableContent search={search} filters={filters} />
      </Suspense>
    </div>
  )
}

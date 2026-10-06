import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ChefHat, Search } from "lucide-react"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import {
  defaultFilters,
  RecipeFilterBar,
  type RecipeFilters,
} from "@/components/Recipes/RecipeFilterBar"
import { RecipeGrid } from "@/components/Recipes/RecipeGrid"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { APP_NAME } from "@/lib/config"

export const Route = createFileRoute("/_layout/recipes/public")({
  component: PublicRecipes,
  head: () => ({
    meta: [{ title: `Community Recipes - ${APP_NAME}` }],
  }),
})

function PublicRecipes() {
  const { t } = useTranslation("recipes")
  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [filters, setFilters] = useState<RecipeFilters>(defaultFilters)
  const [debouncedFilters, setDebouncedFilters] =
    useState<RecipeFilters>(defaultFilters)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
      setDebouncedFilters(filters)
    }, 300)
    return () => clearTimeout(timer)
  }, [search, filters])

  const { data, isLoading } = useQuery({
    queryKey: [
      "public-recipes",
      debouncedSearch,
      debouncedFilters.seasons,
      debouncedFilters.is_vegan,
      debouncedFilters.is_vegetarian,
      debouncedFilters.is_gluten_free,
      debouncedFilters.is_dairy_free,
      debouncedFilters.difficulty,
      debouncedFilters.meal_type,
      debouncedFilters.cuisine_type,
    ],
    queryFn: () =>
      RecipesService.readPublicRecipes({
        search: debouncedSearch || null,
        limit: 100,
        seasons: debouncedFilters.seasons.length
          ? debouncedFilters.seasons
          : null,
        isVegan: debouncedFilters.is_vegan || null,
        isVegetarian: debouncedFilters.is_vegetarian || null,
        isGlutenFree: debouncedFilters.is_gluten_free || null,
        isDairyFree: debouncedFilters.is_dairy_free || null,
        difficulty: debouncedFilters.difficulty || null,
        mealType: debouncedFilters.meal_type || null,
        cuisineType: debouncedFilters.cuisine_type || null,
      }),
  })

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("public.title")}
        </h1>
        <p className="text-muted-foreground">{t("public.subtitle")}</p>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t("public.search_placeholder")}
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

      {isLoading ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-80 rounded-2xl" />
          ))}
        </div>
      ) : !data || data.data.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-center py-12">
          <div className="rounded-full bg-muted p-4 mb-4">
            <ChefHat className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold">{t("public.empty_title")}</h3>
          <p className="text-muted-foreground">{t("public.empty_subtitle")}</p>
        </div>
      ) : (
        <>
          <Badge variant="secondary" className="w-fit">
            {t("public.recipe_count", { count: data.count })}
          </Badge>
          <RecipeGrid recipes={data.data} community />
        </>
      )}
    </div>
  )
}

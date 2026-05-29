import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ChefHat, Clock, Search, User, Users } from "lucide-react"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import {
  defaultFilters,
  RecipeFilterBar,
  type RecipeFilters,
} from "@/components/Recipes/RecipeFilterBar"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { APP_NAME } from "@/lib/config"

export const Route = createFileRoute("/_layout/recipes/public")({
  component: PublicRecipes,
  head: () => ({
    meta: [{ title: `Community Recipes - ${APP_NAME}` }],
  }),
})

function RecipeCard({
  recipe,
}: {
  recipe: {
    id: string
    title: string
    description?: string | null
    servings?: number | null
    prep_time_minutes?: number | null
    cook_time_minutes?: number | null
    image_url?: string | null
    owner_id: string
    owner_name?: string | null
    is_vegan?: boolean
    is_vegetarian?: boolean
    is_gluten_free?: boolean
    is_dairy_free?: boolean
    meal_type?: string | null
    cuisine_type?: string | null
  }
}) {
  const { t } = useTranslation("recipes")
  const totalTime =
    (recipe.prep_time_minutes ?? 0) + (recipe.cook_time_minutes ?? 0)

  return (
    <Card className="flex flex-col overflow-hidden hover:shadow-md transition-shadow">
      {recipe.image_url && (
        <div className="h-40 overflow-hidden relative">
          <img
            src={recipe.image_url}
            alt={recipe.title}
            className="w-full h-full object-cover"
          />
          <div className="absolute top-2 left-2 flex flex-wrap gap-1">
            {recipe.is_vegan && (
              <Badge className="text-xs px-1.5 py-0.5 bg-green-600 hover:bg-green-600">
                {t("form.is_vegan_label")}
              </Badge>
            )}
            {!recipe.is_vegan && recipe.is_vegetarian && (
              <Badge className="text-xs px-1.5 py-0.5 bg-green-500 hover:bg-green-500">
                {t("form.is_vegetarian_label")}
              </Badge>
            )}
            {recipe.is_gluten_free && (
              <Badge variant="secondary" className="text-xs px-1.5 py-0.5">
                GF
              </Badge>
            )}
            {recipe.is_dairy_free && (
              <Badge variant="secondary" className="text-xs px-1.5 py-0.5">
                DF
              </Badge>
            )}
          </div>
        </div>
      )}
      <CardHeader className="pb-2">
        <CardTitle className="text-base leading-snug">
          <Link
            to="/recipes/$id"
            params={{ id: recipe.id }}
            className="hover:underline"
          >
            {recipe.title}
          </Link>
        </CardTitle>
        <div className="flex items-center justify-between">
          {recipe.owner_name && (
            <Link
              to="/profile/$userId"
              params={{ userId: recipe.owner_id }}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors w-fit"
            >
              <User className="h-3 w-3" />
              {recipe.owner_name}
            </Link>
          )}
          {recipe.cuisine_type && (
            <span className="text-xs text-muted-foreground">
              {recipe.cuisine_type}
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col gap-2">
        {recipe.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {recipe.description}
          </p>
        )}
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground mt-auto pt-2">
          {recipe.servings && (
            <span className="flex items-center gap-1">
              <Users className="h-3 w-3" />
              {t("detail.servings", { count: recipe.servings })}
            </span>
          )}
          {totalTime > 0 && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {t("columns.minutes", { count: totalTime })}
            </span>
          )}
          {recipe.meal_type && (
            <span className="capitalize">
              {t(`form.meal_${recipe.meal_type}`)}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-52 rounded-lg" />
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
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.data.map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

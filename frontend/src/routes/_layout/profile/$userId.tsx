import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, ChefHat, Clock, Search, Users } from "lucide-react"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { APP_NAME } from "@/lib/config"

export const Route = createFileRoute("/_layout/profile/$userId")({
  component: UserProfile,
  head: () => ({
    meta: [{ title: `Profile - ${APP_NAME}` }],
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
  }
}) {
  const { t } = useTranslation("recipes")
  const totalTime =
    (recipe.prep_time_minutes ?? 0) + (recipe.cook_time_minutes ?? 0)

  return (
    <Card className="flex flex-col overflow-hidden hover:shadow-md transition-shadow">
      {recipe.image_url && (
        <div className="h-40 overflow-hidden">
          <img
            src={recipe.image_url}
            alt={recipe.title}
            className="w-full h-full object-cover"
          />
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
        </div>
      </CardContent>
    </Card>
  )
}

function UserProfile() {
  const { t } = useTranslation("recipes")
  const { userId } = Route.useParams()
  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  const { data: recipes, isLoading } = useQuery({
    queryKey: ["public-recipes", userId, debouncedSearch],
    queryFn: () =>
      RecipesService.readPublicRecipes({
        ownerId: userId,
        search: debouncedSearch || null,
        limit: 100,
      }),
  })

  const displayName =
    recipes?.data[0]?.owner_name ?? t("profile.unknown_user")

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link to="/recipes/public">
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t("profile.back")}
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-32" />
        </div>
      ) : (
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{displayName}</h1>
          {recipes && (
            <p className="text-muted-foreground">
              {t("profile.recipe_count", { count: recipes.count })}
            </p>
          )}
        </div>
      )}

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t("public.search_placeholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-52 rounded-lg" />
          ))}
        </div>
      ) : !recipes || recipes.data.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-center py-12">
          <div className="rounded-full bg-muted p-4 mb-4">
            <ChefHat className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold">{t("profile.empty_title")}</h3>
          <p className="text-muted-foreground">{t("profile.empty_subtitle")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {recipes.data.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} />
          ))}
        </div>
      )}
    </div>
  )
}

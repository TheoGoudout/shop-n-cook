import { Link } from "@tanstack/react-router"
import { ChefHat } from "lucide-react"
import { useTranslation } from "react-i18next"

import type { RecipesPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

interface Props {
  data: RecipesPublic | undefined
}

export function RecentRecipes({ data }: Props) {
  const { t } = useTranslation("dashboard")

  if (data !== undefined && data.count === 0) return null

  const recent = data?.data.slice(-4).reverse() ?? []

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <ChefHat className="h-4 w-4" />
          {t("recent_recipes.title")}
        </CardTitle>
        <Link
          to="/recipes"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {t("recent_recipes.see_all")} →
        </Link>
      </CardHeader>
      <CardContent>
        {data === undefined ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {recent.map((recipe) => {
              const totalTime =
                recipe.prep_time_minutes != null &&
                recipe.cook_time_minutes != null
                  ? recipe.prep_time_minutes + recipe.cook_time_minutes
                  : null

              return (
                <Link
                  key={recipe.id}
                  to="/recipes/$id"
                  params={{ id: recipe.id }}
                  className="rounded-lg border bg-card p-3 transition-colors hover:bg-accent/30"
                >
                  <p className="line-clamp-1 text-sm font-semibold">
                    {recipe.title}
                  </p>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {recipe.servings != null && (
                      <Badge variant="secondary" className="text-xs">
                        {t("recent_recipes.servings", {
                          count: recipe.servings,
                        })}
                      </Badge>
                    )}
                    {recipe.prep_time_minutes != null && totalTime == null && (
                      <Badge variant="secondary" className="text-xs">
                        {t("recent_recipes.prep_min", {
                          count: recipe.prep_time_minutes,
                        })}
                      </Badge>
                    )}
                    {totalTime != null && (
                      <Badge variant="secondary" className="text-xs">
                        {t("recent_recipes.total_min", { count: totalTime })}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    {t("recent_recipes.ingredient_count", {
                      count: recipe.ingredients?.length ?? 0,
                    })}
                  </p>
                </Link>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

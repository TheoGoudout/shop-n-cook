import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, ChefHat, Clock, ExternalLink, Users } from "lucide-react"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import { APP_NAME } from "@/lib/config"
import { RecipeActionsMenu } from "@/components/Recipes/RecipeActionsMenu"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useUnitSystem } from "@/hooks/useUnitSystem"

function getRecipeQueryOptions(id: string) {
  return {
    queryFn: () => RecipesService.readRecipe({ id }),
    queryKey: ["recipe", id],
  }
}

export const Route = createFileRoute("/_layout/recipes/$id")({
  component: RecipeDetail,
  head: () => ({
    meta: [{ title: `Recipe - ${APP_NAME}` }],
  }),
})

function RecipeDetailContent() {
  const { t } = useTranslation("recipes")
  const { t: tCommon } = useTranslation("common")
  const { convert } = useUnitSystem()
  const { id } = Route.useParams()
  const { data: recipe } = useSuspenseQuery(getRecipeQueryOptions(id))

  const totalTime =
    (recipe.prep_time_minutes ?? 0) + (recipe.cook_time_minutes ?? 0)

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      {/* Recipe image */}
      {recipe.image_url && (
        <div className="rounded-lg overflow-hidden max-h-64 w-full">
          <img
            src={recipe.image_url}
            alt={recipe.title}
            className="w-full h-full object-cover"
          />
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h1 className="text-3xl font-bold tracking-tight">{recipe.title}</h1>
          {recipe.description && (
            <p className="text-muted-foreground mt-2 text-lg">
              {recipe.description}
            </p>
          )}
          {recipe.source_url && (
            <a
              href={recipe.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 mt-1 text-sm text-muted-foreground hover:text-foreground underline-offset-4 hover:underline"
            >
              <ExternalLink className="h-3 w-3" />
              {t("detail.source")}
            </a>
          )}
        </div>
        <RecipeActionsMenu recipe={recipe} />
      </div>

      {/* Meta badges */}
      <div className="flex flex-wrap gap-4 text-sm">
        {recipe.servings && (
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Users className="h-4 w-4" />
            <span>{t("detail.servings", { count: recipe.servings })}</span>
          </div>
        )}
        {recipe.prep_time_minutes != null && (
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>{t("detail.prep", { count: recipe.prep_time_minutes })}</span>
          </div>
        )}
        {recipe.cook_time_minutes != null && (
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>{t("detail.cook", { count: recipe.cook_time_minutes })}</span>
          </div>
        )}
        {totalTime > 0 && (
          <div className="flex items-center gap-1.5 font-medium">
            <Clock className="h-4 w-4" />
            <span>{t("detail.total", { count: totalTime })}</span>
          </div>
        )}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Ingredients */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t("detail.ingredients_title")}</CardTitle>
          </CardHeader>
          <CardContent>
            {(recipe.ingredients ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground italic">
                {t("detail.no_ingredients")}
              </p>
            ) : (
              <ul className="space-y-2">
                {(recipe.ingredients ?? []).map((ing) => {
                  const converted = convert(ing.quantity, ing.unit)
                  return (
                    <li key={ing.id} className="text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{ing.ingredient_name}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">
                            {converted.quantity} {tCommon(`unit_labels.${converted.unit}`, { defaultValue: converted.unit })}
                          </span>
                          <Badge variant="outline" className="text-xs capitalize">
                            {tCommon(`categories.${ing.ingredient_category}`, { defaultValue: ing.ingredient_category })}
                          </Badge>
                        </div>
                      </div>
                      {ing.notes && (
                        <p className="text-xs text-muted-foreground mt-0.5 italic">
                          {ing.notes}
                        </p>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Instructions */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t("detail.instructions_title")}</CardTitle>
          </CardHeader>
          <CardContent>
            {recipe.instructions ? (
              <p className="text-sm whitespace-pre-wrap leading-relaxed">
                {recipe.instructions}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground italic">
                {t("detail.no_instructions")}
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function RecipeDetail() {
  const { t } = useTranslation("recipes")

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link to="/recipes">
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t("detail.back")}
          </Link>
        </Button>
      </div>
      <Suspense
        fallback={
          <div className="flex items-center gap-2 text-muted-foreground">
            <ChefHat className="h-5 w-5 animate-pulse" />
            <span>{t("detail.loading")}</span>
          </div>
        }
      >
        <RecipeDetailContent />
      </Suspense>
    </div>
  )
}

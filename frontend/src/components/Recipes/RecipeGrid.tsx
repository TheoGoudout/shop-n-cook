import { Link } from "@tanstack/react-router"
import { Clock, Globe, ListChecks, User, Users } from "lucide-react"
import { useTranslation } from "react-i18next"

import type { RecipePublic } from "@/client"
import { mealTypeIcon } from "@/components/Common/categoryIcons"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { AddToShoppingList } from "./AddToShoppingList"
import { DietaryBadges } from "./DietaryBadges"
import { RecipeActionsMenu } from "./RecipeActionsMenu"
import { RecipeCover } from "./RecipeCover"

function RecipeCard({
  recipe,
  community,
}: {
  recipe: RecipePublic
  community: boolean
}) {
  const { t } = useTranslation("recipes")
  const total =
    (recipe.prep_time_minutes ?? 0) + (recipe.cook_time_minutes ?? 0)
  const MealIcon = mealTypeIcon(recipe.meal_type)

  return (
    <article className="group relative flex flex-col overflow-hidden rounded-2xl border bg-card shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="aspect-[4/3] overflow-hidden">
        <RecipeCover
          recipe={recipe}
          className="transition-transform duration-300 group-hover:scale-105"
        />
      </div>
      {/* right-14 keeps the row clear of the actions menu */}
      <div
        className={cn(
          "absolute left-3 top-3 flex flex-wrap gap-1",
          community ? "right-3" : "right-14",
        )}
      >
        {!community && recipe.is_public && (
          <Badge className="gap-1 bg-card/90 text-foreground backdrop-blur hover:bg-card/90">
            <Globe className="h-3 w-3" />
            {t("columns.public")}
          </Badge>
        )}
        <DietaryBadges recipe={recipe} compact />
      </div>
      {/* Above the card-wide link, so the menu stays clickable */}
      {!community && (
        <div className="absolute right-2 top-2 z-10 rounded-full bg-card/90 backdrop-blur">
          <RecipeActionsMenu recipe={recipe} />
        </div>
      )}
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <h3 className="font-display text-lg leading-snug">
          {/* after:inset-0 stretches the link over the whole card */}
          <Link
            to="/recipes/$id"
            params={{ id: recipe.id }}
            className="after:absolute after:inset-0 focus-visible:outline-none"
          >
            {recipe.title}
          </Link>
        </h3>
        {community && (recipe.owner_name || recipe.cuisine_type) && (
          <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
            {recipe.owner_name && (
              // relative z-10 lifts the author link above the card-wide one
              <Link
                to="/profile/$userId"
                params={{ userId: recipe.owner_id }}
                className="relative z-10 flex items-center gap-1 transition-colors hover:text-foreground"
              >
                <User className="size-3.5" aria-hidden="true" />
                {recipe.owner_name}
              </Link>
            )}
            {recipe.cuisine_type && <span>{recipe.cuisine_type}</span>}
          </div>
        )}
        {recipe.description && (
          <p className="line-clamp-2 text-sm text-muted-foreground">
            {recipe.description}
          </p>
        )}
        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 pt-2 text-xs font-medium text-muted-foreground">
          {total > 0 && (
            <span className="flex items-center gap-1">
              <Clock className="size-3.5" />
              {t("columns.minutes", { count: total })}
            </span>
          )}
          {recipe.servings != null && (
            <span className="flex items-center gap-1">
              <Users className="size-3.5" />
              {recipe.servings}
            </span>
          )}
          {recipe.meal_type && (
            <span className="flex items-center gap-1 capitalize">
              <MealIcon className="size-3.5" aria-hidden="true" />
              {t(`form.meal_${recipe.meal_type}`)}
            </span>
          )}
          <span className="flex items-center gap-1">
            <ListChecks className="size-3.5" />
            {t("columns.ingredient_count", {
              count: (recipe.ingredients ?? []).length,
            })}
          </span>
          {/* relative z-10 lifts the button above the card-wide link */}
          <div className="relative z-10 -my-2 -mr-2 ml-auto">
            <AddToShoppingList recipe={recipe} variant="icon" />
          </div>
        </div>
      </div>
    </article>
  )
}

/**
 * Recipes as a grid of photo cards. `community` cards are other people's:
 * they show the author instead of the owner's actions menu.
 */
export function RecipeGrid({
  recipes,
  community = false,
}: {
  recipes: RecipePublic[]
  community?: boolean
}) {
  const { t } = useTranslation("common")

  if (recipes.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground italic">
        {t("no_results")}
      </p>
    )
  }

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {recipes.map((recipe) => (
        <RecipeCard key={recipe.id} recipe={recipe} community={community} />
      ))}
    </div>
  )
}

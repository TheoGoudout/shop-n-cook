import { X } from "lucide-react"
import { useTranslation } from "react-i18next"
import type { Difficulty, MealType, Season } from "@/client"
import { SeasonSchema } from "@/client/schemas.gen"
import { SEASON_ICONS } from "@/components/Common/categoryIcons"
import { DIET_ICONS } from "@/components/Recipes/DietaryBadges"
import { RecipeEnumSelect } from "@/components/Recipes/RecipeEnumSelect"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export type RecipeFilters = {
  seasons: Season[]
  is_vegan: boolean
  is_vegetarian: boolean
  is_gluten_free: boolean
  is_dairy_free: boolean
  difficulty: Difficulty | ""
  meal_type: MealType | ""
  cuisine_type: string
}

export const defaultFilters: RecipeFilters = {
  seasons: [],
  is_vegan: false,
  is_vegetarian: false,
  is_gluten_free: false,
  is_dairy_free: false,
  difficulty: "",
  meal_type: "",
  cuisine_type: "",
}

/** The filters as the recipe listing endpoints take them; unset ones are left out. */
export function recipeFilterParams(filters: RecipeFilters) {
  return {
    seasons: filters.seasons.length ? filters.seasons : null,
    isVegan: filters.is_vegan || null,
    isVegetarian: filters.is_vegetarian || null,
    isGlutenFree: filters.is_gluten_free || null,
    isDairyFree: filters.is_dairy_free || null,
    difficulty: filters.difficulty || null,
    mealType: filters.meal_type || null,
    cuisineType: filters.cuisine_type.trim() || null,
  }
}

export function activeFilterCount(filters: RecipeFilters): number {
  return (
    filters.seasons.length +
    (filters.is_vegan ? 1 : 0) +
    (filters.is_vegetarian ? 1 : 0) +
    (filters.is_gluten_free ? 1 : 0) +
    (filters.is_dairy_free ? 1 : 0) +
    (filters.difficulty ? 1 : 0) +
    (filters.meal_type ? 1 : 0) +
    (filters.cuisine_type ? 1 : 0)
  )
}

const SEASONS = SeasonSchema.enum

interface RecipeFilterBarProps {
  filters: RecipeFilters
  onChange: (filters: RecipeFilters) => void
  onClear: () => void
}

export function RecipeFilterBar({
  filters,
  onChange,
  onClear,
}: RecipeFilterBarProps) {
  const { t } = useTranslation("recipes")

  const toggleSeason = (season: Season) => {
    const next = filters.seasons.includes(season)
      ? filters.seasons.filter((s) => s !== season)
      : [...filters.seasons, season]
    onChange({ ...filters, seasons: next })
  }

  const toggleDietary = (key: keyof RecipeFilters) => {
    onChange({ ...filters, [key]: !filters[key] })
  }

  const count = activeFilterCount(filters)

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Seasons */}
      {SEASONS.map((s) => {
        const SeasonIcon = SEASON_ICONS[s]
        return (
          <button key={s} type="button" onClick={() => toggleSeason(s)}>
            <Badge
              variant={filters.seasons.includes(s) ? "default" : "outline"}
              className="cursor-pointer text-xs"
            >
              <SeasonIcon aria-hidden="true" />
              {t(`form.season_${s}`)}
            </Badge>
          </button>
        )
      })}

      {/* Dietary toggles */}
      {(["vegan", "vegetarian", "gluten_free", "dairy_free"] as const).map(
        (diet) => {
          const key = `is_${diet}` as const
          const Icon = DIET_ICONS[diet]
          return (
            <button key={key} type="button" onClick={() => toggleDietary(key)}>
              <Badge
                variant={filters[key] ? "default" : "outline"}
                className="cursor-pointer text-xs"
              >
                <Icon aria-hidden="true" />
                {t(`form.${key}_label`)}
              </Badge>
            </button>
          )
        },
      )}

      {/* Difficulty select */}
      <RecipeEnumSelect
        kind="difficulty"
        value={filters.difficulty}
        onChange={(value) => onChange({ ...filters, difficulty: value })}
        noneLabel={t("filters.difficulty")}
        triggerClassName="h-7 w-28 text-xs"
      />

      {/* Meal type select */}
      <RecipeEnumSelect
        kind="meal_type"
        value={filters.meal_type}
        onChange={(value) => onChange({ ...filters, meal_type: value })}
        noneLabel={t("filters.meal_type")}
        triggerClassName="h-7 w-28 text-xs"
      />

      {/* Cuisine type text */}
      <input
        type="text"
        value={filters.cuisine_type}
        onChange={(e) => onChange({ ...filters, cuisine_type: e.target.value })}
        placeholder={t("filters.cuisine")}
        className="h-7 w-28 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
      />

      {/* Clear button */}
      {count > 0 && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1 text-xs text-muted-foreground"
          onClick={onClear}
        >
          <X className="h-3 w-3" />
          {t("filters.clear_all")}
        </Button>
      )}
    </div>
  )
}

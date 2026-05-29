import { X } from "lucide-react"
import { useTranslation } from "react-i18next"

import type { Difficulty, MealType, Season } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

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

const SEASONS: Season[] = ["spring", "summer", "autumn", "winter"]
const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard"]
const MEAL_TYPES: MealType[] = [
  "breakfast",
  "lunch",
  "dinner",
  "snack",
  "dessert",
  "drink",
  "other",
]

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
      {SEASONS.map((s) => (
        <button key={s} type="button" onClick={() => toggleSeason(s)}>
          <Badge
            variant={filters.seasons.includes(s) ? "default" : "outline"}
            className="cursor-pointer text-xs"
          >
            {t(`form.season_${s}`)}
          </Badge>
        </button>
      ))}

      {/* Dietary toggles */}
      {(
        [
          ["is_vegan", "form.is_vegan_label"],
          ["is_vegetarian", "form.is_vegetarian_label"],
          ["is_gluten_free", "form.is_gluten_free_label"],
          ["is_dairy_free", "form.is_dairy_free_label"],
        ] as [keyof RecipeFilters, string][]
      ).map(([key, labelKey]) => (
        <button key={key} type="button" onClick={() => toggleDietary(key)}>
          <Badge
            variant={filters[key] ? "default" : "outline"}
            className="cursor-pointer text-xs"
          >
            {t(labelKey)}
          </Badge>
        </button>
      ))}

      {/* Difficulty select */}
      <Select
        value={filters.difficulty}
        onValueChange={(v) =>
          onChange({ ...filters, difficulty: v as Difficulty | "" })
        }
      >
        <SelectTrigger className="h-7 w-28 text-xs">
          <SelectValue placeholder={t("filters.difficulty")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">{t("filters.difficulty")}</SelectItem>
          {DIFFICULTIES.map((d) => (
            <SelectItem key={d} value={d}>
              {t(`form.difficulty_${d}`)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Meal type select */}
      <Select
        value={filters.meal_type}
        onValueChange={(v) =>
          onChange({ ...filters, meal_type: v as MealType | "" })
        }
      >
        <SelectTrigger className="h-7 w-28 text-xs">
          <SelectValue placeholder={t("filters.meal_type")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">{t("filters.meal_type")}</SelectItem>
          {MEAL_TYPES.map((m) => (
            <SelectItem key={m} value={m}>
              {t(`form.meal_${m}`)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

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

import { Leaf, type LucideIcon, MilkOff, Vegan, WheatOff } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

export type Diet = "vegan" | "vegetarian" | "gluten_free" | "dairy_free"

/** One icon per diet, shared by badges, filters and the menu generator. */
export const DIET_ICONS: Record<Diet, LucideIcon> = {
  vegan: Vegan,
  vegetarian: Leaf,
  gluten_free: WheatOff,
  dairy_free: MilkOff,
}

type DietaryFlags = {
  is_vegan?: boolean
  is_vegetarian?: boolean
  is_gluten_free?: boolean
  is_dairy_free?: boolean
}

/** The diets a recipe qualifies for; vegan implies (and hides) vegetarian. */
export function recipeDiets(recipe: DietaryFlags): Diet[] {
  const diets: Diet[] = []
  if (recipe.is_vegan) diets.push("vegan")
  else if (recipe.is_vegetarian) diets.push("vegetarian")
  if (recipe.is_gluten_free) diets.push("gluten_free")
  if (recipe.is_dairy_free) diets.push("dairy_free")
  return diets
}

const DIET_CLASSES: Record<Diet, string> = {
  vegan: "bg-success text-success-foreground hover:bg-success",
  vegetarian: "bg-accent text-accent-foreground hover:bg-accent",
  gluten_free: "",
  dairy_free: "",
}

/**
 * A recipe's dietary badges. `compact` (card overlays) keeps the vegan /
 * vegetarian label but shows gluten- and dairy-free as icons alone; their
 * label stays available as a tooltip and to screen readers.
 */
export function DietaryBadges({
  recipe,
  compact = false,
}: {
  recipe: DietaryFlags
  compact?: boolean
}) {
  const { t } = useTranslation("recipes")

  return recipeDiets(recipe).map((diet) => {
    const Icon = DIET_ICONS[diet]
    const label = t(`form.is_${diet}_label`)
    const isAllergen = diet === "gluten_free" || diet === "dairy_free"
    const iconOnly = compact && isAllergen

    return (
      <Badge
        key={diet}
        variant={isAllergen ? (compact ? "secondary" : "outline") : "default"}
        className={cn(
          "text-xs",
          compact && "px-1.5 py-0.5",
          DIET_CLASSES[diet],
        )}
        title={iconOnly ? label : undefined}
        aria-label={iconOnly ? label : undefined}
        role={iconOnly ? "img" : undefined}
      >
        <Icon aria-hidden="true" />
        {!iconOnly && label}
      </Badge>
    )
  })
}

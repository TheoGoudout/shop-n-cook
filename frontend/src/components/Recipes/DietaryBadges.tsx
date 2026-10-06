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
 * A recipe's dietary badges, each an icon and its label. `onImage` gives the
 * outline badges a frosted background so they stay legible over a photo.
 */
export function DietaryBadges({
  recipe,
  onImage = false,
}: {
  recipe: DietaryFlags
  onImage?: boolean
}) {
  const { t } = useTranslation("recipes")

  return recipeDiets(recipe).map((diet) => {
    const Icon = DIET_ICONS[diet]
    const isAllergen = diet === "gluten_free" || diet === "dairy_free"

    return (
      <Badge
        key={diet}
        variant={isAllergen ? "outline" : "default"}
        className={cn(
          "text-xs",
          DIET_CLASSES[diet],
          onImage &&
            isAllergen &&
            "border-transparent bg-card/90 text-foreground backdrop-blur",
        )}
      >
        <Icon aria-hidden="true" />
        {t(`form.is_${diet}_label`)}
      </Badge>
    )
  })
}

import {
  Beef,
  CakeSlice,
  Carrot,
  Coffee,
  Cookie,
  Croissant,
  CupSoda,
  Fish,
  Flame,
  GlassWater,
  type LucideIcon,
  Milk,
  Moon,
  Package,
  Sandwich,
  ShoppingBasket,
  Snowflake,
  Utensils,
  Wheat,
} from "lucide-react"

import type { IngredientCategory, MealType } from "@/client"

/**
 * One icon per ingredient category and per meal type, so an icon means the
 * same thing on every screen. Keyed by the generated enums: a new backend
 * value fails type-checking here until it gets an icon.
 */
export const INGREDIENT_CATEGORY_ICONS: Record<IngredientCategory, LucideIcon> =
  {
    produce: Carrot,
    dairy: Milk,
    meat: Beef,
    seafood: Fish,
    grains: Wheat,
    pantry: Package,
    spices: Flame,
    beverages: CupSoda,
    frozen: Snowflake,
    bakery: Croissant,
    other: ShoppingBasket,
  }

export const MEAL_TYPE_ICONS: Record<MealType, LucideIcon> = {
  breakfast: Coffee,
  lunch: Sandwich,
  dinner: Moon,
  snack: Cookie,
  dessert: CakeSlice,
  drink: GlassWater,
  other: Utensils,
}

/** The icon for a meal type as the API returns it (nullable, loosely typed). */
export function mealTypeIcon(mealType: string | null | undefined): LucideIcon {
  return MEAL_TYPE_ICONS[mealType as MealType] ?? Utensils
}

export function categoryIcon(category: string): LucideIcon {
  return (
    INGREDIENT_CATEGORY_ICONS[category as IngredientCategory] ?? ShoppingBasket
  )
}

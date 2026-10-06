import {
  Beef,
  CakeSlice,
  Carrot,
  CloudSnow,
  Coffee,
  Cookie,
  Croissant,
  CupSoda,
  Fish,
  Flame,
  Flower2,
  GlassWater,
  type LucideIcon,
  Milk,
  Moon,
  Package,
  Sandwich,
  ShoppingBasket,
  SignalHigh,
  SignalLow,
  SignalMedium,
  Snowflake,
  Sun,
  TreeDeciduous,
  Utensils,
  Wheat,
} from "lucide-react"

import type { Difficulty, IngredientCategory, MealType, Season } from "@/client"

/**
 * One icon per ingredient category, meal type, season and difficulty, so an
 * icon means the same thing on every screen. Keyed by the generated enums: a
 * new backend value fails type-checking here until it gets an icon.
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

// Winter is not Snowflake (that is frozen food), autumn not Leaf (vegetarian).
export const SEASON_ICONS: Record<Season, LucideIcon> = {
  spring: Flower2,
  summer: Sun,
  autumn: TreeDeciduous,
  winter: CloudSnow,
}

export const DIFFICULTY_ICONS: Record<Difficulty, LucideIcon> = {
  easy: SignalLow,
  medium: SignalMedium,
  hard: SignalHigh,
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

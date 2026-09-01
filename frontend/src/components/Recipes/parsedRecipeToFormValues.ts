import type {
  Difficulty,
  ImportSource,
  MealType,
  ParsedRecipe,
  Season,
} from "@/client"

import { defaultCreateValues, type RecipeFormValues } from "./recipeFormSchema"

/**
 * Map a `ParsedRecipe` returned by an import endpoint onto form values.
 *
 * Steps reference their ingredients by name, while the form addresses them by
 * position, so the names are resolved back to indices here. Shared by the URL
 * and the photo importers.
 */
export function parsedRecipeToFormValues(
  parsed: ParsedRecipe,
  importSource: ImportSource,
): RecipeFormValues {
  const mappedIngredients = (parsed.ingredients ?? []).map((pi) => ({
    ingredient_name: pi.name,
    quantity: pi.quantity,
    unit: pi.unit,
    notes: pi.notes ?? "",
    name_en: pi.name_en ?? null,
    category: pi.category ?? null,
  }))

  const nameToIdx = new Map(
    mappedIngredients.map((mi, idx) => [mi.ingredient_name.toLowerCase(), idx]),
  )

  const mappedSteps = (parsed.steps ?? []).map((ps) => {
    const indices = (ps.ingredient_names ?? [])
      .map((name) => nameToIdx.get(name.toLowerCase()) ?? -1)
      .filter((idx) => idx >= 0)
    return { instruction: ps.instruction, ingredient_indices: indices }
  })

  return {
    ...defaultCreateValues,
    title: parsed.title,
    description: parsed.description ?? "",
    servings: parsed.servings ?? "",
    prep_time_minutes: parsed.prep_time_minutes ?? "",
    cook_time_minutes: parsed.cook_time_minutes ?? "",
    source_url: parsed.source_url ?? "",
    image_url: parsed.image_url ?? "",
    import_source: importSource,
    ingredients: mappedIngredients,
    steps: mappedSteps,
    seasons: (parsed.seasons ?? []) as Season[],
    is_vegan: parsed.is_vegan ?? false,
    is_vegetarian: parsed.is_vegetarian ?? false,
    is_gluten_free: parsed.is_gluten_free ?? false,
    is_dairy_free: parsed.is_dairy_free ?? false,
    kcal_per_serving: parsed.kcal_per_serving ?? "",
    difficulty: (parsed.difficulty as Difficulty) ?? "",
    meal_type: (parsed.meal_type as MealType) ?? "",
    cuisine_type: parsed.cuisine_type ?? "",
  }
}

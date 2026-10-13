import type {
  ParsedRecipe,
  RecipeCreate,
  RecipeIngredientCreate,
  RecipeStepCreate,
} from "./client/types.gen"

/**
 * The recipe to save for an import, carrying every field the import filled in.
 *
 * Mirrors the backend's `parsed_to_create` and the web app's import mapping:
 * steps name their ingredients, matched case-insensitively.
 */
export function parsedRecipeToCreate(parsed: ParsedRecipe): RecipeCreate {
  const ingredients: RecipeIngredientCreate[] = (parsed.ingredients ?? []).map(
    (ing) => ({
      ingredient_name: ing.name,
      name_en: ing.name_en ?? null,
      quantity: ing.quantity,
      unit: ing.unit,
      notes: ing.notes ?? null,
      category: ing.category ?? null,
    }),
  )

  const nameToIdx = new Map(
    ingredients.map((ing, idx) => [ing.ingredient_name.toLowerCase(), idx]),
  )
  const steps: RecipeStepCreate[] = (parsed.steps ?? []).map((step, i) => ({
    step_number: i + 1,
    instruction: step.instruction,
    ingredient_indices: (step.ingredient_names ?? [])
      .map((name) => nameToIdx.get(name.toLowerCase()) ?? -1)
      .filter((idx) => idx !== -1),
  }))

  return {
    title: parsed.title,
    description: parsed.description,
    servings: parsed.servings,
    prep_time_minutes: parsed.prep_time_minutes,
    cook_time_minutes: parsed.cook_time_minutes,
    source_url: parsed.source_url,
    image_url: parsed.image_url,
    import_consent: true,
    import_source: "url",
    import_language: parsed.language ?? null,
    ingredients,
    steps,
    seasons: parsed.seasons ?? [],
    is_vegan: parsed.is_vegan ?? false,
    is_vegetarian: parsed.is_vegetarian ?? false,
    is_gluten_free: parsed.is_gluten_free ?? false,
    is_dairy_free: parsed.is_dairy_free ?? false,
    kcal_per_serving: parsed.kcal_per_serving ?? null,
    difficulty: parsed.difficulty ?? null,
    meal_type: parsed.meal_type ?? null,
    cuisine_type: parsed.cuisine_type ?? null,
  }
}

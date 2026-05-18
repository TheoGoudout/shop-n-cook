import type {
  ParsedRecipe,
  RecipeCreate,
  RecipeIngredientCreate,
  RecipeStepCreate,
} from "./client/types.gen"

export function parsedRecipeToCreate(parsed: ParsedRecipe): RecipeCreate {
  const ingredients: RecipeIngredientCreate[] = (parsed.ingredients ?? []).map(
    (ing) => ({
      ingredient_name: ing.name,
      ingredient_category: ing.category,
      ingredient_default_unit: ing.unit,
      quantity: ing.quantity,
      unit: ing.unit,
      notes: ing.notes,
    }),
  )

  const steps: RecipeStepCreate[] = (parsed.steps ?? []).map((step, i) => ({
    step_number: i + 1,
    instruction: step.instruction,
    ingredient_indices: (step.ingredient_names ?? [])
      .map((name) =>
        (parsed.ingredients ?? []).findIndex((ing) => ing.name === name),
      )
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
    ingredients,
    steps,
  }
}

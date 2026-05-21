import type { TFunction } from "i18next"
import { z } from "zod"

import type {
  IngredientCategory,
  RecipeCreate,
  RecipePublic,
  RecipeUpdate,
  Unit,
} from "@/client"

export type RecipeFormValues = {
  title: string
  description?: string
  servings?: number | ""
  prep_time_minutes?: number | ""
  cook_time_minutes?: number | ""
  source_url?: string
  image_url?: string
  is_public: boolean
  import_consent: boolean
  ingredients: Array<{
    ingredient_name: string
    quantity: number
    unit: string
    notes?: string
    name_en?: string | null
    category?: string | null
  }>
  steps: Array<{
    instruction: string
    ingredient_indices: number[]
  }>
}

interface SchemaOptions {
  requireImportConsent?: boolean
}

export const createRecipeFormSchema = (
  t: TFunction,
  { requireImportConsent = false }: SchemaOptions = {},
) => {
  const ingredientSchema = z.object({
    ingredient_name: z
      .string()
      .min(1, { message: t("form.ingredient_required") }),
    quantity: z.coerce.number().positive(),
    unit: z.string().min(1),
    notes: z.string().optional(),
    name_en: z.string().nullable().optional(),
    category: z.string().nullable().optional(),
  })

  const stepSchema = z.object({
    instruction: z
      .string()
      .min(1, { message: t("form.step_instruction_placeholder") }),
    ingredient_indices: z.array(z.number()),
  })

  const base = z.object({
    title: z.string().min(1, { message: t("form.title_required") }),
    description: z.string().optional(),
    servings: z.coerce.number().int().positive().optional().or(z.literal("")),
    prep_time_minutes: z.coerce
      .number()
      .int()
      .min(0)
      .optional()
      .or(z.literal("")),
    cook_time_minutes: z.coerce
      .number()
      .int()
      .min(0)
      .optional()
      .or(z.literal("")),
    source_url: z.string().url().optional().or(z.literal("")),
    image_url: z.string().url().optional().or(z.literal("")),
    is_public: z.boolean().default(false),
    import_consent: z.boolean().default(false),
    ingredients: z.array(ingredientSchema),
    steps: z.array(stepSchema),
  })

  if (!requireImportConsent) return base

  return base.superRefine((data, ctx) => {
    if (data.source_url && !data.import_consent) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: t("add.import_consent_required"),
        path: ["import_consent"],
      })
    }
  })
}

export const defaultCreateValues: RecipeFormValues = {
  title: "",
  description: "",
  servings: "",
  prep_time_minutes: "",
  cook_time_minutes: "",
  source_url: "",
  image_url: "",
  is_public: false,
  import_consent: false,
  ingredients: [],
  steps: [],
}

export const buildEditDefaults = (recipe: RecipePublic): RecipeFormValues => {
  const riList = recipe.ingredients ?? []
  const initialSteps = (recipe.steps ?? [])
    .slice()
    .sort((a, b) => a.step_number - b.step_number)
    .map((step) => ({
      instruction: step.instruction,
      ingredient_indices: (step.ingredients ?? [])
        .map((si) =>
          riList.findIndex((ri) => ri.id === si.recipe_ingredient_id),
        )
        .filter((idx) => idx >= 0),
    }))

  return {
    title: recipe.title,
    description: recipe.description ?? "",
    servings: recipe.servings ?? "",
    prep_time_minutes: recipe.prep_time_minutes ?? "",
    cook_time_minutes: recipe.cook_time_minutes ?? "",
    source_url: recipe.source_url ?? "",
    image_url: recipe.image_url ?? "",
    is_public: recipe.is_public ?? false,
    import_consent: false,
    ingredients: (recipe.ingredients ?? []).map((i) => ({
      ingredient_name: i.ingredient_name,
      quantity: i.quantity,
      unit: i.unit,
      notes: i.notes ?? "",
    })),
    steps: initialSteps,
  }
}

const toIngredientPayload = (i: RecipeFormValues["ingredients"][number]) => ({
  ingredient_name: i.ingredient_name,
  quantity: i.quantity,
  unit: i.unit as Unit,
  notes: i.notes || null,
  name_en: i.name_en ?? null,
  category: (i.category ?? null) as IngredientCategory | null,
})

const toStepPayload = (s: RecipeFormValues["steps"][number], idx: number) => ({
  step_number: idx + 1,
  instruction: s.instruction,
  ingredient_indices: s.ingredient_indices,
})

export const toRecipeCreatePayload = (
  data: RecipeFormValues,
): RecipeCreate => ({
  title: data.title,
  description: data.description || null,
  servings: data.servings ? Number(data.servings) : null,
  prep_time_minutes: data.prep_time_minutes
    ? Number(data.prep_time_minutes)
    : null,
  cook_time_minutes: data.cook_time_minutes
    ? Number(data.cook_time_minutes)
    : null,
  source_url: data.source_url || null,
  image_url: data.image_url || null,
  is_public: data.is_public,
  import_consent: !!data.source_url && data.import_consent,
  ingredients: data.ingredients.map(toIngredientPayload),
  steps: data.steps.map(toStepPayload),
})

export const toRecipeUpdatePayload = (
  data: RecipeFormValues,
): RecipeUpdate => ({
  title: data.title,
  description: data.description || null,
  servings: data.servings ? Number(data.servings) : null,
  prep_time_minutes: data.prep_time_minutes
    ? Number(data.prep_time_minutes)
    : null,
  cook_time_minutes: data.cook_time_minutes
    ? Number(data.cook_time_minutes)
    : null,
  source_url: data.source_url || null,
  image_url: data.image_url || null,
  is_public: data.is_public,
  ingredients: data.ingredients.map(toIngredientPayload),
  steps: data.steps.map(toStepPayload),
})

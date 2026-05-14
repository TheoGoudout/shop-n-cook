import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import i18n from "i18next"
import { Download, Loader2, Plus, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { type Resolver, useFieldArray, useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"

import {
  type IngredientCategory,
  IngredientsService,
  RecipesService,
  type Unit,
} from "@/client"
import { IngredientCategorySchema, UnitSchema } from "@/client/schemas.gen"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const _stepSchema = z.object({
  instruction: z.string().min(1),
  ingredient_indices: z.array(z.number()),
})

const _ingredientSchema = z.object({
  ingredient_id: z.string().optional(),
  ingredient_name: z.string().optional(),
  category: z.string().min(1),
  quantity: z.coerce.number().positive(),
  unit: z.string().min(1),
  notes: z.string().optional(),
})

const _formSchema = z.object({
  title: z.string(),
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
  ingredients: z.array(_ingredientSchema),
  steps: z.array(_stepSchema),
})

type FormData = z.infer<typeof _formSchema>

const AddRecipe = () => {
  const { t } = useTranslation("recipes")
  const { t: tCommon } = useTranslation("common")

  const ingredientSchema = useMemo(
    () =>
      z
        .object({
          ingredient_id: z.string().optional(),
          ingredient_name: z.string().optional(),
          category: z.string().min(1),
          quantity: z.coerce.number().positive(),
          unit: z.string().min(1),
          notes: z.string().optional(),
        })
        .refine((d) => d.ingredient_id || d.ingredient_name, {
          message: t("form.ingredient_required"),
          path: ["ingredient_id"],
        }),
    [t],
  )

  const stepSchema = useMemo(
    () =>
      z.object({
        instruction: z
          .string()
          .min(1, { message: t("form.step_instruction_placeholder") }),
        ingredient_indices: z.array(z.number()),
      }),
    [t],
  )

  const formSchema = useMemo(
    () =>
      z.object({
        title: z.string().min(1, { message: t("form.title_required") }),
        description: z.string().optional(),
        servings: z.coerce
          .number()
          .int()
          .positive()
          .optional()
          .or(z.literal("")),
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
        ingredients: z.array(ingredientSchema),
        steps: z.array(stepSchema),
      }),
    [t, ingredientSchema, stepSchema],
  )

  const [isOpen, setIsOpen] = useState(false)
  const [importUrl, setImportUrl] = useState("")
  const [isImporting, setIsImporting] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: ingredientsData } = useQuery({
    queryKey: ["ingredients"],
    queryFn: () => IngredientsService.readIngredients({ limit: 500 }),
    enabled: isOpen,
  })

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as Resolver<FormData>,
    defaultValues: {
      title: "",
      description: "",
      servings: "",
      prep_time_minutes: "",
      cook_time_minutes: "",
      source_url: "",
      image_url: "",
      ingredients: [],
      steps: [],
    },
  })

  const {
    fields: ingredientFields,
    append: appendIngredient,
    remove: removeIngredient,
  } = useFieldArray({ control: form.control, name: "ingredients" })

  const {
    fields: stepFields,
    append: appendStep,
    remove: removeStep,
  } = useFieldArray({ control: form.control, name: "steps" })

  const watchedIngredients = form.watch("ingredients")

  const handleImport = async () => {
    if (!importUrl.trim()) return
    setIsImporting(true)
    try {
      const parsed = await RecipesService.importRecipeUrl({
        requestBody: { url: importUrl, language: i18n.language },
      })
      const existingIngredients = ingredientsData?.data ?? []
      let unmatchedCount = 0
      const mappedIngredients = (parsed.ingredients ?? []).map((pi) => {
        const match = existingIngredients.find(
          (ing) => ing.name.toLowerCase() === pi.name.toLowerCase(),
        )
        if (!match) unmatchedCount++
        return {
          ingredient_id: match?.id ?? "",
          ingredient_name: match ? "" : pi.name,
          category: pi.category,
          quantity: pi.quantity,
          unit: pi.unit,
          notes: pi.notes ?? "",
        }
      })

      // Map step ingredient_names → indices into mappedIngredients
      const mappedSteps = (parsed.steps ?? []).map((ps) => {
        const indices = (ps.ingredient_names ?? [])
          .map((name) =>
            mappedIngredients.findIndex(
              (mi) =>
                (mi.ingredient_name || "").toLowerCase() ===
                  name.toLowerCase() ||
                existingIngredients
                  .find((ei) => ei.id === mi.ingredient_id)
                  ?.name.toLowerCase() === name.toLowerCase(),
            ),
          )
          .filter((idx) => idx >= 0)
        return { instruction: ps.instruction, ingredient_indices: indices }
      })

      form.reset({
        title: parsed.title,
        description: parsed.description ?? "",
        servings: parsed.servings ?? "",
        prep_time_minutes: parsed.prep_time_minutes ?? "",
        cook_time_minutes: parsed.cook_time_minutes ?? "",
        source_url: parsed.source_url ?? "",
        image_url: parsed.image_url ?? "",
        ingredients: mappedIngredients,
        steps: mappedSteps,
      })
      setImportUrl("")
      showSuccessToast(
        unmatchedCount > 0
          ? t("add.import_partial", { count: unmatchedCount })
          : t("add.import_success"),
      )
    } catch {
      showErrorToast(t("add.import_error"))
    } finally {
      setIsImporting(false)
    }
  }

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      RecipesService.createRecipe({
        requestBody: {
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
          ingredients: data.ingredients.map((i) => ({
            ingredient_id: i.ingredient_id || null,
            ingredient_name: i.ingredient_id
              ? null
              : (i.ingredient_name ?? null),
            ingredient_category: i.category as IngredientCategory,
            quantity: i.quantity,
            unit: i.unit as Unit,
            ingredient_default_unit: i.unit as Unit,
            notes: i.notes || null,
          })),
          steps: data.steps.map((s, idx) => ({
            step_number: idx + 1,
            instruction: s.instruction,
            ingredient_indices: s.ingredient_indices,
          })),
        },
      }),
    onSuccess: () => {
      showSuccessToast(t("add.success"))
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] })
      queryClient.invalidateQueries({ queryKey: ["ingredients"] })
    },
  })

  const toggleStepIngredient = (stepIndex: number, ingredientIndex: number) => {
    const current = form.getValues(`steps.${stepIndex}.ingredient_indices`)
    const next = current.includes(ingredientIndex)
      ? current.filter((i) => i !== ingredientIndex)
      : [...current, ingredientIndex]
    form.setValue(`steps.${stepIndex}.ingredient_indices`, next)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="my-4">
          <Plus className="mr-2" />
          {t("add.button")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("add.dialog_title")}</DialogTitle>
          <DialogDescription>{t("add.dialog_description")}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))}>
            <div className="grid gap-4 py-4">
              {/* Import from URL */}
              <div className="flex gap-2 p-3 rounded-md border border-dashed bg-muted/30">
                <Input
                  placeholder={t("add.import_placeholder")}
                  value={importUrl}
                  onChange={(e) => setImportUrl(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault()
                      handleImport()
                    }
                  }}
                  className="bg-transparent border-0 shadow-none focus-visible:ring-0 px-0"
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleImport}
                  disabled={isImporting || !importUrl.trim()}
                >
                  {isImporting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  <span className="ml-1.5">{tCommon("import")}</span>
                </Button>
              </div>

              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {t("form.title_label")}{" "}
                      <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder={t("form.title_placeholder")}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("form.description_label")}</FormLabel>
                    <FormControl>
                      <Input
                        placeholder={t("form.description_placeholder")}
                        {...field}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-3 gap-4">
                <FormField
                  control={form.control}
                  name="servings"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("form.servings_label")}</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={1}
                          placeholder="4"
                          {...field}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="prep_time_minutes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("form.prep_label")}</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          placeholder="15"
                          {...field}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="cook_time_minutes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("form.cook_label")}</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          placeholder="30"
                          {...field}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="source_url"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("form.source_url_label")}</FormLabel>
                      <FormControl>
                        <Input
                          placeholder={t("form.url_placeholder")}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="image_url"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("form.image_url_label")}</FormLabel>
                      <FormControl>
                        <Input
                          placeholder={t("form.url_placeholder")}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Ingredients */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <FormLabel>{t("form.ingredients_label")}</FormLabel>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      appendIngredient({
                        ingredient_id: "",
                        ingredient_name: "",
                        category: "other",
                        quantity: 1,
                        unit: "piece",
                        notes: "",
                      })
                    }
                  >
                    <Plus className="mr-1 h-3 w-3" /> {t("form.add_ingredient")}
                  </Button>
                </div>
                <div className="space-y-3">
                  {ingredientFields.map((field, index) => {
                    const ingredientName = form.watch(
                      `ingredients.${index}.ingredient_name`,
                    )
                    const ingredientId = form.watch(
                      `ingredients.${index}.ingredient_id`,
                    )
                    const isNew = !ingredientId && !!ingredientName

                    return (
                      <div key={field.id} className="flex flex-col gap-1">
                        <div className="flex gap-2 items-start">
                          <FormField
                            control={form.control}
                            name={`ingredients.${index}.ingredient_id`}
                            render={({ field: f }) => (
                              <FormItem className="flex-1">
                                <Select
                                  onValueChange={(val) => {
                                    f.onChange(val)
                                    form.setValue(
                                      `ingredients.${index}.ingredient_name`,
                                      "",
                                    )
                                  }}
                                  value={f.value}
                                >
                                  <FormControl>
                                    <SelectTrigger>
                                      {isNew ? (
                                        <span className="flex items-center gap-2 text-sm">
                                          <span>{ingredientName}</span>
                                          <Badge
                                            variant="secondary"
                                            className="text-xs"
                                          >
                                            {tCommon("new")}
                                          </Badge>
                                        </span>
                                      ) : (
                                        <SelectValue
                                          placeholder={t(
                                            "form.select_ingredient",
                                          )}
                                        />
                                      )}
                                    </SelectTrigger>
                                  </FormControl>
                                  <SelectContent>
                                    {ingredientsData?.data.map((ing) => (
                                      <SelectItem key={ing.id} value={ing.id}>
                                        {ing.name}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name={`ingredients.${index}.category`}
                            render={({ field: f }) => (
                              <FormItem className="w-24">
                                <Select
                                  onValueChange={f.onChange}
                                  value={f.value}
                                >
                                  <FormControl>
                                    <SelectTrigger>
                                      <SelectValue />
                                    </SelectTrigger>
                                  </FormControl>
                                  <SelectContent>
                                    {IngredientCategorySchema.enum.map((c) => (
                                      <SelectItem key={c} value={c}>
                                        {c}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name={`ingredients.${index}.quantity`}
                            render={({ field: f }) => (
                              <FormItem className="w-20">
                                <FormControl>
                                  <Input
                                    type="number"
                                    min={0.01}
                                    step="any"
                                    placeholder={t("form.qty_placeholder")}
                                    {...f}
                                  />
                                </FormControl>
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name={`ingredients.${index}.unit`}
                            render={({ field: f }) => (
                              <FormItem className="w-24">
                                <Select
                                  onValueChange={f.onChange}
                                  value={f.value}
                                >
                                  <FormControl>
                                    <SelectTrigger>
                                      <SelectValue />
                                    </SelectTrigger>
                                  </FormControl>
                                  <SelectContent>
                                    {UnitSchema.enum.map((u) => (
                                      <SelectItem key={u} value={u}>
                                        {tCommon(`unit_labels.${u}`, {
                                          defaultValue: u,
                                        })}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </FormItem>
                            )}
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => removeIngredient(index)}
                            className="mt-0.5"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                        <FormField
                          control={form.control}
                          name={`ingredients.${index}.notes`}
                          render={({ field: f }) => (
                            <FormItem className="pr-10">
                              <FormControl>
                                <Input
                                  placeholder={t("form.notes_placeholder")}
                                  className="h-7 text-xs text-muted-foreground"
                                  {...f}
                                />
                              </FormControl>
                            </FormItem>
                          )}
                        />
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Steps */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <FormLabel>{t("form.steps_label")}</FormLabel>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      appendStep({ instruction: "", ingredient_indices: [] })
                    }
                  >
                    <Plus className="mr-1 h-3 w-3" /> {t("form.add_step")}
                  </Button>
                </div>
                <div className="space-y-3">
                  {stepFields.map((field, stepIndex) => {
                    const selectedIndices = form.watch(
                      `steps.${stepIndex}.ingredient_indices`,
                    )
                    return (
                      <div
                        key={field.id}
                        className="flex gap-3 p-3 rounded-md border bg-muted/20"
                      >
                        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-muted text-muted-foreground text-xs flex items-center justify-center font-semibold mt-1">
                          {stepIndex + 1}
                        </span>
                        <div className="flex-1 space-y-2">
                          <FormField
                            control={form.control}
                            name={`steps.${stepIndex}.instruction`}
                            render={({ field: f }) => (
                              <FormItem>
                                <FormControl>
                                  <textarea
                                    className="flex min-h-[72px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                    placeholder={t(
                                      "form.step_instruction_placeholder",
                                    )}
                                    {...f}
                                  />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          {watchedIngredients.length > 0 && (
                            <div>
                              <p className="text-xs text-muted-foreground mb-1">
                                {t("form.step_ingredients_hint")}
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {watchedIngredients.map((ing, ingIdx) => {
                                  const label =
                                    ing.ingredient_name ||
                                    ingredientsData?.data.find(
                                      (d) => d.id === ing.ingredient_id,
                                    )?.name ||
                                    ""
                                  if (!label) return null
                                  const active =
                                    selectedIndices.includes(ingIdx)
                                  return (
                                    <button
                                      key={ingIdx}
                                      type="button"
                                      onClick={() =>
                                        toggleStepIngredient(stepIndex, ingIdx)
                                      }
                                      className="focus:outline-none"
                                    >
                                      <Badge
                                        variant={active ? "default" : "outline"}
                                        className="text-xs cursor-pointer"
                                      >
                                        {label}
                                      </Badge>
                                    </button>
                                  )
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeStep(stepIndex)}
                          className="mt-0.5 flex-shrink-0"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  {tCommon("cancel")}
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                {tCommon("save")}
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddRecipe

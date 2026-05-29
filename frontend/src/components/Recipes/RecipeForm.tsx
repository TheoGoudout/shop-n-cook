import { Plus, Trash2 } from "lucide-react"
import type { ReactNode } from "react"
import { type UseFormReturn, useFieldArray } from "react-hook-form"
import { useTranslation } from "react-i18next"

import { UnitSelect } from "@/components/Common/UnitSelect"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { DialogClose, DialogFooter } from "@/components/ui/dialog"
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

import type { RecipeFormValues } from "./recipeFormSchema"

const SEASONS = ["spring", "summer", "autumn", "winter"] as const
const DIFFICULTIES = ["easy", "medium", "hard"] as const
const MEAL_TYPES = [
  "breakfast",
  "lunch",
  "dinner",
  "snack",
  "dessert",
  "drink",
  "other",
] as const

interface RecipeFormProps {
  form: UseFormReturn<RecipeFormValues>
  mode: "create" | "edit"
  isPublicAlreadySet?: boolean
  onSubmit: (data: RecipeFormValues) => void
  isPending: boolean
  importPanel?: ReactNode
}

export function RecipeForm({
  form,
  mode,
  isPublicAlreadySet = false,
  onSubmit,
  isPending,
  importPanel,
}: RecipeFormProps) {
  const { t } = useTranslation("recipes")
  const { t: tCommon } = useTranslation("common")

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
  const watchedSourceUrl = form.watch("source_url")
  const watchedSeasons = form.watch("seasons")

  const toggleSeason = (season: (typeof SEASONS)[number]) => {
    const current = form.getValues("seasons") ?? []
    const next = current.includes(season)
      ? current.filter((s) => s !== season)
      : [...current, season]
    form.setValue("seasons", next)
  }

  const toggleStepIngredient = (stepIndex: number, ingredientIndex: number) => {
    const current = form.getValues(`steps.${stepIndex}.ingredient_indices`)
    const next = current.includes(ingredientIndex)
      ? current.filter((i) => i !== ingredientIndex)
      : [...current, ingredientIndex]
    form.setValue(`steps.${stepIndex}.ingredient_indices`, next)
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <div className="grid gap-4 py-4">
          {importPanel}

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
                  <Input placeholder={t("form.title_placeholder")} {...field} />
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
                    <Input type="number" min={1} placeholder="4" {...field} />
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
                    <Input type="number" min={0} placeholder="15" {...field} />
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
                    <Input type="number" min={0} placeholder="30" {...field} />
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
                    <Input placeholder={t("form.url_placeholder")} {...field} />
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
                    <Input placeholder={t("form.url_placeholder")} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          {/* Metadata section */}
          <div className="rounded-lg border p-3 space-y-3">
            <p className="text-sm font-medium text-muted-foreground">
              {t("form.metadata_label")}
            </p>

            {/* Dietary checkboxes */}
            <div className="flex flex-wrap gap-4">
              {(
                [
                  "is_vegan",
                  "is_vegetarian",
                  "is_gluten_free",
                  "is_dairy_free",
                ] as const
              ).map((field) => (
                <FormField
                  key={field}
                  control={form.control}
                  name={field}
                  render={({ field: f }) => (
                    <FormItem className="flex items-center gap-2">
                      <FormControl>
                        <Checkbox
                          checked={f.value as boolean}
                          onCheckedChange={f.onChange}
                        />
                      </FormControl>
                      <FormLabel className="!mt-0 cursor-pointer font-normal">
                        {t(`form.${field}_label`)}
                      </FormLabel>
                    </FormItem>
                  )}
                />
              ))}
            </div>

            {/* Difficulty, Meal type, Kcal */}
            <div className="grid grid-cols-3 gap-4">
              <FormField
                control={form.control}
                name="difficulty"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("form.difficulty_label")}</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? ""}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue
                            placeholder={t("form.select_placeholder")}
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="">{t("form.none")}</SelectItem>
                        {DIFFICULTIES.map((d) => (
                          <SelectItem key={d} value={d}>
                            {t(`form.difficulty_${d}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="meal_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("form.meal_type_label")}</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? ""}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue
                            placeholder={t("form.select_placeholder")}
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="">{t("form.none")}</SelectItem>
                        {MEAL_TYPES.map((m) => (
                          <SelectItem key={m} value={m}>
                            {t(`form.meal_${m}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="kcal_per_serving"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("form.kcal_label")}</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={0}
                        placeholder="450"
                        {...field}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>

            {/* Cuisine type and Seasons */}
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="cuisine_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("form.cuisine_type_label")}</FormLabel>
                    <FormControl>
                      <Input
                        placeholder={t("form.cuisine_type_placeholder")}
                        {...field}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
              <div>
                <FormLabel>{t("form.seasons_label")}</FormLabel>
                <div className="flex flex-wrap gap-3 mt-2">
                  {SEASONS.map((season) => (
                    <button
                      key={season}
                      type="button"
                      onClick={() => toggleSeason(season)}
                      className="focus:outline-none"
                    >
                      <Badge
                        variant={
                          watchedSeasons?.includes(season)
                            ? "default"
                            : "outline"
                        }
                        className="text-xs cursor-pointer"
                      >
                        {t(`form.season_${season}`)}
                      </Badge>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Public toggle */}
          <FormField
            control={form.control}
            name="is_public"
            render={({ field }) => (
              <FormItem className="flex flex-row items-start gap-3 rounded-lg border p-3">
                <FormControl>
                  <Checkbox
                    checked={field.value}
                    onCheckedChange={field.onChange}
                    disabled={isPublicAlreadySet}
                  />
                </FormControl>
                <div className="space-y-1 leading-none">
                  <FormLabel>{t("form.make_public_label")}</FormLabel>
                  <p className="text-xs text-muted-foreground">
                    {isPublicAlreadySet
                      ? t("form.already_public")
                      : t("form.make_public_warning")}
                  </p>
                </div>
              </FormItem>
            )}
          />

          {/* Import consent — only in create mode when source URL is present */}
          {mode === "create" && watchedSourceUrl && (
            <FormField
              control={form.control}
              name="import_consent"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/20">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <div className="space-y-1 leading-none">
                    <FormLabel className="text-sm font-medium leading-snug cursor-pointer">
                      {t("add.import_consent_label")}
                    </FormLabel>
                    <FormMessage />
                  </div>
                </FormItem>
              )}
            />
          )}

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
                    ingredient_name: "",
                    quantity: 1,
                    unit: "piece",
                    notes: "",
                    name_en: null,
                    category: null,
                  })
                }
              >
                <Plus className="mr-1 h-3 w-3" /> {t("form.add_ingredient")}
              </Button>
            </div>
            <div className="space-y-3">
              {ingredientFields.map((field, index) => (
                <div key={field.id} className="flex flex-col gap-1">
                  <div className="flex gap-2 items-start">
                    <FormField
                      control={form.control}
                      name={`ingredients.${index}.ingredient_name`}
                      render={({ field: f }) => (
                        <FormItem className="flex-1">
                          <FormControl>
                            <Input
                              placeholder={t(
                                "form.ingredient_name_placeholder",
                                { defaultValue: "Ingredient name" },
                              )}
                              {...f}
                            />
                          </FormControl>
                          <FormMessage />
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
                          <FormControl>
                            <UnitSelect
                              value={f.value}
                              onValueChange={f.onChange}
                            />
                          </FormControl>
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
              ))}
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
                              const label = ing.ingredient_name
                              if (!label) return null
                              const active = selectedIndices.includes(ingIdx)
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
            <Button variant="outline" disabled={isPending}>
              {tCommon("cancel")}
            </Button>
          </DialogClose>
          <LoadingButton type="submit" loading={isPending}>
            {tCommon("save")}
          </LoadingButton>
        </DialogFooter>
      </form>
    </Form>
  )
}

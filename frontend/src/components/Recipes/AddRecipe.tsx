import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, Loader2, Plus, Trash2 } from "lucide-react"
import { useState } from "react"
import { type Resolver, useFieldArray, useForm } from "react-hook-form"
import { z } from "zod"

import { IngredientsService, RecipesService, type Unit } from "@/client"
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

const UNITS = [
  "g",
  "kg",
  "ml",
  "L",
  "piece",
  "tbsp",
  "tsp",
  "cup",
  "oz",
  "lb",
  "bunch",
  "pinch",
  "clove",
  "slice",
  "can",
  "package",
]

const ingredientSchema = z.object({
  ingredient_id: z.string().uuid({ message: "Select an ingredient" }),
  quantity: z.coerce.number().positive(),
  unit: z.string().min(1),
  notes: z.string().optional(),
})

const formSchema = z.object({
  title: z.string().min(1, { message: "Title is required" }),
  description: z.string().optional(),
  instructions: z.string().optional(),
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
  ingredients: z.array(ingredientSchema),
})

type FormData = z.infer<typeof formSchema>

const AddRecipe = () => {
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
      instructions: "",
      servings: "",
      prep_time_minutes: "",
      cook_time_minutes: "",
      ingredients: [],
    },
  })

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "ingredients",
  })

  const handleImport = async () => {
    if (!importUrl.trim()) return
    setIsImporting(true)
    try {
      const parsed = await RecipesService.importRecipeUrl({
        requestBody: { url: importUrl },
      })
      // Match parsed ingredient names to existing ingredients
      const existingIngredients = ingredientsData?.data ?? []
      const matchedIngredients = (parsed.ingredients ?? [])
        .map((pi) => {
          const match = existingIngredients.find(
            (ing) => ing.name.toLowerCase() === pi.name.toLowerCase(),
          )
          return match
            ? {
                ingredient_id: match.id,
                quantity: pi.quantity,
                unit: pi.unit as Unit,
                notes: pi.notes ?? "",
              }
            : null
        })
        .filter(Boolean) as FormData["ingredients"]

      form.reset({
        title: parsed.title,
        description: parsed.description ?? "",
        instructions: parsed.instructions ?? "",
        servings: parsed.servings ?? "",
        prep_time_minutes: parsed.prep_time_minutes ?? "",
        cook_time_minutes: parsed.cook_time_minutes ?? "",
        ingredients: matchedIngredients,
      })
      setImportUrl("")
      showSuccessToast(
        `Recipe imported. ${(parsed.ingredients ?? []).length - matchedIngredients.length} ingredient(s) not matched — add them manually.`,
      )
    } catch {
      showErrorToast("Failed to import recipe. Check the URL and try again.")
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
          instructions: data.instructions || null,
          servings: data.servings ? Number(data.servings) : null,
          prep_time_minutes: data.prep_time_minutes
            ? Number(data.prep_time_minutes)
            : null,
          cook_time_minutes: data.cook_time_minutes
            ? Number(data.cook_time_minutes)
            : null,
          ingredients: data.ingredients.map((i) => ({
            ingredient_id: i.ingredient_id,
            quantity: i.quantity,
            unit: i.unit as Unit,
            notes: i.notes || null,
          })),
        },
      }),
    onSuccess: () => {
      showSuccessToast("Recipe created successfully")
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["recipes"] }),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="my-4">
          <Plus className="mr-2" />
          Add Recipe
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add Recipe</DialogTitle>
          <DialogDescription>
            Create a new recipe with ingredients.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))}>
            <div className="grid gap-4 py-4">
              {/* Import from URL */}
              <div className="flex gap-2 p-3 rounded-md border border-dashed bg-muted/30">
                <Input
                  placeholder="Paste a recipe URL to auto-fill…"
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
                  <span className="ml-1.5">Import</span>
                </Button>
              </div>

              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Title <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="e.g. Spaghetti Bolognese"
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
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Input placeholder="Short description" {...field} />
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
                      <FormLabel>Servings</FormLabel>
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
                      <FormLabel>Prep (min)</FormLabel>
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
                      <FormLabel>Cook (min)</FormLabel>
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
              <FormField
                control={form.control}
                name="instructions"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Instructions</FormLabel>
                    <FormControl>
                      <textarea
                        className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        placeholder="Step by step instructions..."
                        {...field}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />

              {/* Ingredients */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <FormLabel>Ingredients</FormLabel>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      append({
                        ingredient_id: "",
                        quantity: 1,
                        unit: "piece",
                        notes: "",
                      })
                    }
                  >
                    <Plus className="mr-1 h-3 w-3" /> Add
                  </Button>
                </div>
                <div className="space-y-2">
                  {fields.map((field, index) => (
                    <div key={field.id} className="flex gap-2 items-start">
                      <FormField
                        control={form.control}
                        name={`ingredients.${index}.ingredient_id`}
                        render={({ field: f }) => (
                          <FormItem className="flex-1">
                            <Select onValueChange={f.onChange} value={f.value}>
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="Ingredient" />
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
                        name={`ingredients.${index}.quantity`}
                        render={({ field: f }) => (
                          <FormItem className="w-20">
                            <FormControl>
                              <Input
                                type="number"
                                min={0.01}
                                step="any"
                                placeholder="Qty"
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
                            <Select onValueChange={f.onChange} value={f.value}>
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                {UNITS.map((u) => (
                                  <SelectItem key={u} value={u}>
                                    {u}
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
                        onClick={() => remove(index)}
                        className="mt-0.5"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddRecipe

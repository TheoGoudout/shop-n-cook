import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Pencil, Plus, Trash2 } from "lucide-react"
import { useState } from "react"
import { type Resolver, useFieldArray, useForm } from "react-hook-form"
import { z } from "zod"

import {
  IngredientsService,
  type RecipePublic,
  RecipesService,
  type Unit,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
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

interface Props {
  recipe: RecipePublic
  onSuccess: () => void
}

const EditRecipe = ({ recipe, onSuccess }: Props) => {
  const [isOpen, setIsOpen] = useState(false)
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
      title: recipe.title,
      description: recipe.description ?? "",
      instructions: recipe.instructions ?? "",
      servings: recipe.servings ?? "",
      prep_time_minutes: recipe.prep_time_minutes ?? "",
      cook_time_minutes: recipe.cook_time_minutes ?? "",
      ingredients: (recipe.ingredients ?? []).map((i) => ({
        ingredient_id: i.ingredient_id,
        quantity: i.quantity,
        unit: i.unit,
        notes: i.notes ?? "",
      })),
    },
  })

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "ingredients",
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      RecipesService.updateRecipe({
        id: recipe.id,
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
      showSuccessToast("Recipe updated successfully")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] })
      queryClient.invalidateQueries({ queryKey: ["recipe", recipe.id] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        Edit
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Recipe</DialogTitle>
          <DialogDescription>
            Update the recipe details and ingredients.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))}>
            <div className="grid gap-4 py-4">
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

export default EditRecipe

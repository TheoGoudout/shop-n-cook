import { useFieldArray, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import type { RecipeCreate, RecipePublic } from "@/client"

const ingredientSchema = z.object({
  name: z.string().min(1, "Required"),
  quantity: z.coerce.number().min(0, "Must be ≥ 0"),
  unit: z.string().min(1, "Required"),
})

const schema = z.object({
  title: z.string().min(1, "Title is required"),
  description: z.string().optional(),
  base_servings: z.coerce.number().int().min(1, "At least 1"),
  ingredients: z.array(ingredientSchema),
})

type FormValues = z.infer<typeof schema>

interface RecipeFormProps {
  defaultValues?: Partial<RecipePublic>
  onSubmit: (data: RecipeCreate) => void
  isLoading?: boolean
  submitLabel?: string
}

export function RecipeForm({
  defaultValues,
  onSubmit,
  isLoading,
  submitLabel = "Save",
}: RecipeFormProps) {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: defaultValues?.title ?? "",
      description: defaultValues?.description ?? "",
      base_servings: defaultValues?.base_servings ?? 4,
      ingredients: defaultValues?.ingredients?.map((i) => ({
        name: i.name,
        quantity: i.quantity,
        unit: i.unit,
      })) ?? [],
    },
  })

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "ingredients",
  })

  const handleSubmit = (values: FormValues) => {
    onSubmit({
      title: values.title,
      description: values.description || null,
      base_servings: values.base_servings,
      ingredients: values.ingredients,
    })
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl>
                <Input placeholder="Recipe name" {...field} />
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
                <Textarea
                  placeholder="Instructions, notes..."
                  rows={4}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="base_servings"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Base servings</FormLabel>
              <FormControl>
                <Input type="number" min={1} {...field} className="w-24" />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <FormLabel>Ingredients</FormLabel>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => append({ name: "", quantity: 0, unit: "" })}
            >
              <Plus className="h-4 w-4 mr-1" />
              Add ingredient
            </Button>
          </div>

          {fields.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No ingredients yet. Click "Add ingredient" to start.
            </p>
          )}

          {fields.map((field, index) => (
            <div key={field.id} className="flex gap-2 items-start">
              <FormField
                control={form.control}
                name={`ingredients.${index}.name`}
                render={({ field }) => (
                  <FormItem className="flex-1">
                    {index === 0 && <FormLabel>Name</FormLabel>}
                    <FormControl>
                      <Input placeholder="Flour" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name={`ingredients.${index}.quantity`}
                render={({ field }) => (
                  <FormItem className="w-24">
                    {index === 0 && <FormLabel>Qty</FormLabel>}
                    <FormControl>
                      <Input type="number" step="any" min={0} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name={`ingredients.${index}.unit`}
                render={({ field }) => (
                  <FormItem className="w-24">
                    {index === 0 && <FormLabel>Unit</FormLabel>}
                    <FormControl>
                      <Input placeholder="g" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className={index === 0 ? "mt-8" : ""}
                onClick={() => remove(index)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          ))}
        </div>

        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Saving..." : submitLabel}
        </Button>
      </form>
    </Form>
  )
}

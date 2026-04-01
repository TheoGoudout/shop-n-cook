import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus } from "lucide-react"

import { RecipesService, ShoppingListsService } from "@/client"
import type { ShoppingListPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const schema = z.object({
  recipe_id: z.string().min(1, "Select a recipe"),
  num_people: z.coerce.number().int().min(1),
  num_meals: z.coerce.number().int().min(1),
})

type FormValues = z.infer<typeof schema>

interface AddRecipeToListProps {
  listId: string
  onUpdated: (updated: ShoppingListPublic) => void
}

export function AddRecipeToList({ listId, onUpdated }: AddRecipeToListProps) {
  const [open, setOpen] = useState(false)

  const { data: recipes } = useQuery({
    queryFn: () => RecipesService.readRecipes({ skip: 0, limit: 100 }),
    queryKey: ["recipes"],
  })

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { recipe_id: "", num_people: 4, num_meals: 1 },
  })

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      ShoppingListsService.addRecipe({
        id: listId,
        requestBody: {
          recipe_id: values.recipe_id,
          num_people: values.num_people,
          num_meals: values.num_meals,
        },
      }),
    onSuccess: (updated) => {
      onUpdated(updated)
      setOpen(false)
      form.reset()
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Plus className="h-4 w-4 mr-1" />
          Add recipe
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add recipe to list</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
            className="space-y-4"
          >
            <FormField
              control={form.control}
              name="recipe_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Recipe</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a recipe" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {recipes?.data.map((r) => (
                        <SelectItem key={r.id} value={r.id}>
                          {r.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="flex gap-4">
              <FormField
                control={form.control}
                name="num_people"
                render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormLabel>People</FormLabel>
                    <FormControl>
                      <Input type="number" min={1} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="num_meals"
                render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormLabel>Meals</FormLabel>
                    <FormControl>
                      <Input type="number" min={1} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <Button type="submit" disabled={mutation.isPending} className="w-full">
              {mutation.isPending ? "Adding..." : "Add to list"}
            </Button>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

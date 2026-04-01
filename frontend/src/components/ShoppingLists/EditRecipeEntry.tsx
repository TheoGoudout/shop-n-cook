import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Pencil } from "lucide-react"

import { ShoppingListsService } from "@/client"
import type { ShoppingListPublic, ShoppingListRecipePublic } from "@/client"
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

const schema = z.object({
  num_people: z.coerce.number().int().min(1),
  num_meals: z.coerce.number().int().min(1),
})

type FormValues = z.infer<typeof schema>

interface EditRecipeEntryProps {
  listId: string
  entry: ShoppingListRecipePublic
  onUpdated: (updated: ShoppingListPublic) => void
}

export function EditRecipeEntry({ listId, entry, onUpdated }: EditRecipeEntryProps) {
  const [open, setOpen] = useState(false)

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      num_people: entry.num_people,
      num_meals: entry.num_meals,
    },
  })

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      ShoppingListsService.updateRecipe({
        id: listId,
        entryId: entry.id,
        requestBody: values,
      }),
    onSuccess: (updated) => {
      onUpdated(updated)
      setOpen(false)
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" className="h-7 w-7">
          <Pencil className="h-3.5 w-3.5" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Edit — {entry.recipe_title}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
            className="space-y-4"
          >
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
              {mutation.isPending ? "Saving..." : "Save"}
            </Button>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

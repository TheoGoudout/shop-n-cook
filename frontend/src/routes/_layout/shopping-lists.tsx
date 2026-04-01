import { zodResolver } from "@hookform/resolvers/zod"
import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { BookOpen, Plus, ShoppingCart, Trash2 } from "lucide-react"
import { Suspense, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import type { ShoppingListCreate } from "@/client"
import { ShoppingListsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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

export const Route = createFileRoute("/_layout/shopping-lists")({
  component: ShoppingListsPage,
  head: () => ({
    meta: [{ title: "Shopping Lists - Shop'n'Cook" }],
  }),
})

function getListsQueryOptions() {
  return {
    queryFn: () => ShoppingListsService.readShoppingLists(),
    queryKey: ["shopping-lists"],
  }
}

const schema = z.object({ name: z.string().min(1, "Name is required") })
type FormValues = z.infer<typeof schema>

function CreateListDialog() {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "" },
  })

  const mutation = useMutation({
    mutationFn: (data: ShoppingListCreate) =>
      ShoppingListsService.createShoppingList({ requestBody: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["shopping-lists"] })
      setOpen(false)
      form.reset()
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4 mr-1" />
          New list
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>New shopping list</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
            className="space-y-4"
          >
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Weekly groceries" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button
              type="submit"
              disabled={mutation.isPending}
              className="w-full"
            >
              {mutation.isPending ? "Creating..." : "Create"}
            </Button>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function ListsContent() {
  const { data } = useSuspenseQuery(getListsQueryOptions())
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: (id: string) => ShoppingListsService.deleteShoppingList({ id }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["shopping-lists"] }),
  })

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-16">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ShoppingCart className="h-10 w-10 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No shopping lists yet</h3>
        <p className="text-muted-foreground mt-1">
          Create a new list to start planning your shopping.
        </p>
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.data.map((list) => (
        <Card key={list.id} className="hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <div className="flex items-start justify-between gap-2">
              <Link
                to="/shopping-lists/$listId"
                params={{ listId: list.id }}
                className="flex-1"
              >
                <CardTitle className="text-base hover:underline line-clamp-2">
                  {list.name}
                </CardTitle>
              </Link>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                onClick={() => deleteMutation.mutate(list.id)}
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <BookOpen className="h-3.5 w-3.5" />
              <span>
                {list.recipe_count} recipe{list.recipe_count !== 1 ? "s" : ""}
              </span>
              {list.created_at && (
                <span className="ml-auto text-xs">
                  {new Date(list.created_at).toLocaleDateString()}
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function ShoppingListsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Shopping Lists</h1>
          <p className="text-muted-foreground">
            Plan your shopping from your recipes
          </p>
        </div>
        <CreateListDialog />
      </div>
      <Suspense
        fallback={
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Card key={i} className="h-28 animate-pulse bg-muted" />
            ))}
          </div>
        }
      >
        <ListsContent />
      </Suspense>
    </div>
  )
}

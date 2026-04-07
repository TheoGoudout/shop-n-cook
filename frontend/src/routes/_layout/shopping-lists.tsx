import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ShoppingCart } from "lucide-react"
import { Suspense } from "react"

import { ShoppingListsService } from "@/client"
import PendingItems from "@/components/Pending/PendingItems"
import AddShoppingList from "@/components/ShoppingLists/AddShoppingList"
import { ShoppingListCard } from "@/components/ShoppingLists/ShoppingListCard"

function getShoppingListsQueryOptions() {
  return {
    queryFn: () => ShoppingListsService.readShoppingLists({ limit: 100 }),
    queryKey: ["shopping-lists"],
  }
}

export const Route = createFileRoute("/_layout/shopping-lists")({
  component: ShoppingLists,
  head: () => ({
    meta: [{ title: "Shopping Lists - Shop n Cook" }],
  }),
})

function ShoppingListsContent() {
  const { data } = useSuspenseQuery(getShoppingListsQueryOptions())

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ShoppingCart className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No shopping lists yet</h3>
        <p className="text-muted-foreground">
          Create a list and start adding ingredients or recipes
        </p>
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.data.map((list) => (
        <ShoppingListCard key={list.id} list={list} />
      ))}
    </div>
  )
}

function ShoppingLists() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Shopping Lists</h1>
          <p className="text-muted-foreground">Plan your grocery runs</p>
        </div>
        <AddShoppingList />
      </div>
      <Suspense fallback={<PendingItems />}>
        <ShoppingListsContent />
      </Suspense>
    </div>
  )
}

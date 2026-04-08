import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ShoppingCart } from "lucide-react"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"

import { ShoppingListsService } from "@/client"
import { APP_NAME } from "@/lib/config"
import PendingItems from "@/components/Pending/PendingItems"
import AddShoppingList from "@/components/ShoppingLists/AddShoppingList"
import { ShoppingListCard } from "@/components/ShoppingLists/ShoppingListCard"

function getShoppingListsQueryOptions() {
  return {
    queryFn: () => ShoppingListsService.readShoppingLists({ limit: 100 }),
    queryKey: ["shopping-lists"],
  }
}

export const Route = createFileRoute("/_layout/shopping-lists/")({
  component: ShoppingLists,
  head: () => ({
    meta: [{ title: `Shopping Lists - ${APP_NAME}` }],
  }),
})

function ShoppingListsContent() {
  const { t } = useTranslation("shopping")
  const { data } = useSuspenseQuery(getShoppingListsQueryOptions())

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ShoppingCart className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">{t("page.empty_title")}</h3>
        <p className="text-muted-foreground">
          {t("page.empty_subtitle")}
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
  const { t } = useTranslation("shopping")

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("page.title")}</h1>
          <p className="text-muted-foreground">{t("page.subtitle")}</p>
        </div>
        <AddShoppingList />
      </div>
      <Suspense fallback={<PendingItems />}>
        <ShoppingListsContent />
      </Suspense>
    </div>
  )
}

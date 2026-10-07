import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ShoppingCart } from "lucide-react"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"
import { ShoppingListsService } from "@/client"
import { EmptyListState } from "@/components/Common/EmptyListState"
import { PageHeader } from "@/components/Common/PageHeader"
import PendingItems from "@/components/Pending/PendingItems"
import AddShoppingList from "@/components/ShoppingLists/AddShoppingList"
import { ShoppingListCard } from "@/components/ShoppingLists/ShoppingListCard"
import { APP_NAME } from "@/lib/config"

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
      <EmptyListState
        icon={ShoppingCart}
        title={t("page.empty_title")}
        subtitle={t("page.empty_subtitle")}
      />
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
      <PageHeader title={t("page.title")} subtitle={t("page.subtitle")}>
        <AddShoppingList />
      </PageHeader>
      <Suspense fallback={<PendingItems />}>
        <ShoppingListsContent />
      </Suspense>
    </div>
  )
}

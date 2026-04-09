import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  ArrowLeft,
  CalendarRange,
  CheckCircle2,
  ChefHat,
  Circle,
  ShoppingCart,
  Trash2,
  Users,
} from "lucide-react"
import { Suspense } from "react"

import {
  type ShoppingListItemPublic,
  type ShoppingListPublic,
  type ShoppingListRecipePublic,
  ShoppingListsService,
} from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useCustomToast from "@/hooks/useCustomToast"
import { APP_NAME } from "@/lib/config"
import { handleError } from "@/utils"

function getListQueryOptions(id: string) {
  return {
    queryFn: () => ShoppingListsService.readShoppingList({ id }),
    queryKey: ["shopping-list", id],
  }
}

export const Route = createFileRoute("/_layout/shopping-lists/$id")({
  component: ShoppingListDetail,
  head: () => ({
    meta: [{ title: `Shopping List - ${APP_NAME}` }],
  }),
})

// ---- helpers ---- //

function formatDate(d: string) {
  return new Date(d).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  })
}

/** Group items by ingredient_category, sorted by category name */
function groupByCategory(items: ShoppingListItemPublic[]) {
  const map = new Map<string, ShoppingListItemPublic[]>()
  for (const item of items) {
    const cat = item.ingredient_category
    if (!map.has(cat)) map.set(cat, [])
    map.get(cat)!.push(item)
  }
  return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
}

/** For an ingredient, compute per-recipe quantity contributions based on planned_recipes */
function recipeBreakdown(
  item: ShoppingListItemPublic,
  planned: ShoppingListRecipePublic[],
): { title: string; quantity: number; unit: string }[] {
  const results: { title: string; quantity: number; unit: string }[] = []
  for (const pr of planned) {
    const scale = pr.servings_planned / Math.max(pr.recipe_servings ?? 1, 1)
    const ri = pr.ingredients?.find(
      (i) => i.ingredient_id === item.ingredient_id && i.unit === item.unit,
    )
    if (ri) {
      results.push({
        title: pr.recipe_title,
        quantity: Math.round(ri.quantity * scale * 100) / 100,
        unit: item.unit,
      })
    }
  }
  return results
}

// ---- Shopping tab ---- //

function ShoppingTab({ list }: { list: ShoppingListPublic }) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const id = list.id
  const planned = list.planned_recipes ?? []
  const items = list.items ?? []

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["shopping-list", id] })

  const checkMutation = useMutation({
    mutationFn: ({ itemId, checked }: { itemId: string; checked: boolean }) =>
      ShoppingListsService.updateItem({
        id,
        itemId,
        requestBody: { is_checked: checked },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const removeItemMutation = useMutation({
    mutationFn: (itemId: string) =>
      ShoppingListsService.deleteItem({ id, itemId }),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic py-4">
        No items yet. Add ingredients or use "Add recipe" to populate this list.
      </p>
    )
  }

  const grouped = groupByCategory(items)
  const checkedCount = items.filter((i) => i.is_checked).length

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {checkedCount}/{items.length} items checked
      </p>
      {grouped.map(([category, catItems]) => (
        <Card key={category}>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm capitalize text-muted-foreground font-medium tracking-wide">
              {category}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3 space-y-2">
            {catItems.map((item) => {
              const breakdown = recipeBreakdown(item, planned)
              return (
                <div key={item.id} className="group">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      checked={item.is_checked}
                      onCheckedChange={(c) =>
                        checkMutation.mutate({
                          itemId: item.id,
                          checked: Boolean(c),
                        })
                      }
                    />
                    <span
                      className={`flex-1 text-sm font-medium ${item.is_checked ? "line-through text-muted-foreground" : ""}`}
                    >
                      {item.ingredient_name}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {item.quantity} {item.unit}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100"
                      onClick={() => removeItemMutation.mutate(item.id)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                  {breakdown.length > 1 && (
                    <div className="ml-6 mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5">
                      {breakdown.map((b) => (
                        <span
                          key={b.title}
                          className="text-xs text-muted-foreground"
                        >
                          {b.title}: {b.quantity} {b.unit}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

// ---- Meals tab ---- //

function MealsTab({ list }: { list: ShoppingListPublic }) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const id = list.id
  const planned = list.planned_recipes ?? []

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["shopping-list", id] })

  const togglePrepared = useMutation({
    mutationFn: ({
      plannedRecipeId,
      isPrepared,
    }: {
      plannedRecipeId: string
      isPrepared: boolean
    }) =>
      ShoppingListsService.updatePlannedRecipe({
        id,
        plannedRecipeId,
        requestBody: { is_prepared: isPrepared },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const removePlanned = useMutation({
    mutationFn: (plannedRecipeId: string) =>
      ShoppingListsService.deletePlannedRecipe({ id, plannedRecipeId }),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  if (planned.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic py-4">
        No recipes planned yet. Go back and use "Add recipe" on the shopping
        list.
      </p>
    )
  }

  const preparedCount = planned.filter((r) => r.is_prepared).length

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {preparedCount}/{planned.length} meals prepared
      </p>
      {planned.map((pr) => (
        <Card key={pr.id} className={pr.is_prepared ? "opacity-60" : ""}>
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <button
                type="button"
                onClick={() =>
                  togglePrepared.mutate({
                    plannedRecipeId: pr.id,
                    isPrepared: !pr.is_prepared,
                  })
                }
                className="mt-0.5 shrink-0 text-primary"
              >
                {pr.is_prepared ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                ) : (
                  <Circle className="h-5 w-5 text-muted-foreground" />
                )}
              </button>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Link
                    to="/recipes/$id"
                    params={{ id: pr.recipe_id }}
                    className={`font-medium hover:underline ${pr.is_prepared ? "line-through" : ""}`}
                  >
                    {pr.recipe_title}
                  </Link>
                  <Badge variant="secondary" className="text-xs">
                    <Users className="h-3 w-3 mr-1" />
                    {pr.servings_planned} servings
                  </Badge>
                  {pr.is_prepared && (
                    <Badge variant="outline" className="text-xs text-green-600">
                      Done
                    </Badge>
                  )}
                </div>
                {(pr.ingredients ?? []).length > 0 && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {(pr.ingredients ?? []).length} ingredients
                    {pr.recipe_servings &&
                    pr.recipe_servings !== pr.servings_planned
                      ? ` · scaled from ${pr.recipe_servings} servings`
                      : ""}
                  </p>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                onClick={() => removePlanned.mutate(pr.id)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

// ---- Main content ---- //

function ShoppingListDetailContent() {
  const { id } = Route.useParams()
  const { data: list } = useSuspenseQuery(getListQueryOptions(id))
  const items = list.items ?? []
  const planned = list.planned_recipes ?? []
  const checkedCount = items.filter((i) => i.is_checked).length
  const preparedCount = planned.filter((r) => r.is_prepared).length

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{list.name}</h1>
        <div className="flex flex-wrap gap-4 mt-2 text-sm text-muted-foreground">
          {list.start_date && list.end_date && (
            <div className="flex items-center gap-1.5">
              <CalendarRange className="h-4 w-4" />
              <span>
                {formatDate(list.start_date)} – {formatDate(list.end_date)}
              </span>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <ShoppingCart className="h-4 w-4" />
            <span>
              {checkedCount}/{items.length} items
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <ChefHat className="h-4 w-4" />
            <span>
              {preparedCount}/{planned.length} meals
            </span>
          </div>
        </div>
      </div>

      <Tabs defaultValue="shopping">
        <TabsList>
          <TabsTrigger value="shopping">
            <ShoppingCart className="h-4 w-4 mr-2" />
            Shopping
          </TabsTrigger>
          <TabsTrigger value="meals">
            <ChefHat className="h-4 w-4 mr-2" />
            Meals
          </TabsTrigger>
        </TabsList>
        <TabsContent value="shopping" className="mt-4">
          <ShoppingTab list={list} />
        </TabsContent>
        <TabsContent value="meals" className="mt-4">
          <MealsTab list={list} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function ShoppingListDetail() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link to="/shopping-lists">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Shopping Lists
          </Link>
        </Button>
      </div>
      <Suspense
        fallback={
          <div className="flex items-center gap-2 text-muted-foreground">
            <ShoppingCart className="h-5 w-5 animate-pulse" />
            <span>Loading…</span>
          </div>
        }
      >
        <ShoppingListDetailContent />
      </Suspense>
    </div>
  )
}

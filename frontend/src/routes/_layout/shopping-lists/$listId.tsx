import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Trash2,
  Users,
  UtensilsCrossed,
} from "lucide-react"
import { useState } from "react"
import type {
  AggregatedIngredient,
  ShoppingListPublic,
  ShoppingListRecipePublic,
} from "@/client"
import { ShoppingListsService } from "@/client"
import { AddRecipeToList } from "@/components/ShoppingLists/AddRecipeToList"
import { EditRecipeEntry } from "@/components/ShoppingLists/EditRecipeEntry"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"

export const Route = createFileRoute("/_layout/shopping-lists/$listId")({
  component: ShoppingListDetailPage,
  head: () => ({
    meta: [{ title: "Shopping List - Shop'n'Cook" }],
  }),
})

function formatQty(qty: number): string {
  const rounded = Math.round(qty * 100) / 100
  return rounded % 1 === 0 ? rounded.toFixed(0) : rounded.toString()
}

function IngredientRow({
  ingredient,
  listId,
  onUpdated,
}: {
  ingredient: AggregatedIngredient
  listId: string
  onUpdated: (updated: ShoppingListPublic) => void
}) {
  const [expanded, setExpanded] = useState(false)

  const toggleMutation = useMutation({
    mutationFn: (checked: boolean) =>
      ShoppingListsService.toggleIngredient({
        id: listId,
        ingredientName: ingredient.name,
        unit: ingredient.unit,
        isChecked: checked,
      }),
    onSuccess: onUpdated,
  })

  const multipleRecipes = ingredient.sources.length > 1

  return (
    <div
      className={`rounded-md border transition-colors ${
        ingredient.is_checked ? "bg-muted/50 opacity-60" : "bg-background"
      }`}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <Checkbox
          checked={ingredient.is_checked}
          onCheckedChange={(checked) => toggleMutation.mutate(Boolean(checked))}
          disabled={toggleMutation.isPending}
        />
        <span
          className={`flex-1 font-medium ${
            ingredient.is_checked ? "line-through text-muted-foreground" : ""
          }`}
        >
          {ingredient.name}
        </span>
        <Badge variant="secondary" className="shrink-0">
          {formatQty(ingredient.total_quantity)} {ingredient.unit}
        </Badge>
        {multipleRecipes && (
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        )}
      </div>

      {/* Sources breakdown */}
      {(multipleRecipes ? expanded : false) && (
        <div className="px-4 pb-3 space-y-1 border-t">
          {ingredient.sources.map((src, i) => (
            <div
              key={i}
              className="flex items-center gap-2 text-sm text-muted-foreground pl-7 pt-1"
            >
              <BookOpen className="h-3.5 w-3.5 shrink-0" />
              <span className="flex-1">{src.recipe_title as string}</span>
              <span>
                {formatQty(src.quantity as number)} {src.unit as string}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Single recipe source — show inline */}
      {!multipleRecipes && ingredient.sources[0] && (
        <div className="px-4 pb-2 text-xs text-muted-foreground flex items-center gap-1 pl-11">
          <BookOpen className="h-3 w-3" />
          {ingredient.sources[0].recipe_title as string}
        </div>
      )}
    </div>
  )
}

function RecipeEntry({
  entry,
  listId,
  onUpdated,
}: {
  entry: ShoppingListRecipePublic
  listId: string
  onUpdated: (updated: ShoppingListPublic) => void
}) {
  const removeMutation = useMutation({
    mutationFn: () =>
      ShoppingListsService.removeRecipeFromList({
        id: listId,
        entryId: entry.id,
      }),
    onSuccess: onUpdated,
  })

  return (
    <div className="flex items-center gap-2 py-2 px-3 rounded-md bg-muted/50">
      <UtensilsCrossed className="h-4 w-4 text-muted-foreground shrink-0" />
      <span className="flex-1 font-medium text-sm">{entry.recipe_title}</span>
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <Users className="h-3.5 w-3.5" />
        {entry.num_people} × {entry.num_meals} meal
        {entry.num_meals > 1 ? "s" : ""}
      </div>
      <EditRecipeEntry listId={listId} entry={entry} onUpdated={onUpdated} />
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 text-muted-foreground hover:text-destructive"
        onClick={() => removeMutation.mutate()}
        disabled={removeMutation.isPending}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

function ShoppingListDetailPage() {
  const { listId } = Route.useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: list, isLoading } = useQuery({
    queryFn: () => ShoppingListsService.readShoppingList({ id: listId }),
    queryKey: ["shopping-lists", listId],
  })

  const [localList, setLocalList] = useState<ShoppingListPublic | null>(null)
  const current = localList ?? list ?? null

  const handleUpdated = (updated: ShoppingListPublic) => {
    setLocalList(updated)
    queryClient.setQueryData(["shopping-lists", listId], updated)
  }

  if (isLoading || !current) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  const checkedCount = current.ingredients.filter((i) => i.is_checked).length
  const totalCount = current.ingredients.length

  return (
    <div className="flex flex-col gap-6">
      <Button
        variant="ghost"
        size="sm"
        className="w-fit -ml-2"
        onClick={() => navigate({ to: "/shopping-lists" })}
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back to lists
      </Button>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{current.name}</h1>
          {totalCount > 0 && (
            <p className="text-muted-foreground mt-1 text-sm">
              {checkedCount}/{totalCount} ingredients checked
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Ingredients */}
        <div className="space-y-3">
          <h2 className="font-semibold text-lg">Shopping list</h2>
          {current.ingredients.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                <p>Add recipes to see the aggregated ingredients here.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {/* Pending first */}
              {current.ingredients
                .filter((i) => !i.is_checked)
                .map((ing) => (
                  <IngredientRow
                    key={`${ing.name}-${ing.unit}`}
                    ingredient={ing}
                    listId={listId}
                    onUpdated={handleUpdated}
                  />
                ))}

              {checkedCount > 0 && (
                <>
                  <Separator className="my-3" />
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                    Done ({checkedCount})
                  </p>
                  {current.ingredients
                    .filter((i) => i.is_checked)
                    .map((ing) => (
                      <IngredientRow
                        key={`${ing.name}-${ing.unit}`}
                        ingredient={ing}
                        listId={listId}
                        onUpdated={handleUpdated}
                      />
                    ))}
                </>
              )}
            </div>
          )}
        </div>

        {/* Recipes panel */}
        <Card className="h-fit">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Recipes</CardTitle>
              <AddRecipeToList listId={listId} onUpdated={handleUpdated} />
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {current.recipes.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No recipes added yet.
              </p>
            ) : (
              current.recipes.map((entry) => (
                <RecipeEntry
                  key={entry.id}
                  entry={entry}
                  listId={listId}
                  onUpdated={handleUpdated}
                />
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

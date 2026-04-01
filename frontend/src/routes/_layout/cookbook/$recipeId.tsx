import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { ArrowLeft, Edit2, X } from "lucide-react"
import { Suspense, useState } from "react"
import type { RecipeUpdate } from "@/client"
import { RecipesService } from "@/client"
import { DeleteRecipe } from "@/components/Cookbook/DeleteRecipe"
import { RecipeForm } from "@/components/Cookbook/RecipeForm"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"

export const Route = createFileRoute("/_layout/cookbook/$recipeId")({
  component: RecipeDetailPage,
  head: () => ({
    meta: [{ title: "Recipe - Shop'n'Cook" }],
  }),
})

function getRecipeQueryOptions(id: string) {
  return {
    queryFn: () => RecipesService.readRecipe({ id }),
    queryKey: ["recipes", id],
  }
}

function RecipeDetail({ recipeId }: { recipeId: string }) {
  const [editing, setEditing] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { data: recipe } = useSuspenseQuery(getRecipeQueryOptions(recipeId))

  const updateMutation = useMutation({
    mutationFn: (data: RecipeUpdate) =>
      RecipesService.updateRecipe({ id: recipeId, requestBody: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] })
      setEditing(false)
    },
  })

  if (editing) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
            <X className="h-4 w-4 mr-1" />
            Cancel
          </Button>
          <h1 className="text-xl font-bold">Edit recipe</h1>
        </div>
        <RecipeForm
          defaultValues={recipe}
          onSubmit={(data) => updateMutation.mutate(data)}
          isLoading={updateMutation.isPending}
          submitLabel="Save changes"
        />
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{recipe.title}</h1>
          <p className="text-muted-foreground mt-1">
            Base: {recipe.base_servings} serving
            {recipe.base_servings > 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            <Edit2 className="h-4 w-4 mr-1" />
            Edit
          </Button>
          <DeleteRecipe
            recipeId={recipe.id}
            recipeTitle={recipe.title}
            onDeleted={() => navigate({ to: "/cookbook" })}
          />
        </div>
      </div>

      {recipe.description && (
        <div>
          <h2 className="font-semibold mb-2">Description / Instructions</h2>
          <p className="text-muted-foreground whitespace-pre-wrap">
            {recipe.description}
          </p>
        </div>
      )}

      <Separator />

      <div>
        <h2 className="font-semibold mb-3">
          Ingredients{" "}
          <span className="text-muted-foreground font-normal text-sm">
            (for {recipe.base_servings} serving
            {recipe.base_servings > 1 ? "s" : ""})
          </span>
        </h2>
        {recipe.ingredients.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            No ingredients listed.
          </p>
        ) : (
          <ul className="space-y-2">
            {recipe.ingredients.map((ing) => (
              <li
                key={ing.id}
                className="flex items-center gap-3 py-2 px-3 rounded-md bg-muted/50"
              >
                <span className="flex-1">{ing.name}</span>
                <Badge variant="secondary">
                  {ing.quantity} {ing.unit}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function RecipeDetailPage() {
  const { recipeId } = Route.useParams()
  const navigate = useNavigate()

  return (
    <div className="flex flex-col gap-6">
      <Button
        variant="ghost"
        size="sm"
        className="w-fit -ml-2"
        onClick={() => navigate({ to: "/cookbook" })}
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back to cookbook
      </Button>
      <Suspense
        fallback={
          <div className="space-y-4">
            <div className="h-8 w-48 bg-muted rounded animate-pulse" />
            <div className="h-4 w-24 bg-muted rounded animate-pulse" />
          </div>
        }
      >
        <RecipeDetail recipeId={recipeId} />
      </Suspense>
    </div>
  )
}

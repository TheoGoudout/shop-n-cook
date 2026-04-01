import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { BookOpen, ChefHat, Clock, Plus, Users } from "lucide-react"
import { Suspense, useState } from "react"
import type { RecipeCreate } from "@/client"
import { RecipesService } from "@/client"
import { RecipeForm } from "@/components/Cookbook/RecipeForm"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

export const Route = createFileRoute("/_layout/cookbook")({
  component: Cookbook,
  head: () => ({
    meta: [{ title: "Cookbook - Shop'n'Cook" }],
  }),
})

function getRecipesQueryOptions() {
  return {
    queryFn: () => RecipesService.readRecipes({ skip: 0, limit: 100 }),
    queryKey: ["recipes"],
  }
}

function RecipesList() {
  const { data } = useSuspenseQuery(getRecipesQueryOptions())

  if (data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-16">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ChefHat className="h-10 w-10 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No recipes yet</h3>
        <p className="text-muted-foreground mt-1">
          Create your first recipe to get started.
        </p>
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.data.map((recipe) => (
        <Link
          key={recipe.id}
          to="/cookbook/$recipeId"
          params={{ recipeId: recipe.id }}
        >
          <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
            <CardHeader>
              <CardTitle className="text-base line-clamp-2">
                {recipe.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {recipe.description && (
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {recipe.description}
                </p>
              )}
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Users className="h-3.5 w-3.5" />
                  {recipe.base_servings} servings
                </span>
                <span className="flex items-center gap-1">
                  <BookOpen className="h-3.5 w-3.5" />
                  {recipe.ingredients.length} ingredients
                </span>
              </div>
              {recipe.created_at && (
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {new Date(recipe.created_at).toLocaleDateString()}
                </p>
              )}
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  )
}

function AddRecipeDialog() {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (data: RecipeCreate) =>
      RecipesService.createRecipe({ requestBody: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] })
      setOpen(false)
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4 mr-1" />
          New recipe
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New recipe</DialogTitle>
        </DialogHeader>
        <RecipeForm
          onSubmit={(data) => mutation.mutate(data)}
          isLoading={mutation.isPending}
          submitLabel="Create recipe"
        />
      </DialogContent>
    </Dialog>
  )
}

function Cookbook() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Cookbook</h1>
          <p className="text-muted-foreground">Manage your personal recipes</p>
        </div>
        <AddRecipeDialog />
      </div>
      <Suspense
        fallback={
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Card key={i} className="h-36 animate-pulse bg-muted" />
            ))}
          </div>
        }
      >
        <RecipesList />
      </Suspense>
    </div>
  )
}

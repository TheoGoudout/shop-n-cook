import { useQuery } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { MealPlansService, RecipesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCrudMutation } from "@/hooks/useCrudMutation"

const MEAL_TYPES = [
  "breakfast",
  "lunch",
  "dinner",
  "snack",
  "dessert",
  "drink",
] as const

/** Put a recipe into one day of a plan. */
export function AddEntryDialog({
  planId,
  date,
}: {
  planId: string
  date: string
}) {
  const { t } = useTranslation("mealPlans")
  const { t: tCommon } = useTranslation("common")
  const [open, setOpen] = useState(false)
  const [recipeId, setRecipeId] = useState("")
  const [mealType, setMealType] = useState<string>("dinner")
  const [servings, setServings] = useState("2")
  const [search, setSearch] = useState("")

  // Deferred until the dialog opens — this renders once per day of the plan.
  const { data: recipes } = useQuery({
    queryKey: ["recipes", "for-plan", search],
    queryFn: () =>
      RecipesService.readRecipes({ limit: 50, search: search || undefined }),
    enabled: open,
  })

  const add = useCrudMutation({
    mutationFn: () =>
      MealPlansService.addEntry({
        id: planId,
        requestBody: {
          recipe_id: recipeId,
          entry_date: date,
          meal_type: mealType as (typeof MEAL_TYPES)[number],
          servings: Number(servings) || 2,
        },
      }),
    invalidateKeys: [["meal-plan", planId], ["meal-plans"]],
    onSuccess: () => {
      setOpen(false)
      setRecipeId("")
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="w-full justify-start">
          <Plus className="h-3 w-3" />
          <span className="text-xs">{t("detail.add_recipe")}</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("detail.add_recipe")}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="entry-search">{tCommon("recipe")}</Label>
            <Input
              id="entry-search"
              value={search}
              placeholder={tCommon("recipe")}
              onChange={(e) => setSearch(e.target.value)}
            />
            <Select value={recipeId} onValueChange={setRecipeId}>
              <SelectTrigger>
                <SelectValue placeholder={tCommon("recipe")} />
              </SelectTrigger>
              <SelectContent>
                {(recipes?.data ?? []).map((recipe) => (
                  <SelectItem key={recipe.id} value={recipe.id}>
                    {recipe.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="entry-meal">{tCommon("category")}</Label>
              <Select value={mealType} onValueChange={setMealType}>
                <SelectTrigger id="entry-meal">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MEAL_TYPES.map((type) => (
                    <SelectItem key={type} value={type}>
                      {t(`meal_types.${type}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="entry-servings">{tCommon("servings")}</Label>
              <Input
                id="entry-servings"
                type="number"
                min="1"
                value={servings}
                onChange={(e) => setServings(e.target.value)}
              />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {tCommon("cancel")}
          </Button>
          <LoadingButton
            loading={add.isPending}
            disabled={!recipeId}
            onClick={() => add.mutate()}
          >
            {tCommon("add")}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

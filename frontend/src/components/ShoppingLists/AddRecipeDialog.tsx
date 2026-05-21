import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { RecipesService, ShoppingListsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCrudMutation } from "@/hooks/useCrudMutation"

interface Props {
  listId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AddRecipeDialog({ listId, open, onOpenChange }: Props) {
  const { t } = useTranslation("shopping")
  const { t: tCommon } = useTranslation("common")
  const [selectedRecipe, setSelectedRecipe] = useState("")
  const [servings, setServings] = useState("")

  const { data: recipesData } = useQuery({
    queryKey: ["recipes"],
    queryFn: () => RecipesService.readRecipes({ limit: 100 }),
    enabled: open,
  })

  const selectedRecipeData = recipesData?.data.find(
    (r) => r.id === selectedRecipe,
  )

  const mutation = useCrudMutation({
    mutationFn: () =>
      ShoppingListsService.addRecipe({
        id: listId,
        recipeId: selectedRecipe,
        servings: servings ? Number(servings) : undefined,
      }),
    successMessage: t("add_recipe_dialog.success"),
    invalidateKeys: ["shopping-lists"],
    onSuccess: () => {
      onOpenChange(false)
      setSelectedRecipe("")
      setServings("")
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("add_recipe_dialog.title")}</DialogTitle>
          <DialogDescription>
            {t("add_recipe_dialog.description")}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div>
            <p className="text-sm font-medium mb-1">
              {t("add_recipe_dialog.recipe_label")}
            </p>
            <Select
              value={selectedRecipe}
              onValueChange={(v) => {
                setSelectedRecipe(v)
                const r = recipesData?.data.find((r) => r.id === v)
                if (r?.servings) setServings(String(r.servings))
              }}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={t("add_recipe_dialog.select_recipe")}
                />
              </SelectTrigger>
              <SelectContent>
                {recipesData?.data.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {selectedRecipe && (
            <div>
              <p className="text-sm font-medium mb-1">
                {t("add_recipe_dialog.servings_label")}
                {selectedRecipeData?.servings && (
                  <span className="text-muted-foreground font-normal ml-1">
                    {t("add_recipe_dialog.recipe_default", {
                      count: selectedRecipeData.servings,
                    })}
                  </span>
                )}
              </p>
              <input
                type="number"
                min={1}
                step={1}
                value={servings}
                onChange={(e) => setServings(e.target.value)}
                placeholder={
                  selectedRecipeData?.servings
                    ? String(selectedRecipeData.servings)
                    : t("add_recipe_dialog.servings_placeholder")
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
          )}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              {tCommon("cancel")}
            </Button>
          </DialogClose>
          <LoadingButton
            onClick={() => mutation.mutate()}
            loading={mutation.isPending}
            disabled={!selectedRecipe}
          >
            {t("add_recipe_dialog.submit")}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

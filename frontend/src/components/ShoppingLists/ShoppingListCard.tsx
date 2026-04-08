import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import {
  CalendarRange,
  ChefHat,
  ExternalLink,
  Pencil,
  Plus,
  ShoppingCart,
  Trash2,
} from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import {
  IngredientsService,
  RecipesService,
  type ShoppingListItemPublic,
  type ShoppingListPublic,
  ShoppingListsService,
} from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
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
import useCustomToast from "@/hooks/useCustomToast"
import { useUnitSystem } from "@/hooks/useUnitSystem"
import { handleError } from "@/utils"

const UNITS = [
  "g",
  "kg",
  "ml",
  "L",
  "piece",
  "tbsp",
  "tsp",
  "cup",
  "oz",
  "lb",
  "bunch",
  "pinch",
  "clove",
  "slice",
  "can",
  "package",
]

interface Props {
  list: ShoppingListPublic
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  })
}

export function ShoppingListCard({ list }: Props) {
  const { t } = useTranslation("shopping")
  const { t: tCommon } = useTranslation("common")
  const { convert } = useUnitSystem()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [addItemOpen, setAddItemOpen] = useState(false)
  const [addRecipeOpen, setAddRecipeOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [renameOpen, setRenameOpen] = useState(false)
  const [selectedIngredient, setSelectedIngredient] = useState("")
  const [quantity, setQuantity] = useState("1")
  const [unit, setUnit] = useState("piece")
  const [selectedRecipe, setSelectedRecipe] = useState("")
  const [servings, setServings] = useState("")
  const [newName, setNewName] = useState(list.name)

  const { data: ingredientsData } = useQuery({
    queryKey: ["ingredients"],
    queryFn: () => IngredientsService.readIngredients({ limit: 500 }),
    enabled: addItemOpen,
  })

  const { data: recipesData } = useQuery({
    queryKey: ["recipes"],
    queryFn: () => RecipesService.readRecipes({ limit: 100 }),
    enabled: addRecipeOpen,
  })

  const selectedRecipeData = recipesData?.data.find(
    (r) => r.id === selectedRecipe,
  )

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["shopping-lists"] })

  const checkMutation = useMutation({
    mutationFn: ({ itemId, checked }: { itemId: string; checked: boolean }) =>
      ShoppingListsService.updateItem({
        id: list.id,
        itemId,
        requestBody: { is_checked: checked },
      }),
    onSettled: invalidate,
  })

  const removeItemMutation = useMutation({
    mutationFn: (itemId: string) =>
      ShoppingListsService.deleteItem({ id: list.id, itemId }),
    onSuccess: () => showSuccessToast(t("item_removed")),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const addItemMutation = useMutation({
    mutationFn: () =>
      ShoppingListsService.addItem({
        id: list.id,
        requestBody: {
          ingredient_id: selectedIngredient,
          quantity: Number(quantity),
          unit: unit as ShoppingListItemPublic["unit"],
        },
      }),
    onSuccess: () => {
      showSuccessToast(t("add_item_dialog.success"))
      setAddItemOpen(false)
      setSelectedIngredient("")
      setQuantity("1")
      setUnit("piece")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const addRecipeMutation = useMutation({
    mutationFn: () =>
      ShoppingListsService.addRecipe({
        id: list.id,
        recipeId: selectedRecipe,
        servings: servings ? Number(servings) : undefined,
      }),
    onSuccess: () => {
      showSuccessToast(t("add_recipe_dialog.success"))
      setAddRecipeOpen(false)
      setSelectedRecipe("")
      setServings("")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const deleteListMutation = useMutation({
    mutationFn: () => ShoppingListsService.deleteShoppingList({ id: list.id }),
    onSuccess: () => showSuccessToast(t("delete_dialog.success")),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const renameMutation = useMutation({
    mutationFn: () =>
      ShoppingListsService.updateShoppingList({
        id: list.id,
        requestBody: { name: newName },
      }),
    onSuccess: () => {
      showSuccessToast(t("rename_dialog.success"))
      setRenameOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const items = list.items ?? []
  const checkedCount = items.filter((i) => i.is_checked).length
  const progress = items.length > 0 ? (checkedCount / items.length) * 100 : 0

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <Link
              to="/shopping-lists/$id"
              params={{ id: list.id }}
              className="text-lg font-semibold hover:underline line-clamp-1"
            >
              {list.name}
            </Link>
            {list.start_date && list.end_date && (
              <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                <CalendarRange className="h-3 w-3" />
                {formatDate(list.start_date)} – {formatDate(list.end_date)}
              </p>
            )}
          </div>
          <div className="flex gap-1 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => {
                setNewName(list.name)
                setRenameOpen(true)
              }}
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-destructive hover:text-destructive"
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <ShoppingCart className="h-3 w-3" />
              {t("card.items_count", { checked: checkedCount, total: items.length })}
            </span>
            {(list.planned_recipes ?? []).length > 0 && (
              <span className="flex items-center gap-1">
                <ChefHat className="h-3 w-3" />
                {t("card.recipes_count", { count: (list.planned_recipes ?? []).length })}
              </span>
            )}
          </div>
          {items.length > 0 && (
            <div className="h-1.5 w-full rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Preview items (up to 4) */}
        <div className="space-y-1">
          {items.slice(0, 4).map((item) => {
            const converted = convert(item.quantity, item.unit)
            return (
              <div key={item.id} className="flex items-center gap-2 group">
                <Checkbox
                  checked={item.is_checked}
                  onCheckedChange={(c) =>
                    checkMutation.mutate({ itemId: item.id, checked: Boolean(c) })
                  }
                />
                <span
                  className={`flex-1 text-sm ${item.is_checked ? "line-through text-muted-foreground" : ""}`}
                >
                  {item.ingredient_name}
                  <span className="text-muted-foreground ml-1">
                    {converted.quantity} {tCommon(`unit_labels.${converted.unit}`, { defaultValue: converted.unit })}
                  </span>
                </span>
                <Badge variant="outline" className="text-xs capitalize">
                  {tCommon(`categories.${item.ingredient_category}`, { defaultValue: item.ingredient_category })}
                </Badge>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 opacity-0 group-hover:opacity-100"
                  onClick={() => removeItemMutation.mutate(item.id)}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            )
          })}
          {items.length > 4 && (
            <Link
              to="/shopping-lists/$id"
              params={{ id: list.id }}
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mt-1"
            >
              <ExternalLink className="h-3 w-3" />
              {t("card.more_items", { count: items.length - 4 })}
            </Link>
          )}
          {items.length === 0 && (
            <p className="text-sm text-muted-foreground italic">{t("card.no_items")}</p>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAddItemOpen(true)}
          >
            <Plus className="mr-1 h-3 w-3" /> {t("card.add_item")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAddRecipeOpen(true)}
          >
            <Plus className="mr-1 h-3 w-3" /> {t("card.add_recipe")}
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to="/shopping-lists/$id" params={{ id: list.id }}>
              <ExternalLink className="mr-1 h-3 w-3" /> {t("card.open")}
            </Link>
          </Button>
        </div>
      </CardContent>

      {/* Add item dialog */}
      <Dialog open={addItemOpen} onOpenChange={setAddItemOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("add_item_dialog.title")}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div>
              <p className="text-sm font-medium mb-1">{t("add_item_dialog.ingredient_label")}</p>
              <Select
                value={selectedIngredient}
                onValueChange={setSelectedIngredient}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t("add_item_dialog.select_ingredient")} />
                </SelectTrigger>
                <SelectContent>
                  {ingredientsData?.data.map((ing) => (
                    <SelectItem key={ing.id} value={ing.id}>
                      {ing.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="text-sm font-medium mb-1">{t("add_item_dialog.quantity_label")}</p>
                <input
                  type="number"
                  min={0.01}
                  step="any"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>
              <div>
                <p className="text-sm font-medium mb-1">{t("add_item_dialog.unit_label")}</p>
                <Select value={unit} onValueChange={setUnit}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {UNITS.map((u) => (
                      <SelectItem key={u} value={u}>
                        {tCommon(`unit_labels.${u}`, { defaultValue: u })}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={addItemMutation.isPending}>
                {tCommon("cancel")}
              </Button>
            </DialogClose>
            <LoadingButton
              onClick={() => addItemMutation.mutate()}
              loading={addItemMutation.isPending}
              disabled={!selectedIngredient}
            >
              {t("add_item_dialog.submit")}
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add recipe dialog */}
      <Dialog open={addRecipeOpen} onOpenChange={setAddRecipeOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("add_recipe_dialog.title")}</DialogTitle>
            <DialogDescription>
              {t("add_recipe_dialog.description")}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div>
              <p className="text-sm font-medium mb-1">{t("add_recipe_dialog.recipe_label")}</p>
              <Select
                value={selectedRecipe}
                onValueChange={(v) => {
                  setSelectedRecipe(v)
                  const r = recipesData?.data.find((r) => r.id === v)
                  if (r?.servings) setServings(String(r.servings))
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t("add_recipe_dialog.select_recipe")} />
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
                      {t("add_recipe_dialog.recipe_default", { count: selectedRecipeData.servings })}
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
                      : "e.g. 4"
                  }
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={addRecipeMutation.isPending}>
                {tCommon("cancel")}
              </Button>
            </DialogClose>
            <LoadingButton
              onClick={() => addRecipeMutation.mutate()}
              loading={addRecipeMutation.isPending}
              disabled={!selectedRecipe}
            >
              {t("add_recipe_dialog.submit")}
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename dialog */}
      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("rename_dialog.title")}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={renameMutation.isPending}>
                {tCommon("cancel")}
              </Button>
            </DialogClose>
            <LoadingButton
              onClick={() => renameMutation.mutate()}
              loading={renameMutation.isPending}
              disabled={!newName.trim()}
            >
              {t("rename_dialog.submit")}
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("delete_dialog.title")}</DialogTitle>
            <DialogDescription>
              {t("delete_dialog.description", { name: list.name })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={deleteListMutation.isPending}>
                {tCommon("cancel")}
              </Button>
            </DialogClose>
            <LoadingButton
              variant="destructive"
              onClick={() => deleteListMutation.mutate()}
              loading={deleteListMutation.isPending}
            >
              {tCommon("delete")}
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

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

import { type ShoppingListPublic, ShoppingListsService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { useCrudMutation } from "@/hooks/useCrudMutation"
import { useUnitSystem } from "@/hooks/useUnitSystem"

import { AddItemDialog } from "./AddItemDialog"
import { AddRecipeDialog } from "./AddRecipeDialog"
import { RenameListDialog } from "./RenameListDialog"

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
  const [addItemOpen, setAddItemOpen] = useState(false)
  const [addRecipeOpen, setAddRecipeOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [renameOpen, setRenameOpen] = useState(false)

  const listsKey = ["shopping-lists"]

  const checkMutation = useCrudMutation({
    mutationFn: ({ itemId, checked }: { itemId: string; checked: boolean }) =>
      ShoppingListsService.updateItem({
        id: list.id,
        itemId,
        requestBody: { is_checked: checked },
      }),
    invalidateKeys: listsKey,
  })

  const removeItemMutation = useCrudMutation({
    mutationFn: (itemId: string) =>
      ShoppingListsService.deleteItem({ id: list.id, itemId }),
    successMessage: t("item_removed"),
    invalidateKeys: listsKey,
  })

  const deleteListMutation = useCrudMutation({
    mutationFn: () => ShoppingListsService.deleteShoppingList({ id: list.id }),
    successMessage: t("delete_dialog.success"),
    invalidateKeys: listsKey,
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
              onClick={() => setRenameOpen(true)}
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
              {t("card.items_count", {
                checked: checkedCount,
                total: items.length,
              })}
            </span>
            {(list.planned_recipes ?? []).length > 0 && (
              <span className="flex items-center gap-1">
                <ChefHat className="h-3 w-3" />
                {t("card.recipes_count", {
                  count: (list.planned_recipes ?? []).length,
                })}
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
                    checkMutation.mutate({
                      itemId: item.id,
                      checked: Boolean(c),
                    })
                  }
                />
                <span
                  className={`flex-1 text-sm ${item.is_checked ? "line-through text-muted-foreground" : ""}`}
                >
                  {item.name}
                  <span className="text-muted-foreground ml-1">
                    {converted.quantity}{" "}
                    {tCommon(`unit_labels.${converted.unit}`, {
                      defaultValue: converted.unit,
                    })}
                  </span>
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
            <p className="text-sm text-muted-foreground italic">
              {t("card.no_items")}
            </p>
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

      <AddItemDialog
        listId={list.id}
        open={addItemOpen}
        onOpenChange={setAddItemOpen}
      />
      <AddRecipeDialog
        listId={list.id}
        open={addRecipeOpen}
        onOpenChange={setAddRecipeOpen}
      />
      <RenameListDialog
        listId={list.id}
        currentName={list.name}
        open={renameOpen}
        onOpenChange={setRenameOpen}
      />
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={t("delete_dialog.title")}
        description={t("delete_dialog.description", { name: list.name })}
        variant="destructive"
        isPending={deleteListMutation.isPending}
        onConfirm={() => deleteListMutation.mutate()}
      />
    </Card>
  )
}

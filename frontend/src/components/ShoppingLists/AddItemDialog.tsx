import { useState } from "react"
import { useTranslation } from "react-i18next"

import { type ShoppingListItemPublic, ShoppingListsService } from "@/client"
import { UnitSelect } from "@/components/Common/UnitSelect"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCrudMutation } from "@/hooks/useCrudMutation"

interface Props {
  listId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AddItemDialog({ listId, open, onOpenChange }: Props) {
  const { t } = useTranslation("shopping")
  const { t: tCommon } = useTranslation("common")
  const [itemName, setItemName] = useState("")
  const [quantity, setQuantity] = useState("1")
  const [unit, setUnit] = useState("piece")

  const mutation = useCrudMutation({
    mutationFn: () =>
      ShoppingListsService.addItem({
        id: listId,
        requestBody: {
          name: itemName.trim(),
          quantity: Number(quantity),
          unit: unit as ShoppingListItemPublic["unit"],
        },
      }),
    successMessage: t("add_item_dialog.success"),
    invalidateKeys: ["shopping-lists"],
    onSuccess: () => {
      onOpenChange(false)
      setItemName("")
      setQuantity("1")
      setUnit("piece")
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("add_item_dialog.title")}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div>
            <p className="text-sm font-medium mb-1">
              {t("add_item_dialog.ingredient_label")}
            </p>
            <input
              type="text"
              value={itemName}
              onChange={(e) => setItemName(e.target.value)}
              placeholder={t("add_item_dialog.item_name_placeholder", {
                defaultValue: "e.g. Toilet paper, Milk…",
              })}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-sm font-medium mb-1">
                {t("add_item_dialog.quantity_label")}
              </p>
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
              <p className="text-sm font-medium mb-1">
                {t("add_item_dialog.unit_label")}
              </p>
              <UnitSelect value={unit} onValueChange={setUnit} />
            </div>
          </div>
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
            disabled={!itemName.trim()}
          >
            {t("add_item_dialog.submit")}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

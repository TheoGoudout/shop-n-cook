import { useState } from "react"
import { useTranslation } from "react-i18next"

import { type ShoppingListItemPublic, ShoppingListsService } from "@/client"
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
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCrudMutation } from "@/hooks/useCrudMutation"

interface Props {
  listId: string
  items: ShoppingListItemPublic[]
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Kept as strings so a field can be cleared while typing. */
type Draft = Record<string, string>

function draftFrom(items: ShoppingListItemPublic[]): Draft {
  return Object.fromEntries(
    items.map((item) => [
      item.id,
      item.quantity_at_home ? String(item.quantity_at_home) : "",
    ]),
  )
}

function parseQuantity(value: string | undefined): number {
  const parsed = Number.parseFloat((value ?? "").replace(",", "."))
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0
}

/**
 * The "check what's at home" step: for each item, how much is already in the
 * cupboard. Quantities are entered in the item's own unit, which is the unit
 * the backend stores them in.
 */
export function PantryCheckDialog({
  listId,
  items,
  open,
  onOpenChange,
}: Props) {
  const { t } = useTranslation("shopping")
  const { t: tCommon } = useTranslation("common")
  const [draft, setDraft] = useState<Draft>(() => draftFrom(items))
  const [wasOpen, setWasOpen] = useState(open)

  // Reset only as the dialog opens, so a background refetch cannot wipe what
  // is being typed.
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) setDraft(draftFrom(items))
  }

  const mutation = useCrudMutation({
    mutationFn: () =>
      ShoppingListsService.pantryCheck({
        id: listId,
        requestBody: {
          items: items.map((item) => ({
            item_id: item.id,
            quantity_at_home: parseQuantity(draft[item.id]),
          })),
        },
      }),
    successMessage: t("pantry.success"),
    invalidateKeys: [["shopping-list", listId], ["shopping-lists"]],
    onSuccess: () => onOpenChange(false),
  })

  const set = (itemId: string, value: string) =>
    setDraft((d) => ({ ...d, [itemId]: value }))

  const unitLabel = (unit: string) =>
    tCommon(`unit_labels.${unit}`, { defaultValue: unit })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("pantry.title")}</DialogTitle>
          <DialogDescription>{t("pantry.description")}</DialogDescription>
        </DialogHeader>
        <div className="max-h-[60vh] overflow-y-auto -mx-1 px-1 divide-y">
          {items.map((item) => {
            const atHome = parseQuantity(draft[item.id])
            const toBuy = Math.max(
              Math.round((item.quantity - atHome) * 100) / 100,
              0,
            )
            return (
              <div
                key={item.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2"
              >
                <div className="flex-1 min-w-[8rem]">
                  <p className="text-sm font-medium">{item.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {t("pantry.needed", {
                      quantity: item.quantity,
                      unit: unitLabel(item.unit),
                    })}
                    {" · "}
                    {toBuy > 0
                      ? t("pantry.to_buy", {
                          quantity: toBuy,
                          unit: unitLabel(item.unit),
                        })
                      : t("pantry.covered")}
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="any"
                    placeholder="0"
                    aria-label={t("pantry.at_home_label", { name: item.name })}
                    value={draft[item.id] ?? ""}
                    onChange={(e) => set(item.id, e.target.value)}
                    className="h-8 w-20 text-right"
                  />
                  <span className="text-xs text-muted-foreground w-12 truncate">
                    {unitLabel(item.unit)}
                  </span>
                  <Button
                    type="button"
                    variant={atHome >= item.quantity ? "secondary" : "outline"}
                    size="sm"
                    className="h-8"
                    onClick={() => set(item.id, String(item.quantity))}
                  >
                    {t("pantry.have_all")}
                  </Button>
                </div>
              </div>
            )
          })}
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
          >
            {t("pantry.submit")}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

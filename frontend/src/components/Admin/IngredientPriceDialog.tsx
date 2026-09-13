import { useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { type IngredientPublic, IngredientsService } from "@/client"
import { UnitSelect } from "@/components/Common/UnitSelect"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCrudMutation } from "@/hooks/useCrudMutation"

/**
 * Edit an ingredient's reference price.
 *
 * The price is entered the way a price is quoted — an amount per a quantity of
 * a unit ("2.50 per 1 kg") — rather than as a normalised price-per-gram, which
 * nobody reads off a shelf. Density and piece weight are the optional bridges
 * that let that price answer a question asked in another dimension: without
 * them, a recipe calling for a cup or a clove is reported as unpriced instead
 * of being guessed at.
 */
export function IngredientPriceDialog({
  ingredient,
  children,
}: {
  ingredient: IngredientPublic
  children: React.ReactNode
}) {
  const { t } = useTranslation("admin")
  const { t: tCommon } = useTranslation("common")
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)

  const [amount, setAmount] = useState(ingredient.price_amount ?? "")
  const [quantity, setQuantity] = useState(
    ingredient.price_quantity != null ? String(ingredient.price_quantity) : "1",
  )
  const [unit, setUnit] = useState(ingredient.price_unit ?? "kg")
  const [density, setDensity] = useState(
    ingredient.density_g_per_ml != null
      ? String(ingredient.density_g_per_ml)
      : "",
  )
  const [pieceWeight, setPieceWeight] = useState(
    ingredient.piece_weight_g != null ? String(ingredient.piece_weight_g) : "",
  )

  const numberOrNull = (value: string) => {
    const trimmed = value.trim()
    if (trimmed === "") return null
    const parsed = Number(trimmed)
    return Number.isFinite(parsed) ? parsed : null
  }

  const mutation = useCrudMutation({
    mutationFn: () =>
      IngredientsService.updateIngredient({
        id: ingredient.id,
        requestBody: {
          price_amount: String(amount).trim() === "" ? null : String(amount),
          price_quantity: numberOrNull(quantity),
          price_unit: String(amount).trim() === "" ? null : unit,
          density_g_per_ml: numberOrNull(density),
          piece_weight_g: numberOrNull(pieceWeight),
        },
      }),
    successMessage: t("ingredient.price_saved"),
    invalidateKeys: [["ingredient-catalog"], ["ingredients"]],
    onSuccess: () => {
      setOpen(false)
      queryClient.invalidateQueries({ queryKey: ["recipes"] })
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("ingredient.price_title")}</DialogTitle>
          <DialogDescription>
            {t("ingredient.price_description", { name: ingredient.name })}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="price-amount">
                {t("ingredient.price_amount")}
              </Label>
              <Input
                id="price-amount"
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="price-quantity">{tCommon("quantity")}</Label>
              <Input
                id="price-quantity"
                type="number"
                min="0"
                step="any"
                inputMode="decimal"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="price-unit">{tCommon("unit")}</Label>
              <UnitSelect
                value={unit}
                onValueChange={(value) => setUnit(value as typeof unit)}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="density">{t("ingredient.density")}</Label>
              <Input
                id="density"
                type="number"
                min="0"
                step="any"
                inputMode="decimal"
                placeholder={t("ingredient.optional")}
                value={density}
                onChange={(e) => setDensity(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                {t("ingredient.density_hint")}
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="piece-weight">
                {t("ingredient.piece_weight")}
              </Label>
              <Input
                id="piece-weight"
                type="number"
                min="0"
                step="any"
                inputMode="decimal"
                placeholder={t("ingredient.optional")}
                value={pieceWeight}
                onChange={(e) => setPieceWeight(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                {t("ingredient.piece_weight_hint")}
              </p>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {tCommon("cancel")}
          </Button>
          <LoadingButton
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {tCommon("save")}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

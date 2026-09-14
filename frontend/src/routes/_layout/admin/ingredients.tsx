import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Combine, Package, Sparkles } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { IngredientsService } from "@/client"
import { IngredientActionsMenu } from "@/components/Admin/IngredientActionsMenu"
import { IngredientPriceDialog } from "@/components/Admin/IngredientPriceDialog"
import { Badge } from "@/components/ui/badge"
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
import useCustomToast from "@/hooks/useCustomToast"
import { APP_NAME } from "@/lib/config"
import { formatMoney } from "@/lib/money"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/admin/ingredients")({
  component: IngredientsPage,
  head: () => ({
    meta: [{ title: `Ingredients - Admin - ${APP_NAME}` }],
  }),
})

/**
 * Fill in prices for every ingredient that has none.
 *
 * Estimates never overwrite a price a human curated, so this is safe to run
 * repeatedly after a bulk recipe import.
 */
function EstimatePricesButton() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { t } = useTranslation("admin")

  const mutation = useMutation({
    mutationFn: () =>
      IngredientsService.estimateIngredientPricesRoute({ requestBody: {} }),
    onSuccess: (data) => {
      showSuccessToast(data.message)
      queryClient.invalidateQueries({ queryKey: ["ingredient-catalog"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <LoadingButton
      variant="outline"
      loading={mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      <Sparkles />
      {t("ingredient.estimate_prices")}
    </LoadingButton>
  )
}

function DeduplicateButton() {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { t } = useTranslation("admin")

  const mutation = useMutation({
    mutationFn: () =>
      IngredientsService.deduplicateIngredients({ dryRun: false }),
    onSuccess: (data) => {
      setOpen(false)
      if (data.removed_count === 0) {
        showSuccessToast(t("ingredient.deduplicate_none"))
      } else {
        showSuccessToast(
          t("ingredient.deduplicate_success", { count: data.removed_count }),
        )
      }
      queryClient.invalidateQueries({ queryKey: ["ingredient-catalog"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Combine />
        {t("ingredient.deduplicate")}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {t("ingredient.deduplicate_confirm_title")}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t("ingredient.deduplicate_confirm_description")}
          </p>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                {t("cancel", { ns: "common" })}
              </Button>
            </DialogClose>
            <LoadingButton
              loading={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {t("ingredient.deduplicate")}
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

function IngredientsTableContent() {
  const { t, i18n } = useTranslation("common")
  const { data } = useQuery({
    queryKey: ["ingredient-catalog"],
    queryFn: () => IngredientsService.readIngredients({}),
  })

  const ingredients = data?.data ?? []

  if (ingredients.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic py-8 text-center">
        {t("ingredients.empty", { ns: "admin" })}
      </p>
    )
  }

  return (
    <div className="border rounded-md">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left font-medium p-3 w-10" />
            <th className="text-left font-medium p-3">{t("name")}</th>
            <th className="text-left font-medium p-3">{t("category")}</th>
            <th className="text-left font-medium p-3">
              {t("ingredient.price_column", { ns: "admin" })}
            </th>
            <th className="text-left font-medium p-3 hidden sm:table-cell">
              {t("ingredient.image_url", { ns: "admin" })}
            </th>
            <th className="p-3 w-12">
              <span className="sr-only">{t("actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {ingredients.map((ingredient) => {
            const categoryKey = ingredient.category ?? "other"
            const amount = formatMoney(
              ingredient.price_amount,
              undefined,
              i18n.language,
            )
            const price =
              amount && ingredient.price_unit
                ? `${amount} / ${ingredient.price_quantity ?? 1} ${t(
                    `unit_labels.${ingredient.price_unit}`,
                    { defaultValue: ingredient.price_unit },
                  )}`
                : null
            return (
              <tr key={ingredient.id} className="border-b last:border-0">
                <td className="p-3">
                  {ingredient.image_url ? (
                    <img
                      src={ingredient.image_url}
                      alt={ingredient.name}
                      className="w-10 h-10 rounded-md object-contain shrink-0 bg-muted p-0.5"
                    />
                  ) : (
                    <div className="w-10 h-10 rounded-md shrink-0 bg-muted flex items-center justify-center">
                      <Package className="h-4 w-4 text-muted-foreground" />
                    </div>
                  )}
                </td>
                <td className="p-3 font-medium">{ingredient.name}</td>
                <td className="p-3">
                  <Badge variant="secondary">
                    {t(`categories.${categoryKey}`, {
                      defaultValue: categoryKey,
                    })}
                  </Badge>
                </td>
                <td className="p-3">
                  <IngredientPriceDialog ingredient={ingredient}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 -ml-2 font-normal tabular-nums"
                      title={t("ingredient.price_edit", { ns: "admin" })}
                    >
                      {price ? (
                        <span
                          className={
                            ingredient.price_source === "estimated"
                              ? "text-muted-foreground"
                              : undefined
                          }
                          title={
                            ingredient.price_source === "estimated"
                              ? t("ingredient.price_estimated", { ns: "admin" })
                              : undefined
                          }
                        >
                          {price}
                          {ingredient.price_source === "estimated" && " ~"}
                        </span>
                      ) : (
                        <span className="text-muted-foreground italic">
                          {t("ingredient.price_none", { ns: "admin" })}
                        </span>
                      )}
                    </Button>
                  </IngredientPriceDialog>
                </td>
                <td className="p-3 hidden sm:table-cell">
                  {ingredient.image_url ? (
                    <a
                      href={ingredient.image_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-muted-foreground hover:text-foreground underline truncate max-w-xs block"
                    >
                      {ingredient.image_url}
                    </a>
                  ) : (
                    <span className="text-xs text-muted-foreground italic">
                      {t("none")}
                    </span>
                  )}
                </td>
                <td className="p-3">
                  <div className="flex justify-end">
                    <IngredientActionsMenu ingredient={ingredient} />
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function IngredientsPage() {
  const { t } = useTranslation("admin")

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("ingredients.title")}
          </h1>
          <p className="text-muted-foreground">{t("ingredients.subtitle")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <EstimatePricesButton />
          <DeduplicateButton />
        </div>
      </div>
      <IngredientsTableContent />
    </div>
  )
}

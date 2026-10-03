import { useQuery } from "@tanstack/react-query"
import { Info } from "lucide-react"
import { useTranslation } from "react-i18next"

import { ShoppingListsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatMoney, isPriced, type Money, toAmount } from "@/lib/money"

/**
 * What this basket costs at each retailer.
 *
 * Stores rarely price the same items, so each store's raw total is not
 * comparable: a store missing a price would look cheaper for it. Stores are
 * ranked on `projected_total` instead, which fills a store's gaps with
 * estimates so every store covers the same items — and every estimate is
 * called out here, as is any item no store prices at all.
 */
export function StoreComparison({ listId }: { listId: string }) {
  const { t } = useTranslation("shopping")
  const { i18n } = useTranslation("common")

  const { data, isLoading } = useQuery({
    queryKey: ["shopping-list", listId, "store-comparison"],
    queryFn: () => ShoppingListsService.compareStores({ id: listId }),
  })

  const entries = data?.data ?? []
  const anyPriced = entries.some((e) => isPriced(e.estimated_total))
  // The backend sorts rankable stores first, cheapest first.
  const ranked = entries.filter((e) => isPriced(e.projected_total))

  if (isLoading) return null

  if (!anyPriced) {
    return (
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm font-medium">
            {t("store_comparison.title")}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <p className="text-sm text-muted-foreground italic">
            {t("store_comparison.empty")}
          </p>
        </CardContent>
      </Card>
    )
  }

  const money = (value: Money, c: string) =>
    formatMoney(value, c, i18n.language)

  const hasEstimates = ranked.some((e) => (e.projected_item_count ?? 0) > 0)
  const canRank = ranked.length >= 2 && !!data?.cheapest_store_id
  const cheapest = canRank ? toAmount(ranked[0].projected_total) : 0
  const dearest = canRank
    ? toAmount(ranked[ranked.length - 1].projected_total)
    : 0
  const spread = dearest - cheapest
  // A bar relative to the most expensive store makes the spread readable at a
  // glance without needing a chart library here.
  const widthOf = (total: number) =>
    dearest > 0 ? Math.max(8, (total / dearest) * 100) : 100

  const itemCount = data?.item_count ?? 0
  const comparableCount = data?.comparable_item_count ?? 0
  const unpriceableCount = data?.unpriceable_item_count ?? 0

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-sm font-medium">
          {t("store_comparison.title")}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {t("store_comparison.description")}
        </p>
      </CardHeader>
      <CardContent className="px-4 pb-4 space-y-2">
        {entries.map((entry) => {
          const rankable = isPriced(entry.projected_total)
          const estimated = entry.projected_item_count ?? 0
          const total = rankable
            ? money(entry.projected_total, entry.currency)
            : money(entry.estimated_total, entry.currency)
          const isCheapest =
            canRank && entry.store_id === data?.cheapest_store_id
          return (
            <div key={entry.store_id} className="space-y-1">
              <div className="flex items-center gap-2 text-sm">
                <span className="flex-1 truncate">{entry.store_name}</span>
                {isCheapest && (
                  <Badge variant="secondary" className="text-xs">
                    {t("store_comparison.cheapest")}
                  </Badge>
                )}
                <span
                  className={
                    rankable
                      ? "tabular-nums font-medium"
                      : "tabular-nums text-muted-foreground"
                  }
                >
                  {total
                    ? estimated > 0
                      ? t("store_comparison.approx", { amount: total })
                      : total
                    : "—"}
                </span>
              </div>
              {rankable && canRank && (
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className={
                      isCheapest ? "h-full bg-primary" : "h-full bg-primary/40"
                    }
                    style={{
                      width: `${widthOf(toAmount(entry.projected_total))}%`,
                    }}
                  />
                </div>
              )}
              {estimated > 0 && (
                <p className="text-xs text-muted-foreground">
                  {t("store_comparison.estimated_items", {
                    count: estimated,
                    actual: money(entry.estimated_total, entry.currency),
                  })}
                </p>
              )}
              {!rankable && isPriced(entry.estimated_total) && (
                <p className="text-xs text-muted-foreground">
                  {t("store_comparison.not_comparable", {
                    count: entry.unpriced_item_count ?? 0,
                  })}
                </p>
              )}
              {!isPriced(entry.estimated_total) && (
                <p className="text-xs text-muted-foreground">
                  {t("store_comparison.no_prices")}
                </p>
              )}
            </div>
          )
        })}
        {canRank && spread > 0 && (
          <p className="text-xs text-muted-foreground pt-1">
            {t(
              hasEstimates
                ? "store_comparison.savings_estimated"
                : "store_comparison.savings",
              { amount: money(spread, ranked[0].currency) },
            )}
          </p>
        )}
        {!canRank && (
          <p className="text-xs text-muted-foreground pt-1">
            {t("store_comparison.cannot_rank")}
          </p>
        )}
        {(hasEstimates || unpriceableCount > 0) && (
          <div className="flex gap-2 rounded-md bg-muted/50 p-2 text-xs text-muted-foreground">
            <Info className="size-3.5 shrink-0 mt-0.5" aria-hidden />
            <div className="space-y-1">
              {hasEstimates && (
                <p>
                  {t("store_comparison.estimate_explained", {
                    count: itemCount,
                    comparable: comparableCount,
                  })}
                </p>
              )}
              {unpriceableCount > 0 && (
                <p>
                  {t("store_comparison.unpriceable", {
                    count: unpriceableCount,
                  })}
                </p>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

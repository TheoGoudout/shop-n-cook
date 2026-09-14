import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"

import { ShoppingListsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatMoney, isPriced, toAmount } from "@/lib/money"

/**
 * What this basket costs at each retailer.
 *
 * The backend costs every store from the same list, so the spread is
 * comparable even where a store falls back to the catalog baseline. Stores
 * that could not be priced at all sort last and show no figure rather than a
 * zero.
 */
export function StoreComparison({ listId }: { listId: string }) {
  const { t } = useTranslation("shopping")
  const { i18n } = useTranslation("common")

  const { data, isLoading } = useQuery({
    queryKey: ["shopping-list", listId, "store-comparison"],
    queryFn: () => ShoppingListsService.compareStores({ id: listId }),
  })

  const entries = data?.data ?? []
  const priced = entries.filter((e) => isPriced(e.estimated_total))

  if (isLoading) return null

  if (priced.length === 0) {
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

  const cheapest = toAmount(priced[0].estimated_total)
  const dearest = toAmount(priced[priced.length - 1].estimated_total)
  const spread = dearest - cheapest
  // A bar relative to the most expensive store makes the spread readable at a
  // glance without needing a chart library here.
  const widthOf = (total: number) =>
    dearest > 0 ? Math.max(8, (total / dearest) * 100) : 100

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
          const total = formatMoney(
            entry.estimated_total,
            entry.currency,
            i18n.language,
          )
          const isCheapest = entry.store_id === data?.cheapest_store_id
          return (
            <div key={entry.store_id} className="space-y-1">
              <div className="flex items-center gap-2 text-sm">
                <span className="flex-1 truncate">{entry.store_name}</span>
                {isCheapest && (
                  <Badge variant="secondary" className="text-xs">
                    {t("store_comparison.cheapest")}
                  </Badge>
                )}
                <span className="tabular-nums font-medium">{total ?? "—"}</span>
              </div>
              {total && (
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className={
                      isCheapest ? "h-full bg-primary" : "h-full bg-primary/40"
                    }
                    style={{
                      width: `${widthOf(toAmount(entry.estimated_total))}%`,
                    }}
                  />
                </div>
              )}
            </div>
          )
        })}
        {spread > 0 && (
          <p className="text-xs text-muted-foreground pt-1">
            {t("store_comparison.savings", {
              amount: formatMoney(spread, priced[0].currency, i18n.language),
            })}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

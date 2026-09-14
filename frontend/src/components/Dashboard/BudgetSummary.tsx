import { useQueries } from "@tanstack/react-query"
import { AlertTriangle, PiggyBank, Receipt, Wallet } from "lucide-react"
import { useTranslation } from "react-i18next"

import { ShoppingListsService, UserSettingsService } from "@/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatMoney, isPriced, toAmount } from "@/lib/money"

/**
 * What the current lists cost, against the household budget.
 *
 * Deliberately not a chart: this is one measure against one threshold, which a
 * hero number and a meter say more clearly than any plot would. Going over
 * budget is a *status*, so it is carried by an icon and a label as well as
 * colour — never colour alone.
 */
export function BudgetSummary() {
  const { t } = useTranslation("dashboard")
  const { i18n } = useTranslation("common")

  const [settingsQuery, listsQuery] = useQueries({
    queries: [
      {
        queryKey: ["user-settings"],
        queryFn: () => UserSettingsService.readUserSettings(),
      },
      {
        queryKey: ["shopping-lists"],
        queryFn: () => ShoppingListsService.readShoppingLists({ limit: 100 }),
      },
    ],
  })

  const settings = settingsQuery.data
  const lists = listsQuery.data?.data ?? []
  const currency = settings?.currency

  // Only unchecked items are still to buy, but the API totals the whole list,
  // so this is "what these lists are worth" rather than "what is left to pay".
  const spend = lists.reduce(
    (sum, list) => sum + toAmount(list.estimated_total),
    0,
  )
  const unpriced = lists.reduce(
    (sum, list) => sum + (list.unpriced_item_count ?? 0),
    0,
  )
  const anyPriced = lists.some((list) => isPriced(list.estimated_total))

  const budget = toAmount(settings?.budget_amount)
  const hasBudget = isPriced(settings?.budget_amount) && budget > 0
  const remaining = budget - spend
  const overBudget = hasBudget && remaining < 0

  // Nothing to say until either a budget or a priced list exists.
  if (!hasBudget && !anyPriced) return null

  const pct = hasBudget ? Math.min(100, (spend / budget) * 100) : 0

  const tiles = [
    {
      key: "budget",
      icon: Wallet,
      label: t("budget.budget"),
      value: hasBudget ? formatMoney(budget, currency, i18n.language) : null,
    },
    {
      key: "spend",
      icon: Receipt,
      label: t("budget.spend"),
      value: anyPriced ? formatMoney(spend, currency, i18n.language) : null,
    },
    {
      key: "remaining",
      icon: PiggyBank,
      label: overBudget ? t("budget.over") : t("budget.remaining"),
      value: hasBudget
        ? formatMoney(Math.abs(remaining), currency, i18n.language)
        : null,
      emphasis: overBudget,
    },
  ]

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{t("budget.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {tiles.map(({ key, icon: Icon, label, value, emphasis }) => (
            <div key={key} className="space-y-1">
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Icon className="h-4 w-4" />
                {label}
              </div>
              <p
                className={`text-2xl font-bold tabular-nums ${
                  emphasis ? "text-destructive" : ""
                }`}
              >
                {value ?? "—"}
              </p>
            </div>
          ))}
        </div>

        {hasBudget && (
          <div className="space-y-1.5">
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className={
                  overBudget
                    ? "h-full bg-destructive"
                    : "h-full bg-[var(--color-chart-1)]"
                }
                style={{ width: `${pct}%` }}
              />
            </div>
            {overBudget && (
              <p className="flex items-center gap-1.5 text-xs text-destructive">
                <AlertTriangle className="h-3 w-3" />
                {t("budget.over_hint")}
              </p>
            )}
          </div>
        )}

        {unpriced > 0 && (
          <p className="text-xs text-muted-foreground">
            {t("budget.unpriced", { count: unpriced })}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

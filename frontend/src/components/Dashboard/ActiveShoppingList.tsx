import { Link } from "@tanstack/react-router"
import { CalendarRange, ShoppingCart } from "lucide-react"
import { useTranslation } from "react-i18next"

import type { ShoppingListsPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

interface Props {
  data: ShoppingListsPublic | undefined
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  })
}

export function ActiveShoppingList({ data }: Props) {
  const { t } = useTranslation("dashboard")
  const { t: tShopping } = useTranslation("shopping")

  if (data !== undefined && data.count === 0) return null

  const list = data?.data[data.data.length - 1]
  const items = list?.items ?? []
  const checkedCount = items.filter((i) => i.is_checked).length
  const progress = items.length > 0 ? (checkedCount / items.length) * 100 : 0
  const plannedCount = list?.planned_recipes?.length ?? 0

  return (
    <Card className="border-l-4 border-l-primary">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShoppingCart className="h-4 w-4" />
            {t("active_list.title")}
          </CardTitle>
        </div>
        {data === undefined || !list ? (
          <div className="space-y-2">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-2 w-full" />
          </div>
        ) : (
          <>
            <Link
              to="/shopping-lists/$id"
              params={{ id: list.id }}
              className="text-sm font-semibold hover:underline line-clamp-1"
            >
              {list.name}
            </Link>
            {list.start_date && list.end_date && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <CalendarRange className="h-3 w-3" />
                {formatDate(list.start_date)} – {formatDate(list.end_date)}
              </p>
            )}
          </>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {data === undefined || !list ? (
          <div className="space-y-2">
            <Skeleton className="h-2 w-full rounded-full" />
            <div className="flex gap-2">
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-5 w-24" />
            </div>
          </div>
        ) : (
          <>
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  {t("active_list.progress", {
                    checked: checkedCount,
                    total: items.length,
                  })}
                </span>
              </div>
              {items.length > 0 ? (
                <div className="h-2 w-full rounded-full bg-secondary overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  {tShopping("card.no_items")}
                </p>
              )}
            </div>

            <div className="flex gap-2 flex-wrap">
              <Badge variant="outline" className="text-xs">
                {tShopping("card.items_count", {
                  checked: checkedCount,
                  total: items.length,
                })}
              </Badge>
              {plannedCount > 0 && (
                <Badge variant="outline" className="text-xs">
                  {tShopping("card.recipes_count", { count: plannedCount })}
                </Badge>
              )}
            </div>

            <div className="flex gap-2 pt-1">
              <Button size="sm" asChild>
                <Link to="/shopping-lists/$id" params={{ id: list.id }}>
                  {t("active_list.open")}
                </Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link to="/shopping-lists">{t("active_list.all_lists")}</Link>
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

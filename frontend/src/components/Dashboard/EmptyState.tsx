import { Link } from "@tanstack/react-router"
import { ChefHat } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"

export function EmptyState() {
  const { t } = useTranslation("dashboard")

  return (
    <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed bg-muted/40 px-8 py-12 text-center">
      <ChefHat className="h-12 w-12 text-primary/60" />
      <div className="space-y-1">
        <h2 className="font-display text-xl font-semibold">
          {t("empty_state.title")}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t("empty_state.subtitle")}
        </p>
      </div>
      <div className="flex gap-3">
        <Button asChild>
          <Link to="/recipes">{t("empty_state.add_recipe")}</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to="/shopping-lists">{t("empty_state.create_list")}</Link>
        </Button>
      </div>
    </div>
  )
}

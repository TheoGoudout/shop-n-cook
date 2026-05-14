import { Link } from "@tanstack/react-router"
import { BookOpen, Download, ListChecks, ShoppingCart } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"

export function QuickActions() {
  const { t } = useTranslation("dashboard")

  const actions = [
    {
      icon: Download,
      label: t("quick_actions.import_recipe"),
      to: "/recipes" as const,
    },
    {
      icon: ShoppingCart,
      label: t("quick_actions.new_list"),
      to: "/shopping-lists" as const,
    },
    {
      icon: BookOpen,
      label: t("quick_actions.browse_recipes"),
      to: "/recipes" as const,
    },
    {
      icon: ListChecks,
      label: t("quick_actions.view_lists"),
      to: "/shopping-lists" as const,
    },
  ]

  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold text-muted-foreground uppercase tracking-wide">
        {t("quick_actions.title")}
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {actions.map(({ icon: Icon, label, to }) => (
          <Button
            key={label}
            variant="outline"
            className="h-auto flex-col gap-2 py-4"
            asChild
          >
            <Link to={to}>
              <Icon className="h-5 w-5 text-muted-foreground" />
              <span className="text-xs font-medium">{label}</span>
            </Link>
          </Button>
        ))}
      </div>
    </div>
  )
}

import { Link } from "@tanstack/react-router"
import { BookOpen, Download, ListChecks, ShoppingCart } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"

export function QuickActions() {
  const { t } = useTranslation("dashboard")

  const actions = [
    {
      icon: Download,
      tone: "var(--tomato)",
      label: t("quick_actions.import_recipe"),
      to: "/recipes" as const,
    },
    {
      icon: ShoppingCart,
      tone: "var(--basil)",
      label: t("quick_actions.new_list"),
      to: "/shopping-lists" as const,
    },
    {
      icon: BookOpen,
      tone: "var(--saffron)",
      label: t("quick_actions.browse_recipes"),
      to: "/recipes" as const,
    },
    {
      icon: ListChecks,
      tone: "var(--plum)",
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
        {actions.map(({ icon: Icon, label, to, tone }) => (
          <Button
            key={label}
            variant="outline"
            className="h-auto flex-col gap-2.5 bg-card py-5 shadow-sm transition-transform hover:-translate-y-0.5 hover:shadow-md"
            asChild
          >
            <Link to={to}>
              <span
                className="flex size-10 items-center justify-center rounded-full"
                style={{
                  color: `color-mix(in oklch, ${tone} 80%, var(--foreground))`,
                  backgroundColor: `color-mix(in oklch, ${tone} 22%, transparent)`,
                }}
              >
                <Icon className="h-5 w-5" />
              </span>
              <span className="text-sm font-semibold">{label}</span>
            </Link>
          </Button>
        ))}
      </div>
    </div>
  )
}

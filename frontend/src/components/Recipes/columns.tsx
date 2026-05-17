import { Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Globe } from "lucide-react"
import { useTranslation } from "react-i18next"

import type { RecipePublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { RecipeActionsMenu } from "./RecipeActionsMenu"

export const useColumns = (): ColumnDef<RecipePublic>[] => {
  const { t } = useTranslation("recipes")

  return [
    {
      accessorKey: "title",
      header: t("columns.title"),
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <Link
            to="/recipes/$id"
            params={{ id: row.original.id }}
            className="font-medium hover:underline"
          >
            {row.original.title}
          </Link>
          {row.original.is_public && (
            <Badge variant="secondary" className="gap-1 text-xs">
              <Globe className="h-3 w-3" />
              {t("columns.public")}
            </Badge>
          )}
        </div>
      ),
    },
    {
      accessorKey: "description",
      header: t("columns.description"),
      cell: ({ row }) => {
        const desc = row.original.description
        return (
          <span
            className={cn(
              "max-w-xs truncate block text-muted-foreground",
              !desc && "italic",
            )}
          >
            {desc || t("columns.no_description")}
          </span>
        )
      },
    },
    {
      accessorKey: "servings",
      header: t("columns.servings"),
      cell: ({ row }) => <span>{row.original.servings ?? "—"}</span>,
    },
    {
      id: "time",
      header: t("columns.time"),
      cell: ({ row }) => {
        const prep = row.original.prep_time_minutes
        const cook = row.original.cook_time_minutes
        const total = (prep ?? 0) + (cook ?? 0)
        return (
          <span>
            {total > 0 ? t("columns.minutes", { count: total }) : "—"}
          </span>
        )
      },
    },
    {
      id: "ingredients",
      header: t("columns.ingredients"),
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {t("columns.ingredient_count", {
            count: (row.original.ingredients ?? []).length,
          })}
        </span>
      ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <RecipeActionsMenu recipe={row.original} />
        </div>
      ),
    },
  ]
}

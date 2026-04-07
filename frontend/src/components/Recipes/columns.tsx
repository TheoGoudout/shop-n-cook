import { Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"

import type { RecipePublic } from "@/client"
import { cn } from "@/lib/utils"
import { RecipeActionsMenu } from "./RecipeActionsMenu"

export const columns: ColumnDef<RecipePublic>[] = [
  {
    accessorKey: "title",
    header: "Title",
    cell: ({ row }) => (
      <Link
        to="/recipes/$id"
        params={{ id: row.original.id }}
        className="font-medium hover:underline"
      >
        {row.original.title}
      </Link>
    ),
  },
  {
    accessorKey: "description",
    header: "Description",
    cell: ({ row }) => {
      const desc = row.original.description
      return (
        <span
          className={cn(
            "max-w-xs truncate block text-muted-foreground",
            !desc && "italic",
          )}
        >
          {desc || "No description"}
        </span>
      )
    },
  },
  {
    accessorKey: "servings",
    header: "Servings",
    cell: ({ row }) => <span>{row.original.servings ?? "—"}</span>,
  },
  {
    id: "time",
    header: "Time",
    cell: ({ row }) => {
      const prep = row.original.prep_time_minutes
      const cook = row.original.cook_time_minutes
      const total = (prep ?? 0) + (cook ?? 0)
      return <span>{total > 0 ? `${total} min` : "—"}</span>
    },
  },
  {
    id: "ingredients",
    header: "Ingredients",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {(row.original.ingredients ?? []).length} items
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

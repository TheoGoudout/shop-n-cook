import type { ColumnDef } from "@tanstack/react-table"

import type { IngredientPublic } from "@/client"
import useAuth from "@/hooks/useAuth"
import { IngredientActionsMenu } from "./IngredientActionsMenu"

export const useColumns = (): ColumnDef<IngredientPublic>[] => {
  const { user } = useAuth()

  return [
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <span className="font-medium">{row.original.name}</span>
      ),
    },
    {
      accessorKey: "category",
      header: "Category",
      cell: ({ row }) => (
        <span className="capitalize">{row.original.category}</span>
      ),
    },
    {
      accessorKey: "default_unit",
      header: "Default Unit",
      cell: ({ row }) => <span>{row.original.default_unit}</span>,
    },
    ...(user?.is_superuser
      ? [
          {
            id: "actions",
            header: () => <span className="sr-only">Actions</span>,
            cell: ({ row }: { row: { original: IngredientPublic } }) => (
              <div className="flex justify-end">
                <IngredientActionsMenu ingredient={row.original} />
              </div>
            ),
          } satisfies ColumnDef<IngredientPublic>,
        ]
      : []),
  ]
}

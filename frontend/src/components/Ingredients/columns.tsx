import type { ColumnDef } from "@tanstack/react-table"
import { useTranslation } from "react-i18next"

import type { IngredientPublic } from "@/client"
import useAuth from "@/hooks/useAuth"
import { IngredientActionsMenu } from "./IngredientActionsMenu"

function CategoryCell({ category }: { category: string }) {
  const { t } = useTranslation("common")
  return (
    <span className="capitalize">
      {t(`categories.${category}`, { defaultValue: category })}
    </span>
  )
}

function UnitCell({ unit }: { unit: string }) {
  const { t } = useTranslation("common")
  return <span>{t(`unit_labels.${unit}`, { defaultValue: unit })}</span>
}

export const useColumns = (): ColumnDef<IngredientPublic>[] => {
  const { t } = useTranslation("ingredients")
  const { user } = useAuth()

  return [
    {
      accessorKey: "name",
      header: t("columns.name"),
      cell: ({ row }) => (
        <span className="font-medium">{row.original.name}</span>
      ),
    },
    {
      accessorKey: "category",
      header: t("columns.category"),
      cell: ({ row }) => <CategoryCell category={row.original.category as string} />,
    },
    {
      accessorKey: "default_unit",
      header: t("columns.default_unit"),
      cell: ({ row }) => <UnitCell unit={row.original.default_unit as string} />,
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

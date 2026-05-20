import type { ColumnDef } from "@tanstack/react-table"
import { useTranslation } from "react-i18next"

import type { UserPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { UserActionsMenu } from "./UserActionsMenu"

export type UserTableData = UserPublic & {
  isCurrentUser: boolean
}

export function useUserColumns(): ColumnDef<UserTableData>[] {
  const { t } = useTranslation("admin")

  return [
    {
      accessorKey: "full_name",
      header: t("columns.full_name"),
      cell: ({ row }) => {
        const fullName = row.original.full_name
        return (
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "font-medium",
                !fullName && "text-muted-foreground",
              )}
            >
              {fullName || t("columns.na")}
            </span>
            {row.original.isCurrentUser && (
              <Badge variant="outline" className="text-xs">
                {t("columns.you")}
              </Badge>
            )}
          </div>
        )
      },
    },
    {
      accessorKey: "email",
      header: t("columns.email"),
      cell: ({ row }) => (
        <span className="text-muted-foreground">{row.original.email}</span>
      ),
    },
    {
      accessorKey: "is_superuser",
      header: t("columns.role"),
      cell: ({ row }) => (
        <Badge variant={row.original.is_superuser ? "default" : "secondary"}>
          {row.original.is_superuser
            ? t("columns.superuser")
            : t("columns.user_role")}
        </Badge>
      ),
    },
    {
      accessorKey: "is_active",
      header: t("columns.status"),
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "size-2 rounded-full",
              row.original.is_active ? "bg-primary" : "bg-muted-foreground/40",
            )}
          />
          <span
            className={row.original.is_active ? "" : "text-muted-foreground"}
          >
            {row.original.is_active
              ? t("columns.active")
              : t("columns.inactive")}
          </span>
        </div>
      ),
    },
    {
      id: "actions",
      header: () => (
        <span className="sr-only">{t("actions", { ns: "common" })}</span>
      ),
      cell: ({ row }) => (
        <div className="flex justify-end">
          <UserActionsMenu user={row.original} />
        </div>
      ),
    },
  ]
}

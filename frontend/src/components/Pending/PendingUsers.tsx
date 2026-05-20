import { useTranslation } from "react-i18next"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const PendingUsers = () => {
  const { t } = useTranslation("admin")

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("columns.full_name")}</TableHead>
          <TableHead>{t("columns.email")}</TableHead>
          <TableHead>{t("columns.role")}</TableHead>
          <TableHead>{t("columns.status")}</TableHead>
          <TableHead>
            <span className="sr-only">{t("actions", { ns: "common" })}</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: 5 }).map((_, index) => (
          <TableRow key={index}>
            <TableCell>
              <Skeleton className="h-4 w-32" />
            </TableCell>
            <TableCell>
              <Skeleton className="h-4 w-40" />
            </TableCell>
            <TableCell>
              <Skeleton className="h-5 w-20 rounded-full" />
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <Skeleton className="size-2 rounded-full" />
                <Skeleton className="h-4 w-12" />
              </div>
            </TableCell>
            <TableCell>
              <div className="flex justify-end">
                <Skeleton className="size-8 rounded-md" />
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export default PendingUsers

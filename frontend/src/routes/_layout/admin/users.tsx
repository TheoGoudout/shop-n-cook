import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"
import { type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { type UserTableData, useUserColumns } from "@/components/Admin/columns"
import { DataTable } from "@/components/Common/DataTable"
import { PageHeader } from "@/components/Common/PageHeader"
import PendingUsers from "@/components/Pending/PendingUsers"
import useAuth from "@/hooks/useAuth"
import { APP_NAME } from "@/lib/config"

function getUsersQueryOptions() {
  return {
    queryFn: () => UsersService.readUsers({ skip: 0, limit: 100 }),
    queryKey: ["users"],
  }
}

export const Route = createFileRoute("/_layout/admin/users")({
  component: UsersPage,
  head: () => ({
    meta: [{ title: `Users - Admin - ${APP_NAME}` }],
  }),
})

function UsersTableContent() {
  const { user: currentUser } = useAuth()
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())
  const columns = useUserColumns()

  const tableData: UserTableData[] = users.data.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return <DataTable columns={columns} data={tableData} />
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function UsersPage() {
  const { t } = useTranslation("admin")

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("users.title")} subtitle={t("users.subtitle")}>
        <AddUser />
      </PageHeader>
      <UsersTable />
    </div>
  )
}

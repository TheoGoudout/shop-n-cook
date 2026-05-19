import { useQuery, useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Package } from "lucide-react"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"

import { IngredientsService, type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { IngredientActionsMenu } from "@/components/Admin/IngredientActionsMenu"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"
import { APP_NAME } from "@/lib/config"

function getUsersQueryOptions() {
  return {
    queryFn: () => UsersService.readUsers({ skip: 0, limit: 100 }),
    queryKey: ["users"],
  }
}

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: `Admin - ${APP_NAME}`,
      },
    ],
  }),
})

function UsersTableContent() {
  const { user: currentUser } = useAuth()
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())

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

function IngredientsTableContent() {
  const { t } = useTranslation("common")
  const { data } = useQuery({
    queryKey: ["ingredient-catalog"],
    queryFn: () => IngredientsService.readIngredients({}),
  })

  const ingredients = data?.data ?? []

  if (ingredients.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic py-8 text-center">
        No ingredients in the catalog yet.
      </p>
    )
  }

  return (
    <div className="border rounded-md">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left font-medium p-3 w-10" />
            <th className="text-left font-medium p-3">{t("name")}</th>
            <th className="text-left font-medium p-3">{t("category")}</th>
            <th className="text-left font-medium p-3 hidden sm:table-cell">
              Image URL
            </th>
            <th className="p-3 w-12">
              <span className="sr-only">{t("actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {ingredients.map((ingredient) => {
            const categoryKey = ingredient.category ?? "other"
            return (
              <tr key={ingredient.id} className="border-b last:border-0">
                <td className="p-3">
                  {ingredient.image_url ? (
                    <img
                      src={ingredient.image_url}
                      alt={ingredient.name}
                      className="w-8 h-8 rounded object-cover"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded bg-muted flex items-center justify-center">
                      <Package className="h-4 w-4 text-muted-foreground" />
                    </div>
                  )}
                </td>
                <td className="p-3 font-medium">{ingredient.name}</td>
                <td className="p-3">
                  <Badge variant="secondary">
                    {t(`categories.${categoryKey}`, {
                      defaultValue: categoryKey,
                    })}
                  </Badge>
                </td>
                <td className="p-3 hidden sm:table-cell">
                  {ingredient.image_url ? (
                    <a
                      href={ingredient.image_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-muted-foreground hover:text-foreground underline truncate max-w-xs block"
                    >
                      {ingredient.image_url}
                    </a>
                  ) : (
                    <span className="text-xs text-muted-foreground italic">
                      None
                    </span>
                  )}
                </td>
                <td className="p-3">
                  <div className="flex justify-end">
                    <IngredientActionsMenu ingredient={ingredient} />
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Admin() {
  const { t } = useTranslation("admin")

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("page.title")}</h1>
        <p className="text-muted-foreground">{t("page.subtitle")}</p>
      </div>

      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="ingredients">Ingredients</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="mt-4">
          <div className="flex justify-end mb-4">
            <AddUser />
          </div>
          <UsersTable />
        </TabsContent>

        <TabsContent value="ingredients" className="mt-4">
          <IngredientsTableContent />
        </TabsContent>
      </Tabs>
    </div>
  )
}

import { createFileRoute, Outlet, redirect, useLocation, useNavigate } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { APP_NAME } from "@/lib/config"

export const Route = createFileRoute("/_layout/admin")({
  component: AdminLayout,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [{ title: `Admin - ${APP_NAME}` }],
  }),
})

function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const activeTab = location.pathname.endsWith("ingredients")
    ? "ingredients"
    : "users"

  return (
    <div className="flex flex-col gap-6">
      <Tabs
        value={activeTab}
        onValueChange={(val) => navigate({ to: `/admin/${val}` })}
      >
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="ingredients">Ingredients</TabsTrigger>
        </TabsList>
        <div className="mt-4">
          <Outlet />
        </div>
      </Tabs>
    </div>
  )
}

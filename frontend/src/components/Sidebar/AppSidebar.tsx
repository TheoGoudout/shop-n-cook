import { ChefHat, FlaskConical, Home, ShoppingCart, Users } from "lucide-react"
import { useTranslation } from "react-i18next"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

export function AppSidebar() {
  const { t } = useTranslation("navigation")
  const { user: currentUser } = useAuth()

  const baseItems: Item[] = [
    { icon: Home, title: t("dashboard"), path: "/" },
    { icon: FlaskConical, title: t("ingredients"), path: "/ingredients" },
    { icon: ChefHat, title: t("recipes"), path: "/recipes" },
    { icon: ShoppingCart, title: t("shopping_lists"), path: "/shopping-lists" },
  ]

  const items = currentUser?.is_superuser
    ? [...baseItems, { icon: Users, title: t("admin"), path: "/admin" }]
    : baseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar

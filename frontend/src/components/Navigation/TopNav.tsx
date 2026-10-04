import { Link, useRouterState } from "@tanstack/react-router"
import {
  CalendarDays,
  ChefHat,
  Globe,
  Home,
  type LucideIcon,
  ShoppingCart,
  Users,
} from "lucide-react"
import { useTranslation } from "react-i18next"

import { Appearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import useAuth from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import { UserMenu } from "./UserMenu"

type NavItem = {
  icon: LucideIcon
  title: string
  path: string
}

function useNavItems(): NavItem[] {
  const { t } = useTranslation("navigation")
  const { user } = useAuth()

  const items: NavItem[] = [
    { icon: Home, title: t("dashboard"), path: "/" },
    { icon: ChefHat, title: t("recipes"), path: "/recipes" },
    { icon: Globe, title: t("community"), path: "/recipes/public" },
    { icon: CalendarDays, title: t("meal_plans"), path: "/meal-plans" },
    { icon: ShoppingCart, title: t("shopping_lists"), path: "/shopping-lists" },
  ]
  return user?.is_superuser
    ? [...items, { icon: Users, title: t("admin"), path: "/admin" }]
    : items
}

/** The item owning the current path: the longest path that prefixes it. */
function useActivePath(items: NavItem[]): string | undefined {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  return items
    .filter(
      (item) =>
        pathname === item.path ||
        (item.path !== "/" && pathname.startsWith(`${item.path}/`)),
    )
    .sort((a, b) => b.path.length - a.path.length)[0]?.path
}

/**
 * The app's header: logo, the sections as pills, and the theme and account
 * menus. On small screens the sections move to a tab bar at the bottom of
 * the screen, where a thumb can reach them.
 */
export function TopNav() {
  const items = useNavItems()
  const active = useActivePath(items)

  return (
    <>
      <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 md:px-6">
          <Logo variant="full" className="shrink-0 [&_span]:text-lg" />
          <nav className="hidden flex-1 items-center gap-1 md:flex">
            {items.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center gap-2 rounded-full px-3.5 py-2 text-sm font-medium transition-colors",
                  item.path === active
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-secondary hover:text-secondary-foreground",
                )}
              >
                <item.icon className="size-4" />
                {item.title}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Appearance />
            <UserMenu />
          </div>
        </div>
      </header>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {items.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={cn(
              "flex flex-1 flex-col items-center gap-1 py-2 text-[0.6875rem] font-medium",
              item.path === active ? "text-primary" : "text-muted-foreground",
            )}
          >
            <item.icon className="size-5" />
            <span className="max-w-full truncate px-1">{item.title}</span>
          </Link>
        ))}
      </nav>
    </>
  )
}

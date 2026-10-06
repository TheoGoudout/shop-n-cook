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
  /** A shorter label for the narrow cells of the mobile tab bar. */
  shortTitle: string
  path: string
}

function useNavItems(): NavItem[] {
  const { t } = useTranslation("navigation")
  const { user } = useAuth()

  const item = (icon: LucideIcon, key: string, path: string): NavItem => ({
    icon,
    title: t(key),
    shortTitle: t(`short.${key}`),
    path,
  })

  const items: NavItem[] = [
    item(Home, "dashboard", "/"),
    item(ChefHat, "recipes", "/recipes"),
    item(Globe, "community", "/recipes/public"),
    item(CalendarDays, "meal_plans", "/meal-plans"),
    item(ShoppingCart, "shopping_lists", "/shopping-lists"),
  ]
  return user?.is_superuser ? [...items, item(Users, "admin", "/admin")] : items
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
      <nav className="fixed inset-x-0 bottom-0 z-30 grid auto-cols-[minmax(0,1fr)] grid-flow-col border-t bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {items.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            aria-label={item.title}
            className={cn(
              "flex min-w-0 flex-col items-center gap-1 py-2 text-[0.6875rem] font-medium",
              item.path === active ? "text-primary" : "text-muted-foreground",
            )}
          >
            <item.icon className="size-5" />
            <span className="max-w-full truncate px-0.5">
              {item.shortTitle}
            </span>
          </Link>
        ))}
      </nav>
    </>
  )
}

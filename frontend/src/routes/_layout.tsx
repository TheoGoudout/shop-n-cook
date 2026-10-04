import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"

import { Footer } from "@/components/Common/Footer"
import { TopNav } from "@/components/Navigation/TopNav"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async ({ location }) => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
        search: { redirect: location.href },
      })
    }
  },
})

function Layout() {
  return (
    <div className="bg-kitchen-glow flex min-h-svh flex-col">
      <TopNav />
      {/* pb-24 keeps the last row clear of the mobile tab bar */}
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-8 pb-24 md:px-6 md:pb-12">
        <Outlet />
      </main>
      <div className="hidden md:block">
        <Footer />
      </div>
    </div>
  )
}

export default Layout

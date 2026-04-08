import { createFileRoute } from "@tanstack/react-router"
import { useTranslation } from "react-i18next"

import { StatsChart } from "@/components/Dashboard/StatsChart"
import { APP_NAME } from "@/lib/config"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: `Dashboard - ${APP_NAME}`,
      },
    ],
  }),
})

function Dashboard() {
  const { t } = useTranslation("dashboard")
  const { user: currentUser } = useAuth()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight truncate max-w-sm">
          {t("greeting", { name: currentUser?.full_name || currentUser?.email })}
        </h1>
        <p className="text-muted-foreground">
          {t("welcome")}
        </p>
      </div>
      <StatsChart />
    </div>
  )
}

import { createFileRoute } from "@tanstack/react-router"
import { useTranslation } from "react-i18next"

import { APP_NAME } from "@/lib/config"

import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import { HouseholdSettings } from "@/components/UserSettings/HouseholdSettings"
import UserInformation from "@/components/UserSettings/UserInformation"
import { AppPreferences } from "@/components/UserSettings/AppPreferences"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  head: () => ({
    meta: [{ title: `Settings - ${APP_NAME}` }],
  }),
})

function UserSettings() {
  const { t } = useTranslation("settings")
  const { user: currentUser } = useAuth()

  if (!currentUser) {
    return null
  }

  const tabsConfig = [
    { value: "my-profile", title: t("tabs.my_profile"), component: UserInformation },
    { value: "household", title: t("tabs.household"), component: HouseholdSettings },
    { value: "preferences", title: t("tabs.preferences"), component: AppPreferences },
    { value: "password", title: t("tabs.password"), component: ChangePassword },
    { value: "danger-zone", title: t("tabs.danger_zone"), component: DeleteAccount },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("page.title")}</h1>
        <p className="text-muted-foreground">
          {t("page.subtitle")}
        </p>
      </div>

      <Tabs defaultValue="my-profile">
        <TabsList>
          {tabsConfig.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.title}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabsConfig.map((tab) => (
          <TabsContent key={tab.value} value={tab.value}>
            <tab.component />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}

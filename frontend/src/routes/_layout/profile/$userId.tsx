import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { SearchInput } from "@/components/Common/SearchInput"
import { RecipeResults } from "@/components/Recipes/RecipeResults"
import { useRecipeSearch } from "@/components/Recipes/useRecipeSearch"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { APP_NAME } from "@/lib/config"

export const Route = createFileRoute("/_layout/profile/$userId")({
  component: UserProfile,
  head: () => ({
    meta: [{ title: `Profile - ${APP_NAME}` }],
  }),
})

function UserProfile() {
  const { t } = useTranslation("recipes")
  const { userId } = Route.useParams()
  const [search, setSearch] = useState("")
  const { data, isLoading, isFiltered } = useRecipeSearch({
    scope: "public",
    search,
    ownerId: userId,
  })

  const displayName = data?.data[0]?.owner_name ?? t("profile.unknown_user")

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link to="/recipes/public">
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t("profile.back")}
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-32" />
        </div>
      ) : (
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{displayName}</h1>
          {data && (
            <p className="text-muted-foreground">
              {t("profile.recipe_count", { count: data.count })}
            </p>
          )}
        </div>
      )}

      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder={t("public.search_placeholder")}
      />
      <RecipeResults
        data={data}
        isLoading={isLoading}
        isFiltered={isFiltered}
        emptyTitle={t("profile.empty_title")}
        emptySubtitle={t("profile.empty_subtitle")}
        community
      />
    </div>
  )
}

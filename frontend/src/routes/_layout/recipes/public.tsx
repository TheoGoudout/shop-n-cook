import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { PageHeader } from "@/components/Common/PageHeader"

import { SearchInput } from "@/components/Common/SearchInput"
import {
  defaultFilters,
  RecipeFilterBar,
  type RecipeFilters,
} from "@/components/Recipes/RecipeFilterBar"
import { RecipeResults } from "@/components/Recipes/RecipeResults"
import { useRecipeSearch } from "@/components/Recipes/useRecipeSearch"
import { Badge } from "@/components/ui/badge"
import { APP_NAME } from "@/lib/config"

export const Route = createFileRoute("/_layout/recipes/public")({
  component: PublicRecipes,
  head: () => ({
    meta: [{ title: `Community Recipes - ${APP_NAME}` }],
  }),
})

function PublicRecipes() {
  const { t } = useTranslation("recipes")
  const [search, setSearch] = useState("")
  const [filters, setFilters] = useState<RecipeFilters>(defaultFilters)
  const { data, isLoading, isFiltered } = useRecipeSearch({
    scope: "public",
    search,
    filters,
  })

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("public.title")} subtitle={t("public.subtitle")} />
      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder={t("public.search_placeholder")}
      />
      <RecipeFilterBar
        filters={filters}
        onChange={setFilters}
        onClear={() => setFilters(defaultFilters)}
      />
      {data && data.count > 0 && (
        <Badge variant="secondary" className="w-fit">
          {t("public.recipe_count", { count: data.count })}
        </Badge>
      )}
      <RecipeResults
        data={data}
        isLoading={isLoading}
        isFiltered={isFiltered}
        emptyTitle={t("public.empty_title")}
        emptySubtitle={t("public.empty_subtitle")}
        community
      />
    </div>
  )
}

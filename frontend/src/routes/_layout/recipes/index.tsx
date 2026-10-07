import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { PageHeader } from "@/components/Common/PageHeader"

import { SearchInput } from "@/components/Common/SearchInput"
import AddRecipe from "@/components/Recipes/AddRecipe"
import {
  defaultFilters,
  RecipeFilterBar,
  type RecipeFilters,
} from "@/components/Recipes/RecipeFilterBar"
import { RecipeResults } from "@/components/Recipes/RecipeResults"
import { useRecipeSearch } from "@/components/Recipes/useRecipeSearch"
import { APP_NAME } from "@/lib/config"

export const Route = createFileRoute("/_layout/recipes/")({
  component: Recipes,
  head: () => ({
    meta: [{ title: `Recipes - ${APP_NAME}` }],
  }),
})

function Recipes() {
  const { t } = useTranslation("recipes")
  const [search, setSearch] = useState("")
  const [filters, setFilters] = useState<RecipeFilters>(defaultFilters)
  const { data, isLoading, isFiltered } = useRecipeSearch({
    scope: "mine",
    search,
    filters,
  })

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("page.title")} subtitle={t("page.subtitle")}>
        <AddRecipe />
      </PageHeader>
      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder={t("page.search_placeholder")}
      />
      <RecipeFilterBar
        filters={filters}
        onChange={setFilters}
        onClear={() => setFilters(defaultFilters)}
      />
      <RecipeResults
        data={data}
        isLoading={isLoading}
        isFiltered={isFiltered}
        emptyTitle={t("page.empty_title")}
        emptySubtitle={t("page.empty_subtitle")}
      />
    </div>
  )
}

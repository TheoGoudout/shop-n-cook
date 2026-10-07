import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { RecipesService } from "@/client"
import {
  defaultFilters,
  type RecipeFilters,
  recipeFilterParams,
} from "@/components/Recipes/RecipeFilterBar"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"

const PAGE_SIZE = 100

/**
 * Recipes matching a search box and the filter bar, searched on the server so
 * that every recipe can be found, not only the first page.
 *
 * `mine` lists the user's own recipes (under the `["recipes"]` key every
 * recipe mutation invalidates); `public` lists the community's, optionally
 * one author's.
 */
export function useRecipeSearch({
  scope,
  search,
  filters = defaultFilters,
  ownerId,
}: {
  scope: "mine" | "public"
  search: string
  filters?: RecipeFilters
  ownerId?: string
}) {
  const debouncedSearch = useDebouncedValue(search)
  const debouncedFilters = useDebouncedValue(filters)
  const filterParams = recipeFilterParams(debouncedFilters)
  const params = {
    search: debouncedSearch.trim() || null,
    ...filterParams,
    limit: PAGE_SIZE,
  }
  const query = useQuery({
    queryKey:
      scope === "mine"
        ? ["recipes", "search", params]
        : ["public-recipes", ownerId ?? null, params],
    queryFn: () =>
      scope === "mine"
        ? RecipesService.readRecipes(params)
        : RecipesService.readPublicRecipes({ ...params, ownerId }),
    // Keep the last results on screen while the next search loads.
    placeholderData: keepPreviousData,
  })
  const isFiltered =
    params.search !== null ||
    Object.values(filterParams).some((value) => value !== null)
  return { ...query, isFiltered }
}

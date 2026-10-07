import { ChefHat } from "lucide-react"

import type { RecipesPublic } from "@/client"
import { EmptyListState } from "@/components/Common/EmptyListState"
import { RecipeGrid } from "@/components/Recipes/RecipeGrid"
import { Skeleton } from "@/components/ui/skeleton"

/**
 * The grid under a recipe search: placeholders while loading, a welcome when
 * there is nothing at all, and "no results" when only the search is empty.
 */
export function RecipeResults({
  data,
  isLoading,
  isFiltered,
  emptyTitle,
  emptySubtitle,
  community = false,
}: {
  data: RecipesPublic | undefined
  isLoading: boolean
  isFiltered: boolean
  emptyTitle: string
  emptySubtitle: string
  community?: boolean
}) {
  if (isLoading) {
    return (
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-80 rounded-2xl" />
        ))}
      </div>
    )
  }
  if (!isFiltered && (data?.count ?? 0) === 0) {
    return (
      <EmptyListState
        icon={ChefHat}
        title={emptyTitle}
        subtitle={emptySubtitle}
      />
    )
  }
  return <RecipeGrid recipes={data?.data ?? []} community={community} />
}

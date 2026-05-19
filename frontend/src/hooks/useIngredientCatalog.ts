import { useQuery } from "@tanstack/react-query"
import { useMemo } from "react"

import { type IngredientPublic, IngredientsService } from "@/client"

export function useIngredientCatalog(): Map<string, IngredientPublic> {
  const { data } = useQuery({
    queryKey: ["ingredient-catalog"],
    queryFn: () => IngredientsService.readIngredients({}),
    staleTime: 5 * 60 * 1000,
  })
  return useMemo(() => {
    const map = new Map<string, IngredientPublic>()
    for (const ing of data?.data ?? []) {
      map.set(ing.name.toLowerCase(), ing)
    }
    return map
  }, [data])
}

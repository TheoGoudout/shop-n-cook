import { useMutation } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { ChefHat } from "lucide-react"
import { useEffect, useRef } from "react"
import { useTranslation } from "react-i18next"
import { z } from "zod"

import { RecipesService } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import i18n from "@/i18n"

function extractRecipeUrl(params: {
  url?: string
  text?: string
}): string | null {
  if (params.url?.startsWith("http")) return params.url
  const match = params.text?.match(/https?:\/\/[^\s]+/)
  return match?.[0] ?? null
}

export const Route = createFileRoute("/_layout/share-target")({
  component: ShareTargetPage,
  validateSearch: z.object({
    url: z.string().optional(),
    text: z.string().optional(),
    title: z.string().optional(),
  }),
})

function ShareTargetPage() {
  const { url, text } = Route.useSearch()
  const navigate = useNavigate()
  const { t } = useTranslation("recipes")
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const hasTriggered = useRef(false)

  const importMutation = useMutation({
    mutationFn: async (targetUrl: string) => {
      const parsed = await RecipesService.importRecipeUrl({
        requestBody: { url: targetUrl, language: i18n.language },
      })
      return RecipesService.createRecipe({
        requestBody: {
          title: parsed.title,
          description: parsed.description ?? null,
          servings: parsed.servings ?? null,
          prep_time_minutes: parsed.prep_time_minutes ?? null,
          cook_time_minutes: parsed.cook_time_minutes ?? null,
          source_url: parsed.source_url ?? null,
          image_url: parsed.image_url ?? null,
          ingredients: (parsed.ingredients ?? []).map((ing) => ({
            ingredient_name: ing.name,
            ingredient_category: ing.category,
            ingredient_default_unit: ing.unit,
            quantity: ing.quantity,
            unit: ing.unit,
            notes: ing.notes ?? null,
          })),
          steps: (parsed.steps ?? []).map((step, i) => ({
            step_number: i + 1,
            instruction: step.instruction,
            ingredient_indices: (step.ingredient_names ?? [])
              .map((name) =>
                (parsed.ingredients ?? []).findIndex(
                  (ing) => ing.name === name,
                ),
              )
              .filter((idx) => idx !== -1),
          })),
        },
      })
    },
    onSuccess: (recipe) => {
      showSuccessToast(t("share.success", { title: recipe.title }))
      navigate({ to: "/recipes/$id", params: { id: recipe.id } })
    },
    onError: () => {
      showErrorToast(t("share.error"))
      navigate({ to: "/recipes" })
    },
  })

  useEffect(() => {
    if (hasTriggered.current) return
    hasTriggered.current = true

    const recipeUrl = extractRecipeUrl({ url, text })
    if (!recipeUrl) {
      showErrorToast(t("share.invalid_url"))
      navigate({ to: "/recipes" })
      return
    }
    importMutation.mutate(recipeUrl)
  }, [importMutation, navigate, showErrorToast, t, text, url]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <ChefHat className="h-12 w-12 animate-pulse text-muted-foreground" />
      <p className="text-muted-foreground">{t("share.importing")}</p>
    </div>
  )
}

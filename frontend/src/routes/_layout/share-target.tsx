import { useMutation } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { ChefHat, Loader2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { z } from "zod"

import { type ParsedRecipe, RecipesService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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

type Phase = "importing" | "consent" | "saving"

function ShareTargetPage() {
  const { url, text } = Route.useSearch()
  const navigate = useNavigate()
  const { t } = useTranslation("recipes")
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const hasTriggered = useRef(false)

  const [phase, setPhase] = useState<Phase>("importing")
  const [parsedRecipe, setParsedRecipe] = useState<ParsedRecipe | null>(null)
  const [targetUrl, setTargetUrl] = useState("")
  const [consentChecked, setConsentChecked] = useState(false)

  const importMutation = useMutation({
    mutationFn: (recipeUrl: string) =>
      RecipesService.importRecipeUrl({
        requestBody: { url: recipeUrl, language: i18n.language },
      }),
    onSuccess: (parsed, recipeUrl) => {
      setParsedRecipe(parsed)
      setTargetUrl(recipeUrl)
      setPhase("consent")
    },
    onError: () => {
      showErrorToast(t("share.error"))
      navigate({ to: "/recipes" })
    },
  })

  const saveMutation = useMutation({
    mutationFn: (vars: { parsed: ParsedRecipe; recipeUrl: string }) =>
      RecipesService.createRecipe({
        requestBody: {
          title: vars.parsed.title,
          description: vars.parsed.description ?? null,
          servings: vars.parsed.servings ?? null,
          prep_time_minutes: vars.parsed.prep_time_minutes ?? null,
          cook_time_minutes: vars.parsed.cook_time_minutes ?? null,
          source_url: vars.parsed.source_url ?? null,
          image_url: vars.parsed.image_url ?? null,
          import_consent: true,
          ingredients: (vars.parsed.ingredients ?? []).map((ing) => ({
            ingredient_name: ing.name,
            name_en: ing.name_en ?? null,
            quantity: ing.quantity,
            unit: ing.unit,
            notes: ing.notes ?? null,
            category: ing.category ?? null,
          })),
          steps: (vars.parsed.steps ?? []).map((step, i) => ({
            step_number: i + 1,
            instruction: step.instruction,
            ingredient_indices: (step.ingredient_names ?? [])
              .map((name) =>
                (vars.parsed.ingredients ?? []).findIndex(
                  (ing) => ing.name === name,
                ),
              )
              .filter((idx) => idx !== -1),
          })),
        },
      }),
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

  if (phase === "importing") {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-center">
        <ChefHat className="h-12 w-12 animate-pulse text-muted-foreground" />
        <p className="text-muted-foreground">{t("share.importing")}</p>
      </div>
    )
  }

  if (phase === "consent" && parsedRecipe) {
    return (
      <div className="flex flex-col items-center py-16 px-4">
        <div className="w-full max-w-md space-y-4 text-left">
          <h2 className="text-lg font-semibold">{t("share.consent_title")}</h2>
          <p className="text-sm text-muted-foreground">
            {t("share.consent_description")}
          </p>
          <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/20">
            <Checkbox
              id="share-consent"
              checked={consentChecked}
              onCheckedChange={(v) => setConsentChecked(Boolean(v))}
            />
            <label
              htmlFor="share-consent"
              className="text-sm leading-snug cursor-pointer"
            >
              {t("share.consent_label")}
            </label>
          </div>
          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={() => navigate({ to: "/recipes" })}
            >
              {t("share.consent_cancel")}
            </Button>
            <Button
              disabled={!consentChecked || saveMutation.isPending}
              onClick={() =>
                saveMutation.mutate({
                  parsed: parsedRecipe,
                  recipeUrl: targetUrl,
                })
              }
            >
              {saveMutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              )}
              {t("share.consent_confirm")}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <ChefHat className="h-12 w-12 animate-pulse text-muted-foreground" />
      <p className="text-muted-foreground">{t("share.importing")}</p>
    </div>
  )
}

import i18n from "i18next"
import { Download, Loader2 } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import type { Difficulty, MealType, Season } from "@/client"
import { RecipesService } from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import useCustomToast from "@/hooks/useCustomToast"

import { defaultCreateValues, type RecipeFormValues } from "./recipeFormSchema"

interface Props {
  onImported: (values: RecipeFormValues) => void
}

export function RecipeImportPanel({ onImported }: Props) {
  const { t } = useTranslation("recipes")
  const { t: tCommon } = useTranslation("common")
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [url, setUrl] = useState("")
  const [isImporting, setIsImporting] = useState(false)

  const handleImport = async () => {
    if (!url.trim()) return
    setIsImporting(true)
    try {
      const parsed = await RecipesService.importRecipeUrl({
        requestBody: { url, language: i18n.language },
      })

      const mappedIngredients = (parsed.ingredients ?? []).map((pi) => ({
        ingredient_name: pi.name,
        quantity: pi.quantity,
        unit: pi.unit,
        notes: pi.notes ?? "",
        name_en: pi.name_en ?? null,
        category: pi.category ?? null,
      }))

      const nameToIdx = new Map(
        mappedIngredients.map((mi, idx) => [
          mi.ingredient_name.toLowerCase(),
          idx,
        ]),
      )

      const mappedSteps = (parsed.steps ?? []).map((ps) => {
        const indices = (ps.ingredient_names ?? [])
          .map((name) => nameToIdx.get(name.toLowerCase()) ?? -1)
          .filter((idx) => idx >= 0)
        return { instruction: ps.instruction, ingredient_indices: indices }
      })

      onImported({
        ...defaultCreateValues,
        title: parsed.title,
        description: parsed.description ?? "",
        servings: parsed.servings ?? "",
        prep_time_minutes: parsed.prep_time_minutes ?? "",
        cook_time_minutes: parsed.cook_time_minutes ?? "",
        source_url: parsed.source_url ?? "",
        image_url: parsed.image_url ?? "",
        ingredients: mappedIngredients,
        steps: mappedSteps,
        seasons: (parsed.seasons ?? []) as Season[],
        is_vegan: parsed.is_vegan ?? false,
        is_vegetarian: parsed.is_vegetarian ?? false,
        is_gluten_free: parsed.is_gluten_free ?? false,
        is_dairy_free: parsed.is_dairy_free ?? false,
        kcal_per_serving: parsed.kcal_per_serving ?? "",
        difficulty: (parsed.difficulty as Difficulty) ?? "",
        meal_type: (parsed.meal_type as MealType) ?? "",
        cuisine_type: parsed.cuisine_type ?? "",
      })
      setUrl("")
      showSuccessToast(t("add.import_success"))
    } catch {
      showErrorToast(t("add.import_error"))
    } finally {
      setIsImporting(false)
    }
  }

  return (
    <div className="flex gap-2 p-3 rounded-md border border-dashed bg-muted/30">
      <Input
        placeholder={t("add.import_placeholder")}
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault()
            handleImport()
          }
        }}
        className="bg-transparent border-0 shadow-none focus-visible:ring-0 px-0"
      />
      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={handleImport}
        disabled={isImporting || !url.trim()}
      >
        {isImporting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Download className="h-4 w-4" />
        )}
        <span className="ml-1.5">{tCommon("import")}</span>
      </Button>
    </div>
  )
}

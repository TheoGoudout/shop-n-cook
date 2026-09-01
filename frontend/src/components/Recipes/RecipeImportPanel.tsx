import i18n from "i18next"
import { Download, Loader2 } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { RecipesService } from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import useCustomToast from "@/hooks/useCustomToast"

import { parsedRecipeToFormValues } from "./parsedRecipeToFormValues"
import type { RecipeFormValues } from "./recipeFormSchema"

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
      onImported(parsedRecipeToFormValues(parsed, "url"))
      setUrl("")
      showSuccessToast(t("add.import_success"))
    } catch {
      showErrorToast(t("add.import_error"))
    } finally {
      setIsImporting(false)
    }
  }

  return (
    <div className="flex gap-2">
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

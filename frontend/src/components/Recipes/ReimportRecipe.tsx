import { RefreshCw } from "lucide-react"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { useCrudMutation } from "@/hooks/useCrudMutation"

interface Props {
  id: string
  onSuccess: () => void
}

const ReimportRecipe = ({ id, onSuccess }: Props) => {
  const { t, i18n } = useTranslation("recipes")
  const mutation = useCrudMutation({
    mutationFn: () =>
      RecipesService.reimportRecipe({
        id,
        requestBody: { language: i18n.language },
      }),
    successMessage: t("reimport.success"),
    onSuccess: () => {
      onSuccess()
      window.location.reload()
    },
    invalidateKeys: ["recipes"],
  })

  return (
    <DropdownMenuItem
      onSelect={(e) => e.preventDefault()}
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
    >
      <RefreshCw />
      {t("reimport.menu_item")}
    </DropdownMenuItem>
  )
}

export default ReimportRecipe

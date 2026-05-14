import { useMutation, useQueryClient } from "@tanstack/react-query"
import { RefreshCw } from "lucide-react"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface Props {
  id: string
  onSuccess: () => void
}

const ReimportRecipe = ({ id, onSuccess }: Props) => {
  const { t, i18n } = useTranslation("recipes")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () =>
      RecipesService.reimportRecipe({
        id,
        requestBody: { language: i18n.language },
      }),
    onSuccess: () => {
      showSuccessToast(t("reimport.success"))
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["recipes"] }),
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

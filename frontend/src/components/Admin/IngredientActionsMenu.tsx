import { useMutation, useQueryClient } from "@tanstack/react-query"
import { EllipsisVertical, RefreshCw } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import type { IngredientPublic } from "@/client"
import { IngredientsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import EditIngredient from "./EditIngredient"

interface IngredientActionsMenuProps {
  ingredient: IngredientPublic
}

export const IngredientActionsMenu = ({
  ingredient,
}: IngredientActionsMenuProps) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { t } = useTranslation("admin")

  const fetchImageMutation = useMutation({
    mutationFn: () =>
      IngredientsService.fetchIngredientImage({ id: ingredient.id }),
    onSuccess: () => {
      showSuccessToast(t("ingredient.fetch_image_queued"))
      // Background task needs time to complete; refresh after a short delay
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["ingredient-catalog"] })
      }, 3000)
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditIngredient
          ingredient={ingredient}
          onSuccess={() => setOpen(false)}
        />
        <DropdownMenuItem onClick={() => fetchImageMutation.mutate()}>
          <RefreshCw />
          {t("ingredient.fetch_image")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

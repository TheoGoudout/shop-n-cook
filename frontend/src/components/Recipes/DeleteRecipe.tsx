import { Trash2 } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { useCrudMutation } from "@/hooks/useCrudMutation"

interface Props {
  id: string
  onSuccess: () => void
}

const DeleteRecipe = ({ id, onSuccess }: Props) => {
  const { t } = useTranslation("recipes")
  const [isOpen, setIsOpen] = useState(false)

  const mutation = useCrudMutation({
    mutationFn: () => RecipesService.deleteRecipe({ id }),
    successMessage: t("delete.success"),
    invalidateKeys: ["recipes"],
    onSuccess: () => {
      setIsOpen(false)
      onSuccess()
    },
  })

  return (
    <ConfirmDialog
      open={isOpen}
      onOpenChange={setIsOpen}
      title={t("delete.dialog_title")}
      description={t("delete.dialog_description")}
      variant="destructive"
      isPending={mutation.isPending}
      onConfirm={() => mutation.mutate()}
      trigger={
        <DropdownMenuItem
          variant="destructive"
          onSelect={(e) => e.preventDefault()}
          onClick={() => setIsOpen(true)}
        >
          <Trash2 />
          {t("delete.menu_item")}
        </DropdownMenuItem>
      }
    />
  )
}

export default DeleteRecipe

import { Trash2 } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { UsersService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { useCrudMutation } from "@/hooks/useCrudMutation"

interface DeleteUserProps {
  id: string
  onSuccess: () => void
}

const DeleteUser = ({ id, onSuccess }: DeleteUserProps) => {
  const { t } = useTranslation("admin")
  const [isOpen, setIsOpen] = useState(false)

  const mutation = useCrudMutation({
    mutationFn: () => UsersService.deleteUser({ userId: id }),
    successMessage: t("delete.success"),
    invalidateKeys: ["users"],
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

export default DeleteUser

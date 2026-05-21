import { useState } from "react"
import { useTranslation } from "react-i18next"

import { UsersService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { DialogTrigger } from "@/components/ui/dialog"
import useAuth from "@/hooks/useAuth"
import { useCrudMutation } from "@/hooks/useCrudMutation"

const DeleteConfirmation = () => {
  const { t } = useTranslation("settings")
  const [isOpen, setIsOpen] = useState(false)
  const { logout } = useAuth()

  const mutation = useCrudMutation({
    mutationFn: () => UsersService.deleteUserMe(),
    successMessage: t("delete_account.success"),
    invalidateKeys: ["currentUser"],
    onSuccess: () => {
      logout()
    },
  })

  return (
    <ConfirmDialog
      open={isOpen}
      onOpenChange={setIsOpen}
      title={t("delete_account.dialog_title")}
      description={t("delete_account.dialog_description")}
      variant="destructive"
      isPending={mutation.isPending}
      onConfirm={() => mutation.mutate()}
      trigger={
        <DialogTrigger asChild>
          <Button variant="destructive" className="mt-3">
            {t("delete_account.button")}
          </Button>
        </DialogTrigger>
      }
    />
  )
}

export default DeleteConfirmation

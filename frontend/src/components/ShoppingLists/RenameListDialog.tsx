import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { ShoppingListsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCrudMutation } from "@/hooks/useCrudMutation"

interface Props {
  listId: string
  currentName: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function RenameListDialog({
  listId,
  currentName,
  open,
  onOpenChange,
}: Props) {
  const { t } = useTranslation("shopping")
  const { t: tCommon } = useTranslation("common")
  const [newName, setNewName] = useState(currentName)

  useEffect(() => {
    if (open) setNewName(currentName)
  }, [open, currentName])

  const mutation = useCrudMutation({
    mutationFn: () =>
      ShoppingListsService.updateShoppingList({
        id: listId,
        requestBody: { name: newName },
      }),
    successMessage: t("rename_dialog.success"),
    invalidateKeys: ["shopping-lists"],
    onSuccess: () => onOpenChange(false),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("rename_dialog.title")}</DialogTitle>
        </DialogHeader>
        <div className="py-4">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              {tCommon("cancel")}
            </Button>
          </DialogClose>
          <LoadingButton
            onClick={() => mutation.mutate()}
            loading={mutation.isPending}
            disabled={!newName.trim()}
          >
            {t("rename_dialog.submit")}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: "default" | "destructive"
  isPending: boolean
  onConfirm: () => void
  /**
   * Optional trigger element rendered inside the Dialog (e.g. a
   * DropdownMenuItem that calls `onOpenChange(true)`). When omitted, the
   * caller is expected to control `open` externally.
   */
  trigger?: ReactNode
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel,
  variant = "default",
  isPending,
  onConfirm,
  trigger,
}: ConfirmDialogProps) {
  const { t: tCommon } = useTranslation("common")
  const resolvedConfirm =
    confirmLabel ??
    (variant === "destructive" ? tCommon("delete") : tCommon("save"))
  const resolvedCancel = cancelLabel ?? tCommon("cancel")

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {trigger}
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={isPending}>
              {resolvedCancel}
            </Button>
          </DialogClose>
          <LoadingButton
            variant={variant === "destructive" ? "destructive" : "default"}
            loading={isPending}
            onClick={onConfirm}
          >
            {resolvedConfirm}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

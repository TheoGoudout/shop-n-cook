import { zodResolver } from "@hookform/resolvers/zod"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"
import { type UserPublic, UsersService } from "@/client"
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
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Form } from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCrudMutation } from "@/hooks/useCrudMutation"
import { passwordsMismatch } from "@/lib/passwordSchema"
import { UserFormFields } from "./UserFormFields"

type FormData = {
  email: string
  full_name?: string
  password?: string
  confirm_password?: string
  is_superuser?: boolean
  is_active?: boolean
}

interface EditUserProps {
  user: UserPublic
  onSuccess: () => void
}

const EditUser = ({ user, onSuccess }: EditUserProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const { t } = useTranslation("admin")
  const { t: tAuth } = useTranslation("auth")
  const { t: tCommon } = useTranslation("common")

  const formSchema = z
    .object({
      email: z.email({ message: tAuth("validation.email_invalid") }),
      full_name: z.string().optional(),
      password: z
        .string()
        .min(8, { message: tAuth("validation.password_min") })
        .optional()
        .or(z.literal("")),
      confirm_password: z.string().optional(),
      is_superuser: z.boolean().optional(),
      is_active: z.boolean().optional(),
    })
    .refine(
      (data) => !data.password || data.password === data.confirm_password,
      passwordsMismatch(tAuth),
    )

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: user.email,
      full_name: user.full_name ?? undefined,
      is_superuser: user.is_superuser,
      is_active: user.is_active,
    },
  })

  const mutation = useCrudMutation({
    mutationFn: (data: FormData) =>
      UsersService.updateUser({ userId: user.id, requestBody: data }),
    successMessage: t("edit.success"),
    onSuccess: () => {
      setIsOpen(false)
      onSuccess()
    },
    invalidateKeys: ["users"],
  })

  const onSubmit = (data: FormData) => {
    const { confirm_password: _, ...submitData } = data
    if (!submitData.password) {
      delete submitData.password
    }
    mutation.mutate(submitData)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        {t("edit.menu_item")}
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>{t("edit.dialog_title")}</DialogTitle>
              <DialogDescription>
                {t("edit.dialog_description")}
              </DialogDescription>
            </DialogHeader>
            <UserFormFields passwordRequired={false} />

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  {tCommon("cancel")}
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                {tCommon("save")}
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default EditUser

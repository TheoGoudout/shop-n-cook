import { zodResolver } from "@hookform/resolvers/zod"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"
import { type UserCreate, UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Form } from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCrudMutation } from "@/hooks/useCrudMutation"
import { passwordSchema, passwordsMismatch } from "@/lib/passwordSchema"
import { UserFormFields } from "./UserFormFields"

type FormData = {
  email: string
  full_name?: string
  password: string
  confirm_password: string
  is_superuser: boolean
  is_active: boolean
}

const AddUser = () => {
  const [isOpen, setIsOpen] = useState(false)
  const { t } = useTranslation("admin")
  const { t: tAuth } = useTranslation("auth")
  const { t: tCommon } = useTranslation("common")

  const formSchema = z
    .object({
      email: z.email({ message: tAuth("validation.email_invalid") }),
      full_name: z.string().optional(),
      password: passwordSchema(tAuth),
      confirm_password: z
        .string()
        .min(1, { message: tAuth("validation.confirm_required_alt") }),
      is_superuser: z.boolean(),
      is_active: z.boolean(),
    })
    .refine(
      (data) => data.password === data.confirm_password,
      passwordsMismatch(tAuth),
    )

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: "",
      full_name: "",
      password: "",
      confirm_password: "",
      is_superuser: false,
      is_active: false,
    },
  })

  const mutation = useCrudMutation({
    mutationFn: (data: UserCreate) =>
      UsersService.createUser({ requestBody: data }),
    successMessage: t("add.success"),
    onSuccess: () => {
      form.reset()
      setIsOpen(false)
    },
    invalidateKeys: ["users"],
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate(data)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="my-4">
          <Plus className="mr-2" />
          {t("add.button")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("add.dialog_title")}</DialogTitle>
          <DialogDescription>{t("add.dialog_description")}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <UserFormFields passwordRequired={true} />

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

export default AddUser

import { useFormContext } from "react-hook-form"
import { useTranslation } from "react-i18next"

import { Checkbox } from "@/components/ui/checkbox"
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"

type UserFormFieldValues = {
  email: string
  full_name?: string
  password?: string
  confirm_password?: string
  is_superuser?: boolean
  is_active?: boolean
}

function RequiredMark({ show }: { show: boolean }) {
  return show ? <span className="text-destructive"> *</span> : null
}

/**
 * The fields of the add-user and edit-user forms, read from the enclosing
 * `<Form>`. A new user needs a password; an existing one keeps theirs unless
 * a new one is typed.
 */
export function UserFormFields({
  passwordRequired,
}: {
  passwordRequired: boolean
}) {
  const { t } = useTranslation("admin")
  const { control } = useFormContext<UserFormFieldValues>()

  const passwordField = (
    name: "password" | "confirm_password",
    label: string,
  ) => (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>
            {label}
            <RequiredMark show={passwordRequired} />
          </FormLabel>
          <FormControl>
            <Input
              placeholder={t("forms.password_placeholder")}
              type="password"
              {...field}
              required={passwordRequired}
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )

  const checkboxField = (name: "is_superuser" | "is_active", label: string) => (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem className="flex items-center gap-3 space-y-0">
          <FormControl>
            <Checkbox checked={field.value} onCheckedChange={field.onChange} />
          </FormControl>
          <FormLabel className="font-normal">{label}</FormLabel>
        </FormItem>
      )}
    />
  )

  return (
    <div className="grid gap-4 py-4">
      <FormField
        control={control}
        name="email"
        render={({ field }) => (
          <FormItem>
            <FormLabel>
              {t("forms.email_label")}
              <RequiredMark show />
            </FormLabel>
            <FormControl>
              <Input
                placeholder={t("forms.email_placeholder")}
                type="email"
                {...field}
                required
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
      <FormField
        control={control}
        name="full_name"
        render={({ field }) => (
          <FormItem>
            <FormLabel>{t("forms.full_name_label")}</FormLabel>
            <FormControl>
              <Input
                placeholder={t("forms.full_name_placeholder")}
                type="text"
                {...field}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
      {passwordField("password", t("forms.set_password_label"))}
      {passwordField("confirm_password", t("forms.confirm_password_label"))}
      {checkboxField("is_superuser", t("forms.is_superuser_label"))}
      {checkboxField("is_active", t("forms.is_active_label"))}
    </div>
  )
}

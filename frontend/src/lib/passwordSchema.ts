import { z } from "zod"

/** Translates a key of the `auth` namespace. */
type AuthT = (key: string) => string

/** A password the backend accepts: required, at least 8 characters. */
export const passwordSchema = (t: AuthT) =>
  z
    .string()
    .min(1, { message: t("validation.password_required") })
    .min(8, { message: t("validation.password_min") })

/** The error a form shows on `confirm_password` when it does not match. */
export const passwordsMismatch = (t: AuthT) => ({
  message: t("validation.passwords_mismatch"),
  path: ["confirm_password"],
})

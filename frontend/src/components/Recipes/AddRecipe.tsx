import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useMemo, useState } from "react"
import { type Resolver, useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

import { RecipeForm } from "./RecipeForm"
import { RecipeImportTabs } from "./RecipeImportTabs"
import {
  createRecipeFormSchema,
  defaultCreateValues,
  type RecipeFormValues,
  toRecipeCreatePayload,
} from "./recipeFormSchema"

const AddRecipe = () => {
  const { t } = useTranslation("recipes")
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const formSchema = useMemo(
    () => createRecipeFormSchema(t, { requireImportConsent: true }),
    [t],
  )

  const form = useForm<RecipeFormValues>({
    resolver: zodResolver(formSchema) as Resolver<RecipeFormValues>,
    defaultValues: defaultCreateValues,
  })

  const mutation = useMutation({
    mutationFn: (data: RecipeFormValues) =>
      RecipesService.createRecipe({ requestBody: toRecipeCreatePayload(data) }),
    onSuccess: () => {
      showSuccessToast(t("add.success"))
      form.reset(defaultCreateValues)
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="my-4">
          <Plus className="mr-2" />
          {t("add.button")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("add.dialog_title")}</DialogTitle>
          <DialogDescription>{t("add.dialog_description")}</DialogDescription>
        </DialogHeader>
        <RecipeForm
          form={form}
          mode="create"
          onSubmit={(data) => mutation.mutate(data)}
          isPending={mutation.isPending}
          importPanel={
            <RecipeImportTabs onImported={(values) => form.reset(values)} />
          }
        />
      </DialogContent>
    </Dialog>
  )
}

export default AddRecipe

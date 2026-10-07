import { zodResolver } from "@hookform/resolvers/zod"
import { Pencil } from "lucide-react"
import { useMemo, useState } from "react"
import { type Resolver, useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"

import { type RecipePublic, RecipesService } from "@/client"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { useCrudMutation } from "@/hooks/useCrudMutation"

import { RecipeForm } from "./RecipeForm"
import {
  buildEditDefaults,
  createRecipeFormSchema,
  type RecipeFormValues,
  toRecipeUpdatePayload,
} from "./recipeFormSchema"

interface Props {
  recipe: RecipePublic
  onSuccess: () => void
}

const EditRecipe = ({ recipe, onSuccess }: Props) => {
  const { t } = useTranslation("recipes")
  const [isOpen, setIsOpen] = useState(false)
  const formSchema = useMemo(() => createRecipeFormSchema(t), [t])

  const defaultValues = useMemo(() => buildEditDefaults(recipe), [recipe])

  const form = useForm<RecipeFormValues>({
    resolver: zodResolver(formSchema) as Resolver<RecipeFormValues>,
    defaultValues,
  })

  const mutation = useCrudMutation({
    mutationFn: (data: RecipeFormValues) =>
      RecipesService.updateRecipe({
        id: recipe.id,
        requestBody: toRecipeUpdatePayload(data),
      }),
    successMessage: t("edit.success"),
    onSuccess: () => {
      setIsOpen(false)
      onSuccess()
    },
    invalidateKeys: [["recipes"], ["recipe", recipe.id]],
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        {t("edit.menu_item")}
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("edit.dialog_title")}</DialogTitle>
          <DialogDescription>{t("edit.dialog_description")}</DialogDescription>
        </DialogHeader>
        <RecipeForm
          form={form}
          mode="edit"
          isPublicAlreadySet={recipe.is_public}
          onSubmit={(data) => mutation.mutate(data)}
          isPending={mutation.isPending}
        />
      </DialogContent>
    </Dialog>
  )
}

export default EditRecipe

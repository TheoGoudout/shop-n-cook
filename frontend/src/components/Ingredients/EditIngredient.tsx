import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"

import {
  type IngredientPublic,
  IngredientsService,
  type IngredientUpdate,
} from "@/client"
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const CATEGORIES = [
  "produce",
  "dairy",
  "meat",
  "seafood",
  "grains",
  "pantry",
  "spices",
  "beverages",
  "frozen",
  "bakery",
  "other",
]

const UNITS = [
  "g",
  "kg",
  "ml",
  "L",
  "piece",
  "tbsp",
  "tsp",
  "cup",
  "oz",
  "lb",
  "bunch",
  "pinch",
  "clove",
  "slice",
  "can",
  "package",
]

const formSchema = z.object({
  name: z.string().min(1),
  category: z.string().min(1),
  default_unit: z.string().min(1),
})

type FormData = z.infer<typeof formSchema>

interface Props {
  ingredient: IngredientPublic
  onSuccess: () => void
}

const EditIngredient = ({ ingredient, onSuccess }: Props) => {
  const { t } = useTranslation("ingredients")
  const { t: tCommon } = useTranslation("common")
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: ingredient.name,
      category: ingredient.category,
      default_unit: ingredient.default_unit,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      IngredientsService.updateIngredient({
        id: ingredient.id,
        requestBody: data as IngredientUpdate,
      }),
    onSuccess: () => {
      showSuccessToast(t("edit.success"))
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["ingredients"] }),
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
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))}>
            <DialogHeader>
              <DialogTitle>{t("edit.dialog_title")}</DialogTitle>
              <DialogDescription>
                {t("edit.dialog_description")}
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("form.name_label")}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="category"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("form.category_label")}</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {CATEGORIES.map((c) => (
                          <SelectItem key={c} value={c}>
                            {tCommon(`categories.${c}`, { defaultValue: c })}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="default_unit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("form.default_unit_label")}</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {UNITS.map((u) => (
                          <SelectItem key={u} value={u}>
                            {tCommon(`unit_labels.${u}`, { defaultValue: u })}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
            </div>
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

export default EditIngredient

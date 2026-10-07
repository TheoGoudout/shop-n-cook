import { zodResolver } from "@hookform/resolvers/zod"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { z } from "zod"
import {
  type IngredientCategory,
  type IngredientPublic,
  IngredientsService,
} from "@/client"
import { IngredientCategorySchema } from "@/client/schemas.gen"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
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
import { useCrudMutation } from "@/hooks/useCrudMutation"

const CATEGORIES = IngredientCategorySchema.enum

const formSchema = z.object({
  category: z.string(),
  image_url: z.string().optional(),
})

type FormData = z.infer<typeof formSchema>

interface EditIngredientProps {
  ingredient: IngredientPublic
  onSuccess: () => void
}

const EditIngredient = ({ ingredient, onSuccess }: EditIngredientProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const { t } = useTranslation("common")
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      category: ingredient.category ?? "other",
      image_url: ingredient.image_url ?? "",
    },
  })

  const mutation = useCrudMutation({
    mutationFn: (data: FormData) =>
      IngredientsService.updateIngredient({
        id: ingredient.id,
        requestBody: {
          category: data.category as IngredientCategory,
          image_url: data.image_url || null,
        },
      }),
    successMessage: t("ingredient.updated", { ns: "admin" }),
    onSuccess: () => {
      setIsOpen(false)
      onSuccess()
    },
    invalidateKeys: ["ingredient-catalog"],
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        {t("ingredient.edit", { ns: "admin" })}
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))}>
            <DialogHeader>
              <DialogTitle>
                {t("ingredient.edit_title", {
                  ns: "admin",
                  name: ingredient.name,
                })}
              </DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="category"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("category")}</FormLabel>
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
                        {CATEGORIES.map((cat) => (
                          <SelectItem key={cat} value={cat}>
                            {t(`categories.${cat}`, { defaultValue: cat })}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="image_url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {t("ingredient.image_url", { ns: "admin" })}
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="https://..." {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  {t("cancel")}
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                {t("save")}
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default EditIngredient

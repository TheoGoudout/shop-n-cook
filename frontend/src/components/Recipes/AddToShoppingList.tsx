import { useQuery } from "@tanstack/react-query"
import { ShoppingCart } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import {
  type RecipePublic,
  type ShoppingListPublic,
  ShoppingListsService,
  UserSettingsService,
} from "@/client"
import { getDefaultListDefaults } from "@/components/ShoppingLists/AddShoppingList"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCrudMutation } from "@/hooks/useCrudMutation"

const NEW_LIST = "__new__"

function localDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/**
 * The list a recipe most likely belongs on: the one whose dates cover today,
 * else the newest one (the API returns lists newest first).
 */
export function pickCurrentList(
  lists: ShoppingListPublic[],
  today: string = localDate(new Date()),
): ShoppingListPublic | undefined {
  const current = lists.find(
    (l) =>
      l.start_date &&
      l.end_date &&
      l.start_date <= today &&
      today <= l.end_date,
  )
  return current ?? lists[0]
}

interface Props {
  recipe: RecipePublic
  /** `icon` is the compact form used on recipe cards. */
  variant?: "button" | "icon"
}

export function AddToShoppingList({ recipe, variant = "button" }: Props) {
  const { t, i18n } = useTranslation("recipes")
  const { t: tCommon } = useTranslation("common")
  const [open, setOpen] = useState(false)
  const [listId, setListId] = useState("")
  const [servings, setServings] = useState("")

  const { data: listsData, isLoading: listsLoading } = useQuery({
    queryKey: ["shopping-lists"],
    queryFn: () => ShoppingListsService.readShoppingLists({ limit: 100 }),
    enabled: open,
  })
  const { data: userSettings } = useQuery({
    queryKey: ["user-settings"],
    queryFn: () => UserSettingsService.readUserSettings(),
    enabled: open,
  })

  const lists = listsData?.data ?? []
  const selectedId = listId || pickCurrentList(lists)?.id || NEW_LIST
  const defaultServings = userSettings?.household_size ?? recipe.servings
  const newListDefaults = getDefaultListDefaults(i18n.language)
  const selectedList = lists.find((l) => l.id === selectedId)

  const mutation = useCrudMutation({
    mutationFn: async () => {
      const target =
        selectedList ??
        (await ShoppingListsService.createShoppingList({
          requestBody: newListDefaults,
        }))
      return ShoppingListsService.addRecipe({
        id: target.id,
        recipeId: recipe.id,
        servings: servings ? Number(servings) : (defaultServings ?? undefined),
      })
    },
    // Name the list: it was picked for the user, who may not have looked.
    successMessage: t("add_to_list.success", {
      name: selectedList?.name ?? newListDefaults.name,
    }),
    invalidateKeys: ["shopping-lists"],
    onSuccess: () => setOpen(false),
  })

  const onOpenChange = (next: boolean) => {
    setOpen(next)
    if (next) {
      setListId("")
      setServings("")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {variant === "icon" ? (
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("add_to_list.button")}
          title={t("add_to_list.button")}
          onClick={() => onOpenChange(true)}
        >
          <ShoppingCart />
        </Button>
      ) : (
        <Button onClick={() => onOpenChange(true)}>
          <ShoppingCart />
          {t("add_to_list.button")}
        </Button>
      )}
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("add_to_list.dialog_title")}</DialogTitle>
          <DialogDescription>
            {t("add_to_list.dialog_description", { title: recipe.title })}
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            mutation.mutate()
          }}
        >
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor={`add-to-list-${recipe.id}`}>
                {t("add_to_list.list_label")}
              </Label>
              <Select
                value={listsLoading ? undefined : selectedId}
                onValueChange={setListId}
                disabled={listsLoading}
              >
                <SelectTrigger id={`add-to-list-${recipe.id}`}>
                  <SelectValue placeholder={tCommon("loading")} />
                </SelectTrigger>
                <SelectContent>
                  {lists.map((l) => (
                    <SelectItem key={l.id} value={l.id}>
                      {l.name}
                    </SelectItem>
                  ))}
                  <SelectItem value={NEW_LIST}>
                    {t("add_to_list.new_list", {
                      name: newListDefaults.name,
                    })}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor={`add-to-list-servings-${recipe.id}`}>
                {t("add_to_list.servings_label")}
              </Label>
              <Input
                id={`add-to-list-servings-${recipe.id}`}
                type="number"
                min={1}
                step={1}
                value={servings}
                onChange={(e) => setServings(e.target.value)}
                placeholder={defaultServings ? String(defaultServings) : "4"}
              />
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button
                type="button"
                variant="outline"
                disabled={mutation.isPending}
              >
                {tCommon("cancel")}
              </Button>
            </DialogClose>
            <LoadingButton
              type="submit"
              loading={mutation.isPending}
              disabled={listsLoading}
            >
              {t("add_to_list.submit")}
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

import { useQuery } from "@tanstack/react-query"
import { ChefHat, Search } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import {
  type GenerateMenuRequest,
  MealPlansService,
  type MealType,
} from "@/client"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

/**
 * Pick a recipe by hand for one meal of the menu.
 *
 * Only recipes matching the menu's preferences are listed, so choosing one
 * yourself cannot break the diet the menu was generated for.
 */
export function RecipePickerDialog({
  open,
  onOpenChange,
  request,
  mealType,
  currentRecipeId,
  context,
  onPick,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  request: GenerateMenuRequest
  mealType: MealType | undefined
  currentRecipeId: string | undefined
  /** Which meal this is for, e.g. "Monday dinner". */
  context: string
  onPick: (recipeId: string) => void
}) {
  const { t } = useTranslation("mealPlans")
  const [search, setSearch] = useState("")

  const { data: options, isLoading } = useQuery({
    queryKey: ["menu-options", request, mealType, search],
    queryFn: () =>
      MealPlansService.menuRecipeOptions({
        requestBody: {
          ...request,
          meal_type: mealType,
          search: search.trim() || null,
        },
      }),
    enabled: open,
  })

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setSearch("")
        onOpenChange(next)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("review.choose")}</DialogTitle>
          <DialogDescription>
            {t("review.choose_description", { meal: context })}
          </DialogDescription>
        </DialogHeader>
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            autoFocus
            className="pl-8"
            value={search}
            placeholder={t("review.search_placeholder")}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="-mx-2 max-h-80 overflow-y-auto">
          {isLoading ? (
            <div className="space-y-2 px-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : (options ?? []).length === 0 ? (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">
              {t("review.no_options")}
            </p>
          ) : (
            (options ?? []).map((option) => {
              const current = option.id === currentRecipeId
              return (
                <button
                  type="button"
                  key={option.id}
                  disabled={current}
                  onClick={() => {
                    onPick(option.id)
                    setSearch("")
                  }}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent disabled:cursor-default disabled:opacity-60 disabled:hover:bg-transparent",
                  )}
                >
                  {option.image_url ? (
                    <img
                      src={option.image_url}
                      alt=""
                      className="h-9 w-9 shrink-0 rounded object-cover"
                    />
                  ) : (
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-muted">
                      <ChefHat className="h-4 w-4 text-muted-foreground" />
                    </span>
                  )}
                  <span className="min-w-0 flex-1 truncate">
                    {option.title}
                  </span>
                  {current && (
                    <span className="text-xs text-muted-foreground">
                      {t("review.current")}
                    </span>
                  )}
                </button>
              )
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

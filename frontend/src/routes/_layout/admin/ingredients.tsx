import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Package } from "lucide-react"
import { useTranslation } from "react-i18next"

import { IngredientsService } from "@/client"
import { IngredientActionsMenu } from "@/components/Admin/IngredientActionsMenu"
import { Badge } from "@/components/ui/badge"
import { APP_NAME } from "@/lib/config"

export const Route = createFileRoute("/_layout/admin/ingredients")({
  component: IngredientsPage,
  head: () => ({
    meta: [{ title: `Ingredients - Admin - ${APP_NAME}` }],
  }),
})

function IngredientsTableContent() {
  const { t } = useTranslation("common")
  const { data } = useQuery({
    queryKey: ["ingredient-catalog"],
    queryFn: () => IngredientsService.readIngredients({}),
  })

  const ingredients = data?.data ?? []

  if (ingredients.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic py-8 text-center">
        No ingredients in the catalog yet.
      </p>
    )
  }

  return (
    <div className="border rounded-md">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left font-medium p-3 w-10" />
            <th className="text-left font-medium p-3">{t("name")}</th>
            <th className="text-left font-medium p-3">{t("category")}</th>
            <th className="text-left font-medium p-3 hidden sm:table-cell">
              Image URL
            </th>
            <th className="p-3 w-12">
              <span className="sr-only">{t("actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {ingredients.map((ingredient) => {
            const categoryKey = ingredient.category ?? "other"
            return (
              <tr key={ingredient.id} className="border-b last:border-0">
                <td className="p-3">
                  {ingredient.image_url ? (
                    <img
                      src={ingredient.image_url}
                      alt={ingredient.name}
                      className="w-10 h-10 rounded-md object-contain bg-muted p-0.5"
                    />
                  ) : (
                    <div className="w-10 h-10 rounded-md bg-muted flex items-center justify-center">
                      <Package className="h-4 w-4 text-muted-foreground" />
                    </div>
                  )}
                </td>
                <td className="p-3 font-medium">{ingredient.name}</td>
                <td className="p-3">
                  <Badge variant="secondary">
                    {t(`categories.${categoryKey}`, {
                      defaultValue: categoryKey,
                    })}
                  </Badge>
                </td>
                <td className="p-3 hidden sm:table-cell">
                  {ingredient.image_url ? (
                    <a
                      href={ingredient.image_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-muted-foreground hover:text-foreground underline truncate max-w-xs block"
                    >
                      {ingredient.image_url}
                    </a>
                  ) : (
                    <span className="text-xs text-muted-foreground italic">
                      None
                    </span>
                  )}
                </td>
                <td className="p-3">
                  <div className="flex justify-end">
                    <IngredientActionsMenu ingredient={ingredient} />
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function IngredientsPage() {
  const { t } = useTranslation("admin")

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("ingredients.title")}
        </h1>
        <p className="text-muted-foreground">{t("ingredients.subtitle")}</p>
      </div>
      <IngredientsTableContent />
    </div>
  )
}

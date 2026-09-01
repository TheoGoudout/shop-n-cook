import { Image, Link } from "lucide-react"
import { useTranslation } from "react-i18next"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

import { RecipeImportPanel } from "./RecipeImportPanel"
import { RecipePhotoImportPanel } from "./RecipePhotoImportPanel"
import type { RecipeFormValues } from "./recipeFormSchema"

interface Props {
  onImported: (values: RecipeFormValues) => void
}

/** Import sources offered above the Add Recipe form. */
export function RecipeImportTabs({ onImported }: Props) {
  const { t } = useTranslation("recipes")

  return (
    <Tabs
      defaultValue="url"
      className="rounded-md border border-dashed bg-muted/30 p-3"
    >
      <TabsList className="mb-2">
        <TabsTrigger value="url">
          <Link className="h-4 w-4" />
          <span className="ml-1.5">{t("add.import_tab_url")}</span>
        </TabsTrigger>
        <TabsTrigger value="photos">
          <Image className="h-4 w-4" />
          <span className="ml-1.5">{t("add.import_tab_photos")}</span>
        </TabsTrigger>
      </TabsList>
      <TabsContent value="url">
        <RecipeImportPanel onImported={onImported} />
      </TabsContent>
      <TabsContent value="photos">
        <RecipePhotoImportPanel onImported={onImported} />
      </TabsContent>
    </Tabs>
  )
}

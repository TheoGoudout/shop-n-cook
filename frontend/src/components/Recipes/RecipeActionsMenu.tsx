import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { RecipePublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import DeleteRecipe from "./DeleteRecipe"
import EditRecipe from "./EditRecipe"
import ReimportRecipe from "./ReimportRecipe"

interface Props {
  recipe: RecipePublic
}

export const RecipeActionsMenu = ({ recipe }: Props) => {
  const [open, setOpen] = useState(false)
  const { user } = useAuth()

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditRecipe recipe={recipe} onSuccess={() => setOpen(false)} />
        {user?.is_superuser && recipe.source_url && (
          <ReimportRecipe id={recipe.id} onSuccess={() => setOpen(false)} />
        )}
        <DeleteRecipe id={recipe.id} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { IngredientPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteIngredient from "./DeleteIngredient"
import EditIngredient from "./EditIngredient"

interface Props {
  ingredient: IngredientPublic
}

export const IngredientActionsMenu = ({ ingredient }: Props) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditIngredient
          ingredient={ingredient}
          onSuccess={() => setOpen(false)}
        />
        <DeleteIngredient id={ingredient.id} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

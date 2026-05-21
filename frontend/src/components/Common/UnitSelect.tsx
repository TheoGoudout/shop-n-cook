import type { ComponentProps } from "react"
import { useTranslation } from "react-i18next"

import { UnitSchema } from "@/client/schemas.gen"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

type SelectTriggerProps = ComponentProps<typeof SelectTrigger>

interface UnitSelectProps
  extends Omit<SelectTriggerProps, "value" | "onValueChange" | "children"> {
  value: string
  onValueChange: (value: string) => void
}

export function UnitSelect({
  value,
  onValueChange,
  ...triggerProps
}: UnitSelectProps) {
  const { t: tCommon } = useTranslation("common")
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger {...triggerProps}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {UnitSchema.enum.map((u) => (
          <SelectItem key={u} value={u}>
            {tCommon(`unit_labels.${u}`, { defaultValue: u })}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

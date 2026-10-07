import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"

import type { Difficulty, MealType } from "@/client"
import { DifficultySchema, MealTypeSchema } from "@/client/schemas.gen"
import {
  DIFFICULTY_ICONS,
  MEAL_TYPE_ICONS,
} from "@/components/Common/categoryIcons"
import { FormControl } from "@/components/ui/form"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const KINDS = {
  difficulty: {
    values: DifficultySchema.enum,
    icons: DIFFICULTY_ICONS as Record<string, LucideIcon>,
    labelKey: (value: string) => `form.difficulty_${value}`,
  },
  meal_type: {
    values: MealTypeSchema.enum,
    icons: MEAL_TYPE_ICONS as Record<string, LucideIcon>,
    labelKey: (value: string) => `form.meal_${value}`,
  },
}

type Values = { difficulty: Difficulty; meal_type: MealType }

/** Radix Select forbids an empty value, so "none" travels as this sentinel. */
const NONE = "_none"

/**
 * A recipe's difficulty or meal type, each option with its icon, plus a
 * "none" option whose label the caller chooses. `""` means none.
 */
export function RecipeEnumSelect<K extends keyof Values>({
  kind,
  value,
  onChange,
  noneLabel,
  triggerClassName,
  inForm = false,
}: {
  kind: K
  value: Values[K] | ""
  onChange: (value: Values[K] | "") => void
  noneLabel: string
  triggerClassName?: string
  /** Inside a `FormField`: links the trigger to the field's label. */
  inForm?: boolean
}) {
  const { t } = useTranslation("recipes")
  const { values, icons, labelKey } = KINDS[kind]
  const trigger: ReactNode = (
    <SelectTrigger className={triggerClassName}>
      <SelectValue />
    </SelectTrigger>
  )
  return (
    <Select
      value={value || NONE}
      onValueChange={(v) => onChange(v === NONE ? "" : (v as Values[K]))}
    >
      {inForm ? <FormControl>{trigger}</FormControl> : trigger}
      <SelectContent>
        <SelectItem value={NONE}>{noneLabel}</SelectItem>
        {values.map((option) => {
          const Icon = icons[option]
          return (
            <SelectItem key={option} value={option}>
              <Icon aria-hidden="true" />
              {t(labelKey(option))}
            </SelectItem>
          )
        })}
      </SelectContent>
    </Select>
  )
}

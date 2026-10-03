import { Minus, Plus } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface ServingsStepperProps {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  disabled?: boolean
  /** Names what is being counted, for screen readers ("Monday dinner"). */
  label: string
  className?: string
}

/** A compact − n + control for a number of servings. */
export function ServingsStepper({
  value,
  onChange,
  min = 1,
  max = 50,
  disabled,
  label,
  className,
}: ServingsStepperProps) {
  const { t } = useTranslation("common")
  return (
    <fieldset
      className={cn("inline-flex items-center rounded-md border", className)}
      aria-label={label}
    >
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-7 w-7 rounded-r-none"
        disabled={disabled || value <= min}
        aria-label={t("servings_decrease")}
        onClick={() => onChange(value - 1)}
      >
        <Minus className="h-3 w-3" />
      </Button>
      <output
        className="min-w-14 px-1 text-center text-xs tabular-nums"
        aria-live="polite"
      >
        {t("servings_count", { count: value })}
      </output>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-7 w-7 rounded-l-none"
        disabled={disabled || value >= max}
        aria-label={t("servings_increase")}
        onClick={() => onChange(value + 1)}
      >
        <Plus className="h-3 w-3" />
      </Button>
    </fieldset>
  )
}

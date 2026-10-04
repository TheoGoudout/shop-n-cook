import { Check, Clock, Soup, Users } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Logo } from "@/components/Common/Logo"
import { PantryPattern } from "@/components/Common/PantryPattern"
import { cn } from "@/lib/utils"

/**
 * The sign-in screen's left panel: what the app is for, shown rather than
 * told — a recipe card resting on this week's shopping list.
 */
export function AuthShowcase() {
  const { t } = useTranslation("auth")
  const items = [
    { label: t("showcase.item_1"), done: true },
    { label: t("showcase.item_2"), done: true },
    { label: t("showcase.item_3"), done: false },
    { label: t("showcase.item_4"), done: false },
  ]

  return (
    <div className="relative hidden overflow-hidden bg-[color-mix(in_oklch,var(--saffron)_16%,var(--background))] lg:flex lg:flex-col lg:items-center lg:justify-center">
      <PantryPattern opacity={0.3} />
      <div className="relative flex w-full max-w-lg flex-col gap-10 px-8">
        <div className="flex flex-col gap-4">
          <Logo
            variant="full"
            asLink={false}
            className="[&_span]:text-2xl [&_svg]:size-8"
          />
          <h2 className="text-4xl leading-tight font-bold tracking-tight">
            {t("showcase.headline")}
          </h2>
        </div>

        <div className="relative h-80">
          {/* This week's list, underneath */}
          <div className="absolute right-0 top-14 w-64 rotate-3 rounded-2xl border bg-card p-5 shadow-md">
            <p className="font-display text-lg font-semibold">
              {t("showcase.list_title")}
            </p>
            <ul className="mt-3 flex flex-col gap-2.5 text-sm">
              {items.map(({ label, done }) => (
                <li key={label} className="flex items-center gap-2.5">
                  <span
                    className={cn(
                      "flex size-5 items-center justify-center rounded-md border",
                      done && "border-basil bg-basil text-white",
                    )}
                  >
                    {done && <Check className="size-3.5" strokeWidth={3} />}
                  </span>
                  <span
                    className={cn(done && "text-muted-foreground line-through")}
                  >
                    {label}
                  </span>
                </li>
              ))}
            </ul>
            <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-1/2 rounded-full bg-basil" />
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground">
              {t("showcase.list_progress")}
            </p>
          </div>

          {/* A recipe, resting on top */}
          <div className="absolute left-0 top-0 w-52 -rotate-6 overflow-hidden rounded-2xl border bg-card shadow-lg">
            <div className="flex h-28 items-center justify-center bg-[color-mix(in_oklch,var(--tomato)_22%,var(--card))] text-tomato">
              <Soup className="size-12" strokeWidth={1.5} />
            </div>
            <div className="p-4">
              <p className="font-display text-lg leading-snug font-semibold">
                {t("showcase.recipe_title")}
              </p>
              <div className="mt-2 flex gap-3 text-xs font-medium text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Clock className="size-3.5" />
                  {t("showcase.recipe_time")}
                </span>
                <span className="flex items-center gap-1">
                  <Users className="size-3.5" />
                  {t("showcase.recipe_servings")}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

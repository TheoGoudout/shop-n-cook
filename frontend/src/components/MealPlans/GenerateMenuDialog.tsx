import { useNavigate } from "@tanstack/react-router"
import { Sparkles } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { MealPlansService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCrudMutation } from "@/hooks/useCrudMutation"

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

/** The four dietary switches, which map one-to-one onto request flags. */
const DIETS = [
  ["require_vegan", "vegan"],
  ["require_vegetarian", "vegetarian"],
  ["require_gluten_free", "gluten_free"],
  ["require_dairy_free", "dairy_free"],
] as const

type DietKey = (typeof DIETS)[number][0]

/**
 * Compose a week of meals.
 *
 * Servings and budget are left blank by default and filled in server-side from
 * the user's household settings, so the common case is opening this and
 * pressing Generate.
 */
export function GenerateMenuDialog() {
  const { t } = useTranslation("mealPlans")
  const { t: tCommon } = useTranslation("common")
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const [start, setStart] = useState(today())
  const [days, setDays] = useState("7")
  const [servings, setServings] = useState("")
  const [budget, setBudget] = useState("")
  const [maxPrep, setMaxPrep] = useState("")
  const [matchSeason, setMatchSeason] = useState(true)
  const [includePublic, setIncludePublic] = useState(true)
  const [diets, setDiets] = useState<Record<DietKey, boolean>>({
    require_vegan: false,
    require_vegetarian: false,
    require_gluten_free: false,
    require_dairy_free: false,
  })

  const optionalNumber = (value: string) =>
    value.trim() === "" ? null : Number(value)

  const generate = useCrudMutation({
    mutationFn: () =>
      MealPlansService.generateMenuRoute({
        requestBody: {
          start_date: start,
          days: Number(days) || 7,
          servings: optionalNumber(servings),
          budget: budget.trim() === "" ? null : budget,
          max_prep_minutes: optionalNumber(maxPrep),
          match_season: matchSeason,
          include_public: includePublic,
          // A fresh seed each time, so pressing Generate again after a menu
          // you did not like actually gives you a different one.
          seed: Math.floor(Math.random() * 1_000_000),
          ...diets,
        },
      }),
    successMessage: t("generate.success"),
    invalidateKeys: [["meal-plans"]],
    onSuccess: (plan) => {
      setOpen(false)
      navigate({ to: "/meal-plans/$id", params: { id: plan.id } })
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <Sparkles />
          {t("generate.trigger")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("generate.title")}</DialogTitle>
          <DialogDescription>{t("generate.description")}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="space-y-1.5">
              <Label htmlFor="gen-start">{t("add.start_label")}</Label>
              <Input
                id="gen-start"
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="gen-days">{t("generate.days_label")}</Label>
              <Input
                id="gen-days"
                type="number"
                min="1"
                max="31"
                value={days}
                onChange={(e) => setDays(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="gen-servings">
                {t("generate.servings_label")}
              </Label>
              <Input
                id="gen-servings"
                type="number"
                min="1"
                value={servings}
                placeholder={t("generate.servings_placeholder")}
                onChange={(e) => setServings(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="gen-prep">{t("generate.max_prep_label")}</Label>
              <Input
                id="gen-prep"
                type="number"
                min="0"
                value={maxPrep}
                placeholder={t("generate.max_prep_placeholder")}
                onChange={(e) => setMaxPrep(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="gen-budget">{t("generate.budget_label")}</Label>
            <Input
              id="gen-budget"
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={budget}
              placeholder={t("generate.budget_placeholder")}
              onChange={(e) => setBudget(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">{t("generate.diet_label")}</p>
            <div className="grid grid-cols-2 gap-2">
              {DIETS.map(([key, label]) => (
                <div key={key} className="flex items-center gap-2">
                  <Checkbox
                    id={`gen-${key}`}
                    checked={diets[key]}
                    onCheckedChange={(checked) =>
                      setDiets((prev) => ({ ...prev, [key]: Boolean(checked) }))
                    }
                  />
                  <Label htmlFor={`gen-${key}`} className="cursor-pointer">
                    {t(`generate.${label}`)}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Checkbox
                id="gen-season"
                checked={matchSeason}
                onCheckedChange={(c) => setMatchSeason(Boolean(c))}
              />
              <Label htmlFor="gen-season" className="cursor-pointer">
                {t("generate.season_label")}
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="gen-public"
                checked={includePublic}
                onCheckedChange={(c) => setIncludePublic(Boolean(c))}
              />
              <Label htmlFor="gen-public" className="cursor-pointer">
                {t("generate.public_label")}
              </Label>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {tCommon("cancel")}
          </Button>
          <LoadingButton
            loading={generate.isPending}
            onClick={() => generate.mutate()}
          >
            {t("generate.submit")}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

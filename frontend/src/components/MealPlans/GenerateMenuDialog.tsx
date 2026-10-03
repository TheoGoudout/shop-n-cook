import { useNavigate } from "@tanstack/react-router"
import { Sparkles } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import {
  type GenerateMenuRequest,
  MealPlansService,
  type MenuPreview,
} from "@/client"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCrudMutation } from "@/hooks/useCrudMutation"
import { MenuReview } from "./MenuReview"
import {
  DEFAULT_SCHEDULE,
  scheduleToMealsByWeekday,
  WeeklyMealSchedule,
} from "./WeeklyMealSchedule"

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

/** Batch cooking: how many meals one cooking covers. 1 means no batching. */
const BATCH_PORTIONS = ["1", "2", "3"] as const

function randomSeed(): number {
  return Math.floor(Math.random() * 1_000_000)
}

/**
 * Compose a week of meals, review it, then save it as a plan.
 *
 * Servings and budget are left blank by default and filled in server-side from
 * the user's household settings, so the common case is opening this, pressing
 * Generate, and accepting the menu. The form keeps its values while the dialog
 * is reopened, and every swap or hand-picked recipe in the review step is sent
 * with them, so the preferences hold throughout.
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
  const [schedule, setSchedule] = useState(DEFAULT_SCHEDULE)
  const [batch, setBatch] = useState<string>("1")
  const [preview, setPreview] = useState<MenuPreview | null>(null)
  const [diets, setDiets] = useState<Record<DietKey, boolean>>({
    require_vegan: false,
    require_vegetarian: false,
    require_gluten_free: false,
    require_dairy_free: false,
  })

  const optionalNumber = (value: string) =>
    value.trim() === "" ? null : Number(value)

  // The preferences, sent unchanged with every preview, swap and save.
  const request: GenerateMenuRequest = {
    start_date: start,
    days: Number(days) || 7,
    servings: optionalNumber(servings),
    budget: budget.trim() === "" ? null : budget,
    max_prep_minutes: optionalNumber(maxPrep),
    match_season: matchSeason,
    include_public: includePublic,
    meals_by_weekday: scheduleToMealsByWeekday(schedule),
    batch_portions: Number(batch),
    ...diets,
  }

  const propose = useCrudMutation({
    mutationFn: () =>
      MealPlansService.previewMenu({
        // A fresh seed each time, so generating again after a menu you did
        // not like actually gives you a different one.
        requestBody: { ...request, seed: randomSeed() },
      }),
    onSuccess: setPreview,
  })

  const save = useCrudMutation({
    mutationFn: (menu: MenuPreview) =>
      MealPlansService.generateMenuRoute({
        requestBody: {
          ...request,
          meals: menu.meals.map(({ recipe_id, slots }) => ({
            recipe_id,
            slots,
          })),
        },
      }),
    successMessage: t("generate.success"),
    invalidateKeys: [["meal-plans"]],
    onSuccess: (plan) => {
      setOpen(false)
      setPreview(null)
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
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {preview ? t("review.title") : t("generate.title")}
          </DialogTitle>
          <DialogDescription>
            {preview ? t("review.description") : t("generate.description")}
          </DialogDescription>
        </DialogHeader>

        {preview ? (
          <MenuReview
            preview={preview}
            request={request}
            onPreviewChange={setPreview}
          />
        ) : (
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

            <WeeklyMealSchedule value={schedule} onChange={setSchedule} />

            <div className="space-y-1.5">
              <Label htmlFor="gen-batch">{t("generate.batch_label")}</Label>
              <Select value={batch} onValueChange={setBatch}>
                <SelectTrigger id="gen-batch" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {BATCH_PORTIONS.map((portions) => (
                    <SelectItem key={portions} value={portions}>
                      {t(`generate.batch_${portions}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {t("generate.batch_help")}
              </p>
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
                        setDiets((prev) => ({
                          ...prev,
                          [key]: Boolean(checked),
                        }))
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
        )}

        <DialogFooter>
          {preview ? (
            <>
              <Button variant="outline" onClick={() => setPreview(null)}>
                {tCommon("back")}
              </Button>
              <Button
                variant="outline"
                disabled={propose.isPending}
                onClick={() => propose.mutate()}
              >
                {t("review.regenerate")}
              </Button>
              <LoadingButton
                loading={save.isPending}
                onClick={() => save.mutate(preview)}
              >
                {t("review.create")}
              </LoadingButton>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => setOpen(false)}>
                {tCommon("cancel")}
              </Button>
              <LoadingButton
                loading={propose.isPending}
                disabled={schedule.every((choice) => choice === "none")}
                onClick={() => propose.mutate()}
              >
                {t("generate.submit")}
              </LoadingButton>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

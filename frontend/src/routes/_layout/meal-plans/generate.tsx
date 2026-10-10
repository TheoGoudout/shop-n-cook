import { useMutation } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import {
  AlertTriangle,
  ArrowLeft,
  RefreshCw,
  Shuffle,
  Sparkles,
  X,
} from "lucide-react"
import { type ReactNode, useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import {
  type ApiError,
  type GenerateMenuRequest,
  MealPlansService,
  type MenuPreview,
  type ProposedMealIn,
} from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import {
  MenuBoard,
  type SlotRef,
} from "@/components/MealPlans/generate/MenuBoard"
import { PreferencesPanel } from "@/components/MealPlans/generate/PreferencesPanel"
import {
  plansAnyMeal,
  toRequest,
  useMenuPreferences,
} from "@/components/MealPlans/generate/preferences"
import { RecipePickerDialog } from "@/components/MealPlans/generate/RecipePickerDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { useCrudMutation } from "@/hooks/useCrudMutation"
import { APP_NAME } from "@/lib/config"
import { formatMoney } from "@/lib/money"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout/meal-plans/generate")({
  component: GenerateMenuPage,
  head: () => ({
    meta: [{ title: `Generate a menu - ${APP_NAME}` }],
  }),
})

/** Wait after the last portion change before re-pricing the menu. */
const REPRICE_DELAY_MS = 400

function randomSeed(): number {
  return Math.floor(Math.random() * 1_000_000)
}

function datesOf(start: string, days: number): string[] {
  const first = new Date(`${start}T00:00:00`)
  if (Number.isNaN(first.getTime())) return []
  return Array.from({ length: days }, (_, i) => {
    const day = new Date(first)
    day.setDate(first.getDate() + i)
    const local = new Date(day.getTime() - day.getTimezoneOffset() * 60_000)
    return local.toISOString().slice(0, 10)
  })
}

function mealsOf(preview: MenuPreview): ProposedMealIn[] {
  return preview.meals.map(({ recipe_id, slots }) => ({ recipe_id, slots }))
}

/** What makes two requests compose different menus (the name does not). */
function requestKey(request: GenerateMenuRequest): string {
  return JSON.stringify({ ...request, name: null })
}

function GenerateMenuPage() {
  const { t } = useTranslation("mealPlans")
  const { t: tCommon, i18n } = useTranslation("common")
  const navigate = useNavigate()

  const { preferences, update } = useMenuPreferences()
  const request = toRequest(preferences)
  const canGenerate = plansAnyMeal(preferences)

  const [preview, setPreview] = useState<MenuPreview | null>(null)
  /** The request the shown menu was composed from, to spot stale menus. */
  const [composedWith, setComposedWith] = useState<GenerateMenuRequest | null>(
    null,
  )
  /** Whether an AI balanced the composed menu; swaps afterwards keep it. */
  const [aiBalanced, setAiBalanced] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [picking, setPicking] = useState<number | null>(null)

  // Every change to the menu bumps the version; a response for an older
  // version is dropped, so a slow re-price never undoes a newer swap.
  const version = useRef(0)
  const repriceTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const compose = useMutation<MenuPreview, ApiError, GenerateMenuRequest>({
    mutationFn: (body) =>
      MealPlansService.previewMenu({
        // A fresh seed each time, so generating again after a menu you did
        // not like actually gives you a different one.
        requestBody: { ...body, seed: randomSeed() },
      }),
    onMutate: () => {
      version.current += 1
      clearTimeout(repriceTimer.current)
    },
    onSuccess: (next, body) => {
      setPreview(next)
      setComposedWith(body)
      setAiBalanced(next.ai_balanced ?? false)
      setSelected(new Set())
    },
  })

  const rework = useCrudMutation({
    mutationFn: ({
      meals,
      replace,
    }: {
      meals: ProposedMealIn[]
      replace: number[]
      version: number
    }) =>
      MealPlansService.previewMenu({
        requestBody: { ...request, seed: randomSeed(), meals, replace },
      }),
    onSuccess: (next, variables) => {
      if (variables.version !== version.current) return
      setPreview(next)
      if (variables.replace.length > 0) setSelected(new Set())
    },
  })

  const defaultName = t("generate.default_name", {
    date: new Date(`${preferences.start}T00:00:00`).toLocaleDateString(
      i18n.language,
      { day: "numeric", month: "long" },
    ),
  })

  const save = useCrudMutation({
    mutationFn: (menu: MenuPreview) =>
      MealPlansService.generateMenuRoute({
        requestBody: {
          ...request,
          name: request.name ?? defaultName,
          meals: mealsOf(menu),
        },
      }),
    successMessage: t("generate.success"),
    invalidateKeys: [["meal-plans"]],
    onSuccess: (plan) =>
      navigate({ to: "/meal-plans/$id", params: { id: plan.id } }),
  })

  // Propose a first menu straight away: most weeks, that is all it takes.
  // Deferred and cancelled on cleanup: a mutation started during a mount that
  // StrictMode immediately undoes would leave this page's observer pending.
  // biome-ignore lint/correctness/useExhaustiveDependencies: once, on arrival
  useEffect(() => {
    if (!canGenerate) return
    const timer = setTimeout(() => compose.mutate(request))
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => () => clearTimeout(repriceTimer.current), [])

  const change = (meals: ProposedMealIn[], replace: number[]) => {
    clearTimeout(repriceTimer.current)
    version.current += 1
    rework.mutate({ meals, replace, version: version.current })
  }

  const swap = (meals: number[]) => {
    if (preview) change(mealsOf(preview), meals)
  }

  const choose = (meal: number, recipeId: string) => {
    if (!preview) return
    setPicking(null)
    change(
      mealsOf(preview).map((m, i) =>
        i === meal ? { ...m, recipe_id: recipeId } : m,
      ),
      [],
    )
  }

  /** Show the new portions at once; re-price once the clicking stops. */
  const changeServings = ({ meal, portion }: SlotRef, servings: number) => {
    if (!preview) return
    const next: MenuPreview = {
      ...preview,
      meals: preview.meals.map((m, i) => {
        if (i !== meal) return m
        const slots = m.slots.map((s, j) =>
          j === portion ? { ...s, servings } : s,
        )
        return {
          ...m,
          slots,
          total_servings: slots.reduce(
            (sum, s) => sum + (s.servings ?? m.servings),
            0,
          ),
        }
      }),
    }
    setPreview(next)
    version.current += 1
    const current = version.current
    clearTimeout(repriceTimer.current)
    repriceTimer.current = setTimeout(
      () =>
        rework.mutate({ meals: mealsOf(next), replace: [], version: current }),
      REPRICE_DELAY_MS,
    )
  }

  const toggleSelect = (meal: number, on: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (on) next.add(meal)
      else next.delete(meal)
      return next
    })

  const stale =
    preview !== null &&
    composedWith !== null &&
    requestKey(composedWith) !== requestKey(request)
  const busy = compose.isPending || rework.isPending || save.isPending
  const pickingMeal = picking !== null ? preview?.meals[picking] : undefined

  return (
    <div className="w-full space-y-6">
      <Link
        to="/meal-plans"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {tCommon("back")}
      </Link>

      <PageHeader
        title={t("generate.title")}
        subtitle={t("generate.description")}
      />

      <div className="grid items-start gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Card className="py-5">
          <CardContent className="space-y-6 px-5">
            <PreferencesPanel value={preferences} onChange={update} />
            <LoadingButton
              className="w-full"
              loading={compose.isPending}
              disabled={!canGenerate}
              onClick={() => compose.mutate(request)}
            >
              {preview ? <RefreshCw /> : <Sparkles />}
              {preview ? t("review.regenerate") : t("generate.submit")}
            </LoadingButton>
            {!canGenerate && (
              <p className="text-center text-xs text-muted-foreground">
                {t("generate.no_meals_selected")}
              </p>
            )}
          </CardContent>
        </Card>

        <div className="min-w-0 space-y-4">
          {stale && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/40 bg-primary/5 px-3 py-2 text-sm">
              <span>{t("review.stale")}</span>
              <Button
                size="sm"
                variant="outline"
                disabled={busy || !canGenerate}
                onClick={() => compose.mutate(request)}
              >
                <RefreshCw />
                {t("review.regenerate")}
              </Button>
            </div>
          )}

          {compose.isError && !compose.isPending && (
            <ComposeError
              hasMenu={preview !== null}
              onRetry={() => compose.mutate(request)}
            />
          )}

          {!preview && compose.isPending && <BoardSkeleton />}

          {!preview && !compose.isPending && !compose.isError && (
            <div className="rounded-lg border border-dashed p-10 text-center text-muted-foreground">
              {t("generate.no_meals_selected")}
            </div>
          )}

          {preview && (
            <>
              {composedWith?.use_ai && (
                <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Sparkles className="h-4 w-4 shrink-0 text-primary" />
                  {aiBalanced
                    ? t("review.ai_balanced")
                    : t("review.ai_unavailable")}
                </p>
              )}
              <div className="flex min-h-9 flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-muted-foreground">
                  {selected.size > 0
                    ? t("review.selected", { count: selected.size })
                    : t("review.hint")}
                </p>
                {selected.size > 0 && (
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setSelected(new Set())}
                    >
                      <X />
                      {t("review.clear_selection")}
                    </Button>
                    <Button
                      size="sm"
                      disabled={busy}
                      onClick={() => swap([...selected])}
                    >
                      <Shuffle />
                      {t("review.swap_selected", { count: selected.size })}
                    </Button>
                  </div>
                )}
              </div>

              <div
                className={cn(
                  "transition-opacity",
                  compose.isPending && "pointer-events-none opacity-50",
                )}
              >
                <MenuBoard
                  preview={preview}
                  days={datesOf(
                    composedWith?.start_date ?? preferences.start,
                    composedWith?.days ?? preferences.days,
                  )}
                  selected={selected}
                  busy={busy}
                  onToggleSelect={toggleSelect}
                  onSwap={(meal) => swap([meal])}
                  onChoose={setPicking}
                  onServings={changeServings}
                />
              </div>

              <SummaryBar
                preview={preview}
                name={preferences.name}
                defaultName={defaultName}
                onNameChange={(name) => update({ name })}
                repricing={rework.isPending}
                saving={save.isPending}
                disabled={busy || stale}
                onSave={() => save.mutate(preview)}
              />
            </>
          )}
        </div>
      </div>

      <RecipePickerDialog
        open={picking !== null}
        onOpenChange={(open) => !open && setPicking(null)}
        request={request}
        mealType={pickingMeal?.slots[0].meal_type}
        currentRecipeId={pickingMeal?.recipe_id}
        context={
          pickingMeal
            ? `${new Date(
                `${pickingMeal.slots[0].entry_date}T00:00:00`,
              ).toLocaleDateString(i18n.language, {
                weekday: "long",
              })} · ${t(`meal_types.${pickingMeal.slots[0].meal_type}`)}`
            : ""
        }
        onPick={(recipeId) => picking !== null && choose(picking, recipeId)}
      />
    </div>
  )
}

function ComposeError({
  hasMenu,
  onRetry,
}: {
  hasMenu: boolean
  onRetry: () => void
}) {
  const { t } = useTranslation("mealPlans")
  return (
    <div className="flex items-start gap-3 rounded-lg border border-destructive/40 p-4">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
      <div className="flex-1 space-y-1">
        <p className="font-medium">{t("review.error_title")}</p>
        <p className="text-sm text-muted-foreground">
          {t("review.error_hint")}
        </p>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button size="sm" variant="outline" onClick={onRetry}>
            <RefreshCw />
            {t("review.retry")}
          </Button>
          {!hasMenu && (
            <Button size="sm" variant="ghost" asChild>
              <Link to="/recipes">{t("review.browse_recipes")}</Link>
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

function BoardSkeleton() {
  return (
    <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
      {Array.from({ length: 6 }, (_, i) => (
        <Skeleton key={i} className="h-36 w-full" />
      ))}
    </div>
  )
}

function SummaryBar({
  preview,
  name,
  defaultName,
  onNameChange,
  repricing,
  saving,
  disabled,
  onSave,
}: {
  preview: MenuPreview
  name: string
  defaultName: string
  onNameChange: (name: string) => void
  repricing: boolean
  saving: boolean
  disabled: boolean
  onSave: () => void
}) {
  const { t } = useTranslation("mealPlans")
  const { i18n } = useTranslation("common")

  const meals = preview.meals.reduce((n, m) => n + m.slots.length, 0)
  const portions = preview.meals.reduce((n, m) => n + m.total_servings, 0)
  const total = formatMoney(
    preview.estimated_total,
    preview.currency,
    i18n.language,
  )
  const budget = formatMoney(preview.budget, preview.currency, i18n.language)
  const overBudget =
    preview.budget != null &&
    preview.estimated_total != null &&
    Number(preview.estimated_total) > Number(preview.budget)

  return (
    <div className="sticky bottom-0 z-10 -mx-1 rounded-t-lg border bg-background/95 p-3 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <dl className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
          <Stat label={t("review.stat_recipes")} value={preview.meals.length} />
          <Stat label={t("review.stat_meals")} value={meals} />
          <Stat label={t("review.stat_portions")} value={portions} />
          <Stat
            label={t("review.stat_cost")}
            value={
              <span
                className={cn(
                  "transition-opacity",
                  repricing && "opacity-50",
                  overBudget && "text-destructive",
                )}
              >
                {total ?? "—"}
                {budget && (
                  <span className="font-normal text-muted-foreground">
                    {" "}
                    / {budget}
                  </span>
                )}
              </span>
            }
          />
          {preview.unpriced_meal_count ? (
            <p className="self-end text-xs text-muted-foreground">
              {t("review.unpriced", { count: preview.unpriced_meal_count })}
            </p>
          ) : null}
        </dl>
        <div className="flex flex-1 basis-72 items-center gap-2">
          <Input
            aria-label={t("add.name_label")}
            value={name}
            placeholder={defaultName}
            onChange={(e) => onNameChange(e.target.value)}
            className="h-9"
          />
          <LoadingButton loading={saving} disabled={disabled} onClick={onSave}>
            {t("review.create")}
          </LoadingButton>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

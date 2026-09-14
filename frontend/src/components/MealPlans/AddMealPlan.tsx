import { useNavigate } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { MealPlansService } from "@/client"
import { Button } from "@/components/ui/button"
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

/** ISO date, n days from today. */
function isoDate(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().slice(0, 10)
}

export function AddMealPlan() {
  const { t } = useTranslation("mealPlans")
  const { t: tCommon } = useTranslation("common")
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const [name, setName] = useState("")
  // Defaults to the coming week, which is what a plan almost always is.
  const [start, setStart] = useState(isoDate())
  const [end, setEnd] = useState(isoDate(6))

  const mutation = useCrudMutation({
    mutationFn: () =>
      MealPlansService.createMealPlan({
        requestBody: { name, start_date: start, end_date: end },
      }),
    successMessage: t("add.success"),
    invalidateKeys: [["meal-plans"]],
    onSuccess: (plan) => {
      setOpen(false)
      setName("")
      navigate({ to: "/meal-plans/$id", params: { id: plan.id } })
    },
  })

  const invalidRange = end < start

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus />
          {t("add.trigger")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("add.title")}</DialogTitle>
          <DialogDescription>{t("add.description")}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="plan-name">{t("add.name_label")}</Label>
            <Input
              id="plan-name"
              value={name}
              placeholder={t("add.name_placeholder")}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="plan-start">{t("add.start_label")}</Label>
              <Input
                id="plan-start"
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="plan-end">{t("add.end_label")}</Label>
              <Input
                id="plan-end"
                type="date"
                value={end}
                min={start}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {tCommon("cancel")}
          </Button>
          <LoadingButton
            loading={mutation.isPending}
            disabled={name.trim() === "" || invalidRange}
            onClick={() => mutation.mutate()}
          >
            {tCommon("create")}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

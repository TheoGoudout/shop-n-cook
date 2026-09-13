import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { type UserSettingsPublic, UserSettingsService } from "@/client"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

/** Currencies the app formats costs in. */
const CURRENCIES = ["EUR", "GBP", "USD", "CHF", "CAD"] as const

export function HouseholdSettings() {
  const { t } = useTranslation("settings")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: settings, isLoading } = useQuery({
    queryKey: ["user-settings"],
    queryFn: () => UserSettingsService.readUserSettings(),
  })

  const [householdSize, setHouseholdSize] = useState<string>("")
  const [frequency, setFrequency] = useState<string>("")
  const [budget, setBudget] = useState<string | null>(null)
  const [currency, setCurrency] = useState<string>("")

  // Sync local state when data loads
  const currentSize = householdSize || String(settings?.household_size ?? 2)
  const currentFreq = (frequency || settings?.shopping_frequency) ?? "weekly"
  // An empty budget field is meaningful — it clears the budget — so the local
  // value is only treated as unset while it is still null.
  const currentBudget = budget ?? settings?.budget_amount ?? ""
  const currentCurrency = currency || (settings?.currency ?? "EUR")

  const mutation = useMutation({
    mutationFn: () =>
      UserSettingsService.updateUserSettings({
        requestBody: {
          household_size: Number(currentSize),
          shopping_frequency:
            currentFreq as UserSettingsPublic["shopping_frequency"],
          budget_amount:
            String(currentBudget).trim() === "" ? null : String(currentBudget),
          currency: currentCurrency,
        },
      }),
    onSuccess: () => {
      showSuccessToast(t("household.success"))
      queryClient.invalidateQueries({ queryKey: ["user-settings"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  if (isLoading) {
    return (
      <p className="text-sm text-muted-foreground">
        {t("common:loading", { defaultValue: "Loading…" })}
      </p>
    )
  }

  const frequencyOptions = ["weekly", "biweekly", "monthly"] as const

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("household.title")}</CardTitle>
        <CardDescription>{t("household.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-2">
            <p className="text-sm font-medium">{t("household.size_label")}</p>
            <Select value={currentSize} onValueChange={setHouseholdSize}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n === 1
                      ? t("household.person", { count: n })
                      : t("household.people", { count: n })}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t("household.size_hint")}
            </p>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">
              {t("household.frequency_label")}
            </p>
            <Select value={currentFreq} onValueChange={setFrequency}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {frequencyOptions.map((val) => (
                  <SelectItem key={val} value={val}>
                    {t(`household.frequency.${val}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t("household.frequency_hint")}
            </p>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">{t("household.budget_label")}</p>
            <Input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={currentBudget}
              placeholder={t("household.budget_placeholder")}
              onChange={(e) => setBudget(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {t("household.budget_hint")}
            </p>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">
              {t("household.currency_label")}
            </p>
            <Select value={currentCurrency} onValueChange={setCurrency}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CURRENCIES.map((code) => (
                  <SelectItem key={code} value={code}>
                    {code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t("household.currency_hint")}
            </p>
          </div>
        </div>

        <LoadingButton
          onClick={() => mutation.mutate()}
          loading={mutation.isPending}
        >
          {t("household.save")}
        </LoadingButton>
      </CardContent>
    </Card>
  )
}

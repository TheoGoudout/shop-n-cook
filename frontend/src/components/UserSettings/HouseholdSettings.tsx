import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { type UserSettingsPublic, UserSettingsService } from "@/client"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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

const FREQUENCY_LABELS: Record<string, string> = {
  weekly: "Weekly",
  biweekly: "Every two weeks",
  monthly: "Monthly",
}

export function HouseholdSettings() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: settings, isLoading } = useQuery({
    queryKey: ["user-settings"],
    queryFn: () => UserSettingsService.readUserSettings(),
  })

  const [householdSize, setHouseholdSize] = useState<string>("")
  const [frequency, setFrequency] = useState<string>("")

  // Sync local state when data loads
  const currentSize = householdSize || String(settings?.household_size ?? 2)
  const currentFreq = (frequency || settings?.shopping_frequency) ?? "weekly"

  const mutation = useMutation({
    mutationFn: () =>
      UserSettingsService.updateUserSettings({
        requestBody: {
          household_size: Number(currentSize),
          shopping_frequency:
            currentFreq as UserSettingsPublic["shopping_frequency"],
        },
      }),
    onSuccess: () => {
      showSuccessToast("Household settings saved")
      queryClient.invalidateQueries({ queryKey: ["user-settings"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Household</CardTitle>
        <CardDescription>
          These settings are used as defaults when planning recipes and shopping
          lists.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-2">
            <p className="text-sm font-medium">Household size</p>
            <Select value={currentSize} onValueChange={setHouseholdSize}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} {n === 1 ? "person" : "people"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Used as the default serving count when adding recipes to a
              shopping list.
            </p>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Shopping frequency</p>
            <Select value={currentFreq} onValueChange={setFrequency}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(FREQUENCY_LABELS).map(([val, label]) => (
                  <SelectItem key={val} value={val}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Determines the default date range when creating a new shopping
              list.
            </p>
          </div>
        </div>

        <LoadingButton
          onClick={() => mutation.mutate()}
          loading={mutation.isPending}
        >
          Save settings
        </LoadingButton>
      </CardContent>
    </Card>
  )
}

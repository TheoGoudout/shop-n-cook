import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { RefreshCw } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { RecipesService } from "@/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { APP_NAME } from "@/lib/config"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/admin/recipes")({
  component: RecipesAdminPage,
  head: () => ({
    meta: [{ title: `Recipes - Admin - ${APP_NAME}` }],
  }),
})

const STALE_IMPORTS_KEY = ["stale-imports"]
const DEFAULT_BATCH = 20
const MAX_BATCH = 200

function Stat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 text-2xl font-semibold tabular-nums">
        {value === undefined ? <Skeleton className="h-8 w-16" /> : value}
      </CardContent>
    </Card>
  )
}

/**
 * Reimport, a batch at a time, the recipes an older import pipeline produced.
 *
 * A batch runs in the background on the server; while it does, the counts are
 * polled, so the stale count going down is the progress bar.
 */
function RecipesAdminPage() {
  const { t, i18n } = useTranslation("admin")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [batch, setBatch] = useState(DEFAULT_BATCH)

  const { data } = useQuery({
    queryKey: STALE_IMPORTS_KEY,
    queryFn: () => RecipesService.readStaleImports(),
    refetchInterval: (query) => (query.state.data?.running ? 5000 : false),
  })

  const mutation = useMutation({
    mutationFn: () =>
      RecipesService.reimportStaleImports({
        requestBody: { limit: batch, language: i18n.language },
      }),
    onSuccess: (status) => {
      queryClient.setQueryData(STALE_IMPORTS_KEY, status)
      showSuccessToast(t("recipes.started"))
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: STALE_IMPORTS_KEY }),
  })

  const running = data?.running ?? false
  const nothingStale = data !== undefined && data.stale_count === 0
  const validBatch = batch >= 1 && batch <= MAX_BATCH

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("recipes.title")}
        </h1>
        <p className="text-muted-foreground">{t("recipes.subtitle")}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Stat label={t("recipes.version")} value={data?.import_version} />
        <Stat label={t("recipes.stale")} value={data?.stale_count} />
        <Stat label={t("recipes.failed")} value={data?.failed_count} />
      </div>

      <div className="flex flex-col gap-2 text-sm text-muted-foreground">
        <p>{t("recipes.explain_crawled")}</p>
        <p>{t("recipes.explain_users")}</p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reimport-batch">{t("recipes.batch_size")}</Label>
          <Input
            id="reimport-batch"
            type="number"
            min={1}
            max={MAX_BATCH}
            className="w-28"
            value={batch}
            onChange={(e) => setBatch(Number(e.target.value))}
          />
        </div>
        <LoadingButton
          loading={mutation.isPending || running}
          disabled={nothingStale || !validBatch}
          onClick={() => mutation.mutate()}
        >
          <RefreshCw />
          {running
            ? t("recipes.running")
            : t("recipes.reimport", {
                count: data?.stale_count
                  ? Math.min(batch, data.stale_count)
                  : batch,
              })}
        </LoadingButton>
      </div>
      {nothingStale && (
        <p className="text-sm text-muted-foreground">
          {t("recipes.up_to_date")}
        </p>
      )}
    </div>
  )
}

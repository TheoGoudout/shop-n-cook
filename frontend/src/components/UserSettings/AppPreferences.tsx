import { useTranslation } from "react-i18next"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useUnitSystem } from "@/hooks/useUnitSystem"
import type { UnitSystem } from "@/lib/units"

const LANGUAGE_CODES = ["en", "fr"] as const

export function AppPreferences() {
  const { t, i18n } = useTranslation("settings")
  const { unitSystem, setUnitSystem } = useUnitSystem()

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("preferences.title")}</CardTitle>
        <CardDescription>{t("preferences.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-2">
            <p className="text-sm font-medium">
              {t("preferences.language_label")}
            </p>
            <Select
              value={i18n.language?.split("-")[0] ?? "en"}
              onValueChange={(lang) => i18n.changeLanguage(lang)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGE_CODES.map((code) => (
                  <SelectItem key={code} value={code}>
                    {t(`preferences.languages.${code}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">
              {t("preferences.unit_system_label")}
            </p>
            <Select
              value={unitSystem}
              onValueChange={(v) => setUnitSystem(v as UnitSystem)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="metric">
                  {t("preferences.unit_metric")}
                </SelectItem>
                <SelectItem value="imperial">
                  {t("preferences.unit_imperial")}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

import { useTranslation } from "react-i18next"
import { Appearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  const { t } = useTranslation("common")

  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="bg-sidebar relative hidden lg:flex lg:flex-col lg:items-center lg:justify-center gap-4">
        <Logo variant="full" asLink={false} />
        <p className="text-sm text-muted-foreground text-center max-w-48 leading-relaxed">
          {t("tagline")}
        </p>
      </div>
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex justify-end">
          <Appearance />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs">{children}</div>
        </div>
        <Footer />
      </div>
    </div>
  )
}

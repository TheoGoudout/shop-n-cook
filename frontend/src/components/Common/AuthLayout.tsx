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
      <div className="relative hidden overflow-hidden bg-[linear-gradient(140deg,var(--tomato),oklch(0.68_0.18_50)_55%,var(--saffron))] lg:flex lg:flex-col lg:items-center lg:justify-center gap-5">
        <div
          aria-hidden="true"
          className="absolute -left-24 -top-24 size-96 rounded-full bg-white/10"
        />
        <div
          aria-hidden="true"
          className="absolute -bottom-32 -right-16 size-[28rem] rounded-full bg-white/10"
        />
        <Logo
          variant="full"
          asLink={false}
          className="relative text-white [&_span]:text-4xl [&_svg]:size-12 [&_svg]:text-white"
        />
        <p className="relative font-display text-2xl italic text-white/90 text-center max-w-xs leading-snug">
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

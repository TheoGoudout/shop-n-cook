import { Appearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { AuthShowcase } from "./AuthShowcase"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <AuthShowcase />
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex items-center justify-between lg:justify-end">
          {/* The showcase carries the brand on wide screens; below it, this does */}
          <Logo
            variant="full"
            asLink={false}
            className="lg:hidden [&_span]:text-lg"
          />
          <Appearance />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs sm:max-w-sm">{children}</div>
        </div>
        <Footer />
      </div>
    </div>
  )
}

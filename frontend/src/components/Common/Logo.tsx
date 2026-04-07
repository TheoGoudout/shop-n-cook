import { Link } from "@tanstack/react-router"

import { useTheme } from "@/components/theme-provider"
import { APP_NAME } from "@/lib/config"
import { cn } from "@/lib/utils"
import icon from "/assets/images/icon.svg"
import iconDark from "/assets/images/icon-dark.svg"
import logo from "/assets/images/logo.svg"
import logoDark from "/assets/images/logo-dark.svg"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === "dark"

  const fullLogo = isDark ? logoDark : logo
  const iconLogo = isDark ? iconDark : icon

  const content =
    variant === "responsive" ? (
      <>
        <img
          src={fullLogo}
          alt={APP_NAME}
          className={cn(
            "h-6 w-auto group-data-[collapsible=icon]:hidden",
            className,
          )}
        />
        <img
          src={iconLogo}
          alt={APP_NAME}
          className={cn(
            "size-5 hidden group-data-[collapsible=icon]:block",
            className,
          )}
        />
      </>
    ) : (
      <img
        src={variant === "full" ? fullLogo : iconLogo}
        alt={APP_NAME}
        className={cn(variant === "full" ? "h-6 w-auto" : "size-5", className)}
      />
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}

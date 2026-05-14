import { Link } from "@tanstack/react-router"
import { ChefHat } from "lucide-react"

import { APP_NAME } from "@/lib/config"
import { cn } from "@/lib/utils"

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
  const fullContent = (
    <div className={cn("flex items-center gap-2.5", className)}>
      <ChefHat className="h-6 w-6 shrink-0 text-primary drop-shadow-sm" />
      <span className="font-display font-semibold text-base tracking-tight leading-none">
        {APP_NAME}
      </span>
    </div>
  )

  const iconContent = (
    <ChefHat className={cn("size-5 text-primary drop-shadow-sm", className)} />
  )

  const content =
    variant === "responsive" ? (
      <>
        <div
          className={cn(
            "flex items-center gap-2.5 group-data-[collapsible=icon]:hidden",
            className,
          )}
        >
          <ChefHat className="h-6 w-6 shrink-0 text-primary drop-shadow-sm" />
          <span className="font-display font-semibold text-base tracking-tight leading-none">
            {APP_NAME}
          </span>
        </div>
        <ChefHat
          className={cn(
            "size-5 hidden group-data-[collapsible=icon]:block text-primary drop-shadow-sm",
            className,
          )}
        />
      </>
    ) : variant === "full" ? (
      fullContent
    ) : (
      iconContent
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}

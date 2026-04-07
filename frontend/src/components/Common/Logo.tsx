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
    <div className={cn("flex items-center gap-2", className)}>
      <ChefHat className="h-5 w-5 shrink-0 text-primary" />
      <span className="font-bold text-sm tracking-tight">{APP_NAME}</span>
    </div>
  )

  const iconContent = (
    <ChefHat className={cn("size-5 text-primary", className)} />
  )

  const content =
    variant === "responsive" ? (
      <>
        <div className={cn("flex items-center gap-2 group-data-[collapsible=icon]:hidden", className)}>
          <ChefHat className="h-5 w-5 shrink-0 text-primary" />
          <span className="font-bold text-sm tracking-tight">{APP_NAME}</span>
        </div>
        <ChefHat
          className={cn(
            "size-5 hidden group-data-[collapsible=icon]:block text-primary",
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

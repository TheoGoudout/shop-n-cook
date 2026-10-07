import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

/** What a list page shows before its first item exists. */
export function EmptyListState({
  icon: Icon,
  title,
  subtitle,
  children,
}: {
  icon: LucideIcon
  title: string
  subtitle: string
  /** An action to get started, under the text. */
  children?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12">
      <div className="rounded-full bg-muted p-4 mb-4">
        <Icon className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-muted-foreground">{subtitle}</p>
      {children}
    </div>
  )
}

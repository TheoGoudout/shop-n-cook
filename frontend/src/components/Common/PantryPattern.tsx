import {
  Apple,
  Carrot,
  Cherry,
  Citrus,
  CookingPot,
  Croissant,
  Egg,
  Fish,
  type LucideIcon,
  Pizza,
  Salad,
  Soup,
  Wheat,
} from "lucide-react"

import { cn } from "@/lib/utils"

// Hand-placed rather than random, so the scatter looks composed and never
// shifts between renders. Positions are percentages of the container.
const ITEMS: {
  icon: LucideIcon
  x: number
  y: number
  size: number
  rotate: number
  tone: string
}[] = [
  { icon: Carrot, x: 6, y: 10, size: 44, rotate: -18, tone: "--tomato" },
  { icon: Cherry, x: 30, y: 4, size: 32, rotate: 12, tone: "--plum" },
  { icon: Croissant, x: 58, y: 9, size: 48, rotate: -8, tone: "--saffron" },
  { icon: Salad, x: 84, y: 6, size: 40, rotate: 14, tone: "--basil" },
  { icon: Egg, x: 14, y: 36, size: 30, rotate: 20, tone: "--saffron" },
  { icon: Fish, x: 88, y: 34, size: 42, rotate: -24, tone: "--basil" },
  { icon: Soup, x: 4, y: 62, size: 46, rotate: 6, tone: "--tomato" },
  { icon: Citrus, x: 92, y: 62, size: 34, rotate: -10, tone: "--saffron" },
  { icon: Wheat, x: 22, y: 86, size: 40, rotate: -28, tone: "--saffron" },
  { icon: Apple, x: 48, y: 90, size: 34, rotate: 10, tone: "--tomato" },
  { icon: Pizza, x: 72, y: 84, size: 44, rotate: 18, tone: "--plum" },
  { icon: CookingPot, x: 44, y: 46, size: 38, rotate: -6, tone: "--basil" },
]

/**
 * A scatter of food icons in the pantry colours, like magnets on a fridge.
 * Purely decorative: place it behind content in a `relative` container.
 */
export function PantryPattern({
  className,
  opacity = 0.35,
}: {
  className?: string
  opacity?: number
}) {
  return (
    <div
      aria-hidden="true"
      className={cn("pointer-events-none absolute inset-0", className)}
      style={{ opacity }}
    >
      {ITEMS.map(({ icon: Icon, x, y, size, rotate, tone }) => (
        <Icon
          key={`${x}-${y}`}
          className="absolute"
          strokeWidth={1.5}
          style={{
            left: `${x}%`,
            top: `${y}%`,
            width: size,
            height: size,
            transform: `translate(-50%, -50%) rotate(${rotate}deg)`,
            color: `var(${tone})`,
          }}
        />
      ))}
    </div>
  )
}

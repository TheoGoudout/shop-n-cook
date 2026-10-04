import { ChefHat } from "lucide-react"
import { useState } from "react"

import { cn } from "@/lib/utils"

const TONES = ["--tomato", "--saffron", "--basil", "--plum"]

/** A stable pantry colour per recipe, so a recipe keeps its tile colour. */
function toneFor(seed: string): string {
  let hash = 0
  for (const ch of seed) hash = (hash * 31 + ch.charCodeAt(0)) | 0
  return `var(${TONES[Math.abs(hash) % TONES.length]})`
}

/**
 * The recipe's photo, or — when it has none or it fails to load — a tile in
 * one of the pantry colours with a chef's hat, so a grid never shows a hole.
 */
export function RecipeCover({
  recipe,
  className,
}: {
  recipe: { id: string; title: string; image_url?: string | null }
  className?: string
}) {
  const [failed, setFailed] = useState(false)
  const tone = toneFor(recipe.id)

  if (recipe.image_url && !failed) {
    return (
      <img
        src={recipe.image_url}
        alt=""
        loading="lazy"
        onError={() => setFailed(true)}
        className={cn("size-full object-cover", className)}
      />
    )
  }

  return (
    <div
      aria-hidden="true"
      className={cn("flex size-full items-center justify-center", className)}
      style={{
        backgroundColor: `color-mix(in oklch, ${tone} 22%, var(--card))`,
        color: `color-mix(in oklch, ${tone} 85%, var(--foreground))`,
      }}
    >
      <ChefHat className="size-10 opacity-80" strokeWidth={1.5} />
    </div>
  )
}

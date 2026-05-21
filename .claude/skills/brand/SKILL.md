---
name: brand
description: Apply Shop'n'Cook's visual identity (OKLCH semantic tokens, typography, light/dark mode). Use when styling new UI, choosing colors, or reviewing visual changes.
---

# Visual identity

Authoritative source: `VISUAL_IDENTITY.md` at the repo root. This skill
summarizes the rules most relevant to day-to-day frontend work.

## Color: never hardcode hex

Colors are defined as OKLCH semantic tokens in
`frontend/src/index.css` (or wherever the Tailwind v4 theme block lives)
and exposed as Tailwind utility classes. **Always use the semantic
class**, not a raw hex or `text-[#abc]`-style arbitrary value.

Core semantic tokens:

| Token | Use |
|-------|-----|
| `primary` / `primary-foreground` | Saffron amber — call-to-action buttons, active links |
| `secondary` / `secondary-foreground` | Muted neutral — secondary buttons, badges |
| `accent` / `accent-foreground` | Herb green — highlights, success states |
| `destructive` / `destructive-foreground` | Warm red — destructive actions, errors |
| `muted` / `muted-foreground` | Background tints, placeholder text |
| `background` / `foreground` | Page background and primary text |
| `card` / `card-foreground` | Card surfaces |
| `border` | Outlines, dividers |
| `ring` | Focus ring (paired with `focus-visible:ring-ring`) |
| `input` | Input borders |

Use them with Tailwind: `bg-primary`, `text-primary-foreground`,
`hover:bg-primary/90`, `border-destructive/50`, etc.

## Light and dark mode

The `ThemeProvider` (`frontend/src/components/theme-provider.tsx`) wraps
the app with `next-themes`. Tokens swap automatically — never write
`dark:bg-[#222]` style overrides. If a component needs darker-than-card
in dark mode, use the existing semantic tokens (`muted`, `secondary`),
or extend the theme block centrally.

## Typography

System font stack. Headings use `font-semibold` or `font-bold`; body
text default weight. Don't introduce new font files without an ADR-style
discussion — adding webfonts has performance implications.

## Icons

Lucide React. Use existing icons rather than introducing a second icon
library. Standard sizes: `h-3 w-3`, `h-4 w-4`, `h-5 w-5`.

## Component primitives

`frontend/src/components/ui/` contains shadcn primitives. Do not
modify them directly — they are regenerated. Instead, compose them in
feature components or extend via Tailwind classNames on the call site.

## Brand voice

Warm, home-centric, lightly playful. The English copy treats the user
as a household cook, not a "user" or "customer". Avoid corporate
jargon ("leverage", "utilize") and avoid emoji in UI strings unless
specifically requested.

## Loading & empty states

- Buttons that trigger async work use `<LoadingButton loading={…} />`.
- Empty states use italicized muted text:
  `<p className="text-sm text-muted-foreground italic">…</p>`.
- Skeletons via shadcn's `<Skeleton />` for content-aware placeholders.

---
name: brand
description: Apply Shop'n'Cook's visual identity (tomato and pantry OKLCH tokens, Fraunces + Plus Jakarta Sans, top-nav layout, light/dark mode). Use when styling new UI, choosing colors, or reviewing visual changes.
---

# Visual identity

Authoritative source: `VISUAL_IDENTITY.md` at the repo root. This skill is
the short version for day-to-day frontend work.

## The feel

Warm, generous, appetising, organised: a sunny market stall, not a
productivity tool. Food photos are the heroes; the chrome is cream paper and
tomato red. One bold moment per screen, the rest calm.

## Colour: tokens only

Tokens live in `frontend/src/index.css` (`:root` light, `.dark` dark) and map
to Tailwind classes. Never hardcode hex, `text-[#…]`, or palette classes like
`bg-green-500`.

| Token | Use |
|-------|-----|
| `primary` (= `tomato`) | Primary buttons, active nav pill, links, focus |
| `saffron`, `basil`, `plum` | Pantry accents: icon chips, placeholder tiles, illustration. Identity only — never status, never chart series |
| `secondary` | Badges, secondary buttons, hover fills |
| `accent` | Sage: menu hover, "vegetarian" |
| `success` / `warning` / `destructive` | Status — always with an icon or a word |
| `muted` / `muted-foreground` | Quiet fills, secondary text |
| `background` / `card` / `foreground` | Linen page, paper cards, espresso text |
| `chart-1`…`chart-5` | Data series, in order |

Tint with `color-mix(in oklch, var(--saffron) 20%, var(--card))` rather than
adding a token. Text on tomato is 4.5:1 — keep it 14px medium or larger.

## Light and dark

`ThemeProvider` (`components/theme-provider.tsx`) toggles `.dark`. Dark mode
is warm cocoa, re-stepped per token; never write `dark:bg-…` colour overrides
when a token covers it.

## Typography

- `font-display` — **Fraunces** (SOFT 100, WONK on) for `h1`–`h3`, recipe
  titles, the wordmark. Applied to `h1`–`h3` automatically.
- `font-sans` — **Plus Jakarta Sans** for everything else (the default).
- Page titles `text-3xl md:text-4xl font-bold tracking-tight`.
- Fonts are bundled from `@fontsource-variable/*`. Never add a Google Fonts
  or other font-CDN link.

## Layout and components

- Top nav (`components/Navigation/TopNav.tsx`) with a bottom tab bar on
  phones; content `max-w-6xl`. There is no sidebar.
- Recipe imagery goes through `RecipeCover` (photo, or a pantry tile when
  missing/broken). Recipe lists are photo-card grids (`RecipeGrid`).
- Decoration: `PantryPattern` (food icons, `aria-hidden`) and the
  `bg-kitchen-glow` utility.
- Radius: cards `rounded-2xl`, heroes `rounded-3xl`, nav items `rounded-full`.
- Hover: cards lift `-translate-y-0.5`; photos `scale-105`.

## Icons

Lucide React only. `size-4` inline, `size-5` in navigation.

## Component primitives

`frontend/src/components/ui/` is shadcn-generated. Do not edit it — compose
in feature components or pass classNames at the call site.

## Brand voice

Warm, home-centric, lightly playful. Talk to a household cook, not a "user".
Avoid corporate jargon and emoji in UI strings.

## Loading & empty states

- Async buttons use `<LoadingButton loading={…} />`.
- Empty states: `<p className="text-sm text-muted-foreground italic">…</p>`.
- Skeletons via shadcn's `<Skeleton />`.

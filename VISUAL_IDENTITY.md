# Shop'n'Cook — Visual Identity

The graphical chart for the web app. The tokens it describes live in
`frontend/src/index.css`; this document says what they are for, so a new
screen fits the others without anyone having to reverse-engineer them.

## Who it is for, and how it should feel

Home cooks and households: people planning the week's meals, collecting
recipes and doing the shopping, often on a phone, often in the kitchen.

**Warm · Generous · Appetising · Organised**

It should feel like a sunny market stall and a well-kept kitchen, not a
productivity tool. Food carries the colour: recipe photos are the heroes,
and the interface around them is cream paper and tomato red. It is organised
without being clinical: rounded shapes, soft shadows, a serif with some
personality.

Tagline: **"Your kitchen, organized."** The sign-in screen says the promise in
full: **"Plan the week. Shop once. Cook happy."**

**Do**
- Show food. A recipe without a photo gets a pantry-coloured tile
  (`RecipeCover`), never an empty box.
- Use one bold moment per screen (the dashboard hero, the active nav pill, a
  primary button) and keep the rest calm.
- Write to a cook, not a "user": "Add to your list", not "Create shopping list
  entity".

**Don't**
- Don't make it grey or blue. Even dark mode is warm brown.
- Don't use the pantry colours to encode data, and don't add new accent hues.
- Don't use emoji in UI strings (the greeting's wave is the one exception).

## Colour

Every colour is an OKLCH token in `frontend/src/index.css` (`:root` for
light, `.dark` for dark), exposed to Tailwind as `bg-<token>`,
`text-<token>`, `border-<token>`. Never hardcode a hex value or a Tailwind
palette class such as `bg-green-500`. The hex values below are approximations
for design tools only.

### Brand: tomato and the pantry

| Token | Light | Dark | Role |
|---|---|---|---|
| `--primary` / `--tomato` | `oklch(0.585 0.19 36)` ≈ `#D44214` | `oklch(0.7 0.17 40)` ≈ `#F37344` | The brand colour: primary buttons, the active nav pill, links, focus rings |
| `--saffron` | `oklch(0.8 0.16 80)` ≈ `#F3B01D` | `oklch(0.82 0.15 82)` | Warmth: the dashboard hero, highlights, the logo on dark surfaces |
| `--basil` | `oklch(0.56 0.13 145)` ≈ `#3B8841` | `oklch(0.7 0.13 145)` | Freshness: ticked items, "in the basket" |
| `--plum` | `oklch(0.5 0.14 350)` ≈ `#9B3B6E` | `oklch(0.68 0.13 350)` | The fourth pantry colour, for variety in chips and tiles |

The four **pantry colours** are identity accents: the quick-action icon
chips, recipe placeholder tiles, the food-icon pattern. A colour belongs to a
thing and stays with it (`RecipeCover` picks a recipe's tile colour from its
id). They are not status colours and not chart series.

To tint a surface with one, mix it rather than inventing a new token:
`color-mix(in oklch, var(--saffron) 20%, var(--card))`.

### Surfaces and text

| Token | Light | Dark | Role |
|---|---|---|---|
| `--background` | `oklch(0.972 0.014 78)` ≈ `#FBF5EC` linen | `oklch(0.185 0.013 50)` ≈ `#18110E` cocoa | Page |
| `--card`, `--popover` | `oklch(0.993 0.006 85)` ≈ `#FFFDF8` paper | `oklch(0.228 0.016 50)` ≈ `#231A16` | Cards, menus, dialogs |
| `--foreground` | `oklch(0.255 0.032 48)` ≈ `#301E15` espresso | `oklch(0.945 0.016 80)` ≈ `#F3ECE1` | Body text |
| `--muted` / `--muted-foreground` | oat / warm grey-brown | | Secondary text, quiet fills |
| `--secondary` | `oklch(0.93 0.045 85)` ≈ `#F6E6C7` | `oklch(0.32 0.04 70)` | Badges, secondary buttons, hover fills |
| `--accent` | `oklch(0.93 0.05 140)` ≈ `#D7F1D1` sage | `oklch(0.31 0.04 130)` | Menu hover, "vegetarian" badge |
| `--border`, `--input` | warm tan | `oklch(0.31 0.018 50)` | Hairlines |

Body text on the page is 14.6:1. White on tomato is 4.5:1, the AA minimum,
so keep text on tomato at 14px medium or larger. In dark mode the brighter
tomato takes near-black text (5.9:1) instead of white.

### Status

| Token | Use |
|---|---|
| `--success` | Done, ticked, "vegan" |
| `--warning` | Callouts that need attention (`border-warning/40 bg-warning/10`) |
| `--destructive` | Errors and destructive actions |

Status colours always come with an icon or a word, never colour alone.

### Charts

`--chart-1` … `--chart-5`: tomato, herb green, honey, plum, sage teal, in that
order. They are distinct from the pantry tokens even where the hues are close,
so the two uses can evolve separately.

### Dark mode: cocoa and candlelight

Dark mode is the same kitchen after dark: deep cocoa browns, never a cold
blue-grey. Every token is re-stepped for the dark surface, not inverted:
tomato and the pantry colours get lighter so they stay vivid on brown. The
`ThemeProvider` (`frontend/src/components/theme-provider.tsx`) sets the
`.dark` class on `<html>`; never write `dark:` colour overrides in components
when a token can do it.

## Typography

| Role | Family | Where |
|---|---|---|
| Display | **Fraunces** (variable) | `h1`–`h3`, recipe titles, the wordmark: `font-display` |
| Body / UI | **Plus Jakarta Sans** (variable) | Everything else: `font-sans` (the default) |

Fraunces runs with its **SOFT** axis at 100 and **WONK** on
(`font-variation-settings: "SOFT" 100, "WONK" 1`): rounded terminals and a
little cheek, a cookbook rather than a newspaper. Headings are weight 600 with
`-0.01em` tracking. Page titles are `text-3xl md:text-4xl`; the dashboard
greeting goes to `md:text-5xl`.

Fonts are self-hosted: the `@fontsource-variable/*` packages are bundled by
Vite and served from our own domain. No Google Fonts and no third-party
font CDN: no request leaves for a font, and nothing to declare in a
privacy policy.

## Shape, depth and motion

- **Radius**: `--radius` is `0.75rem`. Cards and tiles go rounder
  (`rounded-2xl`, the dashboard hero `rounded-3xl`); nav items are pills
  (`rounded-full`).
- **Shadows** are warm brown, never grey (`--shadow-xs/sm/md` in the `@theme`
  block). Primary buttons carry a soft tomato drop shadow.
- **Glow**: `bg-kitchen-glow` lays late-afternoon light (saffron and tomato
  radial gradients) across the top of every page.
- **Motion**: cards lift `-translate-y-0.5` on hover; recipe photos zoom
  `scale-105` over 300ms. Nothing bounces or spins.

## Layout

- **Top navigation** (`components/Navigation/TopNav.tsx`): logo, the sections
  as pills (the current one filled tomato), then the theme and account menus.
  Content is centred, `max-w-6xl`.
- **Phones**: the sections move to a bottom tab bar within thumb reach; the
  page keeps `pb-24` clear of it.
- **Dashboard**: a saffron hero (greeting and quick actions over the pantry
  pattern), then recent recipes (wide column) beside the active shopping list.
- **Recipes**: a grid of photo cards (`RecipeGrid`), as Community already was.
- **Sign-in**: the left panel shows the product: a recipe card resting on a
  shopping list, over the pantry pattern (`AuthShowcase`).

## Illustration and icons

- **Icons**: Lucide only, `size-4` inline and `size-5` in navigation, stroke
  1.5–2. Food icons (Carrot, Croissant, Soup…) are welcome in decoration.
- **Pantry pattern** (`components/Common/PantryPattern.tsx`): a hand-placed
  scatter of food icons in the pantry colours, like magnets on a fridge.
  Decorative only (`aria-hidden`), at 30–45% opacity, behind content.

## Logo

- **Mark**: Lucide `ChefHat`, in tomato on light surfaces, white or saffron on
  coloured ones.
- **Wordmark**: "Shop n Cook" in Fraunces, semibold, tight tracking.
- Mark and wordmark sit `gap-2.5` apart. Don't recolour the wordmark with a
  pantry colour or put it on a photo.

## Landing page

`landing/` uses Fraunces and Plus Jakarta Sans, self-hosted in
`landing/fonts/` (Latin and Latin Extended subsets, with their OFL licences)
and copied into the build by `scripts/build-landing.mjs` and the Dockerfile.
Its colours still use the old saffron-amber palette; bring them onto the
tomato tokens when it is next touched.

# Shop n Cook — Visual Identity

## Brand Personality

**Warm · Organized · Home-centric · Nourishing**

The app should feel like a well-lit, organized kitchen — not a sterile SaaS dashboard, not a fancy restaurant. Think golden afternoon light coming through a kitchen window, a wooden chopping board, and the color of saffron. Competent and organized for the shopping/ingredient management side; warm and inviting for the recipe side.

**Tagline:** "Your kitchen, organized."

---

## Color System

All colors use the **OKLCH color space** for perceptually uniform transitions. The three axes are: `L` (lightness 0–1), `C` (chroma 0–0.4), `H` (hue 0–360).

### Primary Palette

| Name | OKLCH | Hex approx. | Role |
|---|---|---|---|
| **Saffron Amber** | `oklch(0.580 0.175 52)` | ~#B36200 | Primary color, buttons, links, focus rings |
| Saffron Amber (dark) | `oklch(0.700 0.165 52)` | ~#D97B00 | Primary in dark mode (brighter for contrast) |
| **Herb Green** | `oklch(0.930 0.040 148)` | ~#E8F5E2 | Accent background (light mode) |
| Herb Green text | `oklch(0.220 0.060 148)` | ~#1A4020 | Accent foreground (light mode) |

### Semantic Tokens

#### Light Mode

| Token | Value | Description |
|---|---|---|
| `--background` | `oklch(0.990 0.006 80)` | Warm near-white (slight amber tint) |
| `--foreground` | `oklch(0.160 0.018 55)` | Warm near-black |
| `--card` | `oklch(0.975 0.008 80)` | Warm white card surface |
| `--card-foreground` | `oklch(0.160 0.018 55)` | |
| `--popover` | `oklch(0.975 0.008 80)` | |
| `--popover-foreground` | `oklch(0.160 0.018 55)` | |
| `--primary` | `oklch(0.580 0.175 52)` | Saffron amber |
| `--primary-foreground` | `oklch(0.100 0.020 52)` | Near-black on amber (~8:1 contrast ratio) |
| `--secondary` | `oklch(0.945 0.014 70)` | Warm cream |
| `--secondary-foreground` | `oklch(0.280 0.022 52)` | Deep amber-brown |
| `--muted` | `oklch(0.940 0.010 75)` | Warm oat |
| `--muted-foreground` | `oklch(0.510 0.018 55)` | Medium warm grey |
| `--accent` | `oklch(0.930 0.040 148)` | Soft herb green |
| `--accent-foreground` | `oklch(0.220 0.060 148)` | Deep green |
| `--destructive` | `oklch(0.577 0.245 27.325)` | Tomato red |
| `--border` | `oklch(0.890 0.015 70)` | Warm tan border |
| `--input` | `oklch(0.890 0.015 70)` | |
| `--ring` | `oklch(0.580 0.175 52)` | Amber focus ring |
| `--sidebar` | `oklch(0.960 0.012 72)` | Warm parchment |
| `--sidebar-foreground` | `oklch(0.160 0.018 55)` | |
| `--sidebar-primary` | `oklch(0.580 0.175 52)` | |
| `--sidebar-primary-foreground` | `oklch(0.100 0.020 52)` | |
| `--sidebar-accent` | `oklch(0.930 0.020 68)` | Warm hover surface |
| `--sidebar-accent-foreground` | `oklch(0.280 0.022 52)` | |
| `--sidebar-border` | `oklch(0.880 0.016 70)` | |
| `--sidebar-ring` | `oklch(0.580 0.175 52)` | |

#### Dark Mode

Dark mode maintains the warm hue family — backgrounds are deep warm-brown, not cold blue-grey. The amber primary brightens to maintain contrast on the dark surface.

| Token | Value | Description |
|---|---|---|
| `--background` | `oklch(0.138 0.012 55)` | Deep warm dark (whisper of amber) |
| `--foreground` | `oklch(0.960 0.008 75)` | Warm off-white |
| `--card` | `oklch(0.195 0.014 52)` | Warm dark card surface |
| `--card-foreground` | `oklch(0.960 0.008 75)` | |
| `--popover` | `oklch(0.195 0.014 52)` | |
| `--popover-foreground` | `oklch(0.960 0.008 75)` | |
| `--primary` | `oklch(0.700 0.165 52)` | Brightened amber (~9:1 contrast on dark bg) |
| `--primary-foreground` | `oklch(0.100 0.020 52)` | Near-black on amber |
| `--secondary` | `oklch(0.260 0.020 52)` | Dark amber-brown |
| `--secondary-foreground` | `oklch(0.920 0.012 72)` | |
| `--muted` | `oklch(0.250 0.016 55)` | Dark warm muted |
| `--muted-foreground` | `oklch(0.660 0.016 65)` | Medium warm grey |
| `--accent` | `oklch(0.270 0.040 148)` | Dark herb green surface |
| `--accent-foreground` | `oklch(0.880 0.060 148)` | Light green text |
| `--destructive` | `oklch(0.704 0.191 22.216)` | Warm red |
| `--border` | `oklch(1 0 0 / 10%)` | |
| `--input` | `oklch(1 0 0 / 15%)` | |
| `--ring` | `oklch(0.700 0.165 52)` | Amber focus ring |
| `--sidebar` | `oklch(0.175 0.016 52)` | Warm dark sidebar |
| `--sidebar-foreground` | `oklch(0.960 0.008 75)` | |
| `--sidebar-primary` | `oklch(0.700 0.165 52)` | |
| `--sidebar-primary-foreground` | `oklch(0.100 0.020 52)` | |
| `--sidebar-accent` | `oklch(0.248 0.020 55)` | |
| `--sidebar-accent-foreground` | `oklch(0.920 0.012 72)` | |
| `--sidebar-border` | `oklch(1 0 0 / 10%)` | |
| `--sidebar-ring` | `oklch(0.700 0.165 52)` | |

### Chart Colors

Five colors for data visualizations, covering the warm cooking color family:

| | Light | Dark | Name |
|---|---|---|---|
| Chart 1 | `oklch(0.580 0.175 52)` | `oklch(0.720 0.170 52)` | Amber |
| Chart 2 | `oklch(0.560 0.140 148)` | `oklch(0.640 0.130 148)` | Herb Green |
| Chart 3 | `oklch(0.720 0.160 60)` | `oklch(0.780 0.155 65)` | Golden Yellow |
| Chart 4 | `oklch(0.580 0.100 25)` | `oklch(0.650 0.110 25)` | Terracotta |
| Chart 5 | `oklch(0.680 0.090 190)` | `oklch(0.700 0.090 188)` | Sage Teal |

---

## Typography

### Typefaces

| Role | Family | Weights | Source |
|---|---|---|---|
| **Display / Headings** | Playfair Display | 400, 600, 700 | Google Fonts |
| **Body / UI** | Plus Jakarta Sans | 400, 500, 600, 700 | Google Fonts |

**Playfair Display** is an editorial serif used in premium food media (NYT Cooking, Bon Appétit). Its high-contrast strokes evoke classic recipe books without being stiff. Used for `h1`, `h2`, `h3`, the brand name in the logo.

**Plus Jakarta Sans** is a modern geometric humanist sans with subtle warmth — rounder and friendlier than Inter, excellent legibility at small sizes for table data and form labels. Used for all body text, UI labels, buttons, navigation.

### CSS Tokens

```css
--font-sans: "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif;
--font-display: "Playfair Display", Georgia, serif;
```

Tailwind 4 auto-generates `font-sans` and `font-display` utility classes from these `--font-*` tokens.

---

## Logo

**Icon:** `ChefHat` from lucide-react, `24×24` (h-6 w-6), `text-primary` (amber), `drop-shadow-sm`
**Wordmark:** `APP_NAME` in Playfair Display (`font-display`), `font-semibold`, `text-base`, `tracking-tight`
**Gap:** `2.5` (gap-2.5) between icon and text

The icon uses the amber primary color which gives the logo an immediate food/cooking signal. Drop shadow adds subtle depth without complication.

---

## Design Tokens — Border Radius

| Token | Value |
|---|---|
| `--radius` | `0.625rem` (10px) |
| `--radius-sm` | `calc(var(--radius) - 4px)` = 6px |
| `--radius-md` | `calc(var(--radius) - 2px)` = 8px |
| `--radius-lg` | `var(--radius)` = 10px |
| `--radius-xl` | `calc(var(--radius) + 4px)` = 14px |

---

## Implementation Notes

- All color tokens live in `/frontend/src/index.css` in the `:root` (light) and `.dark` (dark) blocks
- Font families are registered in the `@theme inline` block and applied in `@layer base`
- Dark mode is toggled by the custom `ThemeProvider` which applies the `.dark` class to `<html>`
- All shadcn/ui components (buttons, cards, inputs, etc.) automatically pick up the semantic tokens
- Never hardcode Tailwind color classes like `bg-zinc-600` or `bg-green-500` in components — always use semantic tokens so both light and dark modes are covered automatically
- The `bg-primary/15` opacity modifier works with OKLCH values in Tailwind 4

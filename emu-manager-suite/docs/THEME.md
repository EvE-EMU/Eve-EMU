# EMU Manager Suite — Visual theme

## Design intent

Match **EVE Online Tranquility client UI** (Photon-era): dark blue-grey panels, 11px body text, window title bars with — □ × controls, 54px neocom rail, list views with alternating rows.

Not generic SaaS, not AI concept art. Functional tools for experienced players.

## Tranquility reference patterns

| Pattern | Implementation |
|---------|----------------|
| Neocom (54px left rail) | `.eve-neocom`, `.eve-neocom-link` — icon wells, left accent on active |
| Window chrome | `.eve-window-titlebar` + `WindowChromeControls` (— □ ×) |
| Title text | 11px, sentence case, `#d4dce4` — not uppercase cyan |
| Location bar | `.eve-location-bar` — breadcrumb strip (Overview › host) |
| List tables | `.eve-table` — alternating rows, teal hover tint |
| Checkboxes | `.eve-checkbox` — not iOS toggles |
| KPI strip | `.eve-kpi-strip` — fused cells, not floating cards |
| Status ticker | `.eve-ticker` — left teal border, overview-style |

## Color tokens

| Token | Hex | Use |
|-------|-----|-----|
| `--bg` | `#0d1014` | Space backdrop |
| `--panel` | `#12181f` | Window body |
| `--panel-header` | `#1a222c` | Title bar |
| `--edge` | `#2a3540` | Window borders |
| `--link` | `#7eb8ca` | Accents, active neocom, ISK highlights |
| `--text` | `#d4dce4` | Body |
| `--text-muted` | `#5c6773` | Labels |
| `--neocom` | `#06080b` | Left rail fill |

Defined in `frontend/src/app/globals.css`.

## Typography

- **Base**: 11px Segoe UI (Tranquility uses small, dense type)
- **Labels**: 9–10px, muted grey
- **Values**: 11–13px tabular nums
- **Window titles**: 11px regular weight, sentence case

## Image generation prompts

### Master prompt (first pass)

Use for initial mockup generation (DALL·E, Midjourney v6, SDXL):

```
Design a highly realistic EVE Online Tranquility client interface for moon rental and moon tax management.

Must look like a shipped game UI screenshot, not concept art or AI dashboard design.

STYLE: Dark industrial sci-fi. Photon UI era EVE Online. Muted blue-grey (#0D1014 background, #12181F panels, #2A3540 borders). Restrained teal accents (#7EB8CA) only for links and selection. No neon, no rounded SaaS cards, no bubbly spacing.

LAYOUT:
- 54px vertical neocom sidebar left with monochrome icons
- Two floating windows side by side with proper title bars (window name left, minimize/maximize/close buttons right)
- Window 1: Moon Rental — moon name, system breadcrumb, composition tags, ISK rent fields, dropdowns, checkboxes, Rent/Cancel buttons
- Window 2: Moon Tax Management — corp header, R4-R64 slider rows, revenue table, payout history, checkboxes, Apply/Reset buttons
- Dense 11px text, left-aligned data rows, compact padding

DO NOT: large rounded cards, bright gradients, centered hero layouts, uppercase display headers, Stripe/Notion/Linear aesthetics, emojis, decorative glow.

REALISM: Slight asymmetry, alternating table row shading, functional density, believable ISK values, captured-from-live-client feel.
```

**Midjourney v6 tuning:** `--style raw --s 75 --chaos 8` + append: `game UI screenshot, EVE Online client interface, not concept art`

**SDXL tuning:** CFG 5–7, steps 35–45, keywords: `UI screenshot, game interface, mmorpg hud`

---

### Second pass prompt (refinement / anti-AI)

Use this **after** the first pass when output looks too clean, symmetrical, or “AI-smoothed”. Feed the first image as img2img reference if supported.

```
Refine this interface to remove all AI design tells. Target: authentic EVE Online Tranquility client screenshot quality.

FIX THESE AI ARTIFACTS:
- Over-symmetrical two-window layout → offset windows slightly, different heights OK
- Over-clean spacing → tighten vertical gaps between data rows to 2-4px
- Rounded corners anywhere → make all corners square, 0px radius
- Soft drop shadows → replace with 1px hard borders and subtle top-edge inset highlight only
- Generic sans-serif dashboard look → smaller 11px text, muted grey labels, teal only on interactive elements
- Fake glassmorphism blur → semi-opaque flat panels (#12181F 95% opacity), minimal blur
- Oversized title text → window titles 11px regular weight, sentence case
- Missing window chrome → add — □ × control buttons on title bar right edge
- Neocom too wide or missing → 54px dark left rail, icons in square hit areas with left accent bar when selected
- Checkbox toggles that look iOS → small 12px square checkboxes with tick mark
- Tables that look like web apps → alternating row backgrounds, 2px cell padding, no zebra over-styling

PRESERVE:
- Dark space background visible between windows
- Moon rental + tax management functional content
- ISK currency formatting with column-aligned numbers
- Industrial sci-fi mood without neon

OUTPUT: Crisp readable UI that could pass as an in-game capture from an experienced player's client. Practical usability over visual perfection. Slight imperfections in alignment acceptable.
```

**Midjourney refinement:** `--style raw --s 50 --chaos 5 --iw 1.2` (image weight on first pass)

**SDXL img2img:** denoise 0.35–0.45, same prompt, add ControlNet lineart if edges are too soft

---

### Split prompts (per window, cleaner results)

**Window A only:**
```
EVE Online Tranquility client window: Moon Rental panel. Title bar with — □ ×. Moon name DS-LO3, region breadcrumb, circular moon thumbnail, data rows (type, composition tags, difficulty, rent ISK/mo), duration dropdown, ISK input, checkboxes, financial summary table, Rent and Cancel buttons. 11px dense UI, #0D1014 background, square corners, game screenshot.
```

**Window B only:**
```
EVE Online Tranquility client window: Moon Tax Management panel. Title bar with — □ ×. Corporation emblem placeholder, tax rate display, horizontal sliders for R4 R8 R16 R32 R64, revenue breakdown table (volume, rate, collected ISK), scrollable payout history, enforcement checkboxes, Apply Tax and Reset buttons. Dense list-view aesthetic, muted teal accents, 11px text.
```

Composite in Figma or use ControlNet layout guide to merge.

## Components (code)

| Component | File |
|-----------|------|
| Neocom shell | `AppShell.tsx` |
| Window chrome | `ui.tsx` → `EveWindow`, `WindowChromeControls` |
| Moon ops windows | `MoonOperations.tsx` |
| Design tokens | `globals.css` |

## Do / Don't

**Do:** 11px base, window chrome, neocom rail, checkbox controls, alternating table rows

**Don't:** Propaganda banners, clip-path panels, iOS toggles, uppercase window titles, KPI cards with heavy shadows

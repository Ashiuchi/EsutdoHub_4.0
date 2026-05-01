# Profile & Cockpit UI Upgrade — Design Spec
**Date:** 2026-05-01  
**Status:** Approved  
**Scope:** `frontend/src/app/globals.css` + `frontend/src/components/perfil/PerfilDashboard.tsx`

---

## Overview

Two focused improvements to the EstudoHub Pro 4.0 Perfil page:

1. **Global CSS contrast fix** — `<select>` and `<option>` elements are illegible in dark mode because they inherit system defaults. Apply explicit dark/light CSS to guarantee readability.
2. **Avatar System — Gamer Edition** — Expand the preset catalogue to 5 DiceBear styles, promote file upload to a "Hero Action" zone at the top of the modal, and add a custom teal scrollbar to the preset area.

Aesthetic constraints: Teal (`#007F8E`), Zinc/Graphite (`#09090b` / `#2D2D2D`), Off-white (`#E0E0E0`), glassmorphism, `rounded-3xl`, smooth transitions.

---

## Task 1 — Select/Option Contrast Fix (`globals.css`)

### Problem
Native `<select>` elements in dark mode render `<option>` items with system-default colors, which on many browsers/OS combos produces dark text on a dark background — unreadable.

### Solution
Append a dedicated CSS block at the end of `globals.css` that overrides `select` and `option` background/color in both themes.

| Theme | `select` background | `select` text | `option` background | `option` text |
|---|---|---|---|---|
| Dark (default) | `#09090b` (zinc-950) | `#e4e4e7` (zinc-200) | `#09090b` | `#e4e4e7` |
| Light (`html.light`) | `#f1f5f9` (slate-100) | `#1e293b` (slate-800) | `#f1f5f9` | `#1e293b` |

Also add a **custom thin scrollbar** (webkit) globally:
- Track: transparent
- Thumb: `#007F8E` (teal-600), `border-radius: 9999px`
- Width/height: 4px

Applied via `::-webkit-scrollbar`, `::-webkit-scrollbar-track`, `::-webkit-scrollbar-thumb` pseudo-selectors on `:root` in `globals.css`. No Tailwind class needed.

### Constraints
- Do NOT use `appearance: none` alone — it removes the arrow; combine with explicit colors only.
- Scope dark styles under `:root` (already defaults to dark) and light styles under `html.light`.
- Must not break Clerk component selects (scoped by class, not affected).

---

## Task 2 — Avatar System Gamer Edition (`PerfilDashboard.tsx`)

### 2A — Expanded AVATAR_PRESETS

Replace the current 4-preset constant with 5 entries covering distinct DiceBear v7 styles:

| id | DiceBear style | Label |
|---|---|---|
| `avataaars` | `avataaars` | Humanos |
| `pixel-art` | `pixel-art` | Pixel Art |
| `bottts` | `bottts` | Robôs |
| `big-smile` | `big-smile` | Pets/Bichos |
| `adventurer` | `adventurer` | Aventureiros |

URL pattern: `https://api.dicebear.com/7.x/{style}/svg?seed=`

### 2B — Upload Hero Action

Inside `showAvatarModal`, add a visually prominent upload zone **above** the presets:

- A styled card/button (`glass`, `rounded-2xl`, teal accent border on hover) that triggers a hidden `<input type="file" accept="image/*">` via `useRef<HTMLInputElement>(null)` — ref named `fileInputRef`, declared alongside other state hooks, called via `fileInputRef.current?.click()` in the button's `onClick`.
- Icon: `Upload` (already imported from lucide-react).
- Loading state: replace icon with `<Loader2 className="animate-spin">` while `uploadingAvatar === true`.
- Handler: the existing `handleAvatarUpload` function — no new logic needed.
- On success: modal closes automatically (already handled by `setShowAvatarModal(false)` in handler).

### 2C — Modal Layout

```
┌──────────────────────────────────┐
│ [X]  Personalizar Perfil         │  ← Close button (top-right)
│──────────────────────────────────│
│  ┌────────────────────────────┐  │
│  │  [Upload / Loader2]        │  │  ← Hero Action zone
│  │  Enviar Foto               │  │
│  │  Clique para selecionar    │  │
│  └────────────────────────────┘  │
│                                  │
│  ── ou escolha um preset ──      │  ← Divider (hr + label centered)
│                                  │
│  ┌──────────┐  ┌──────────┐     │  ← Presets grid (2 cols)
│  │ [avatar] │  │ [avatar] │     │
│  │ Humanos  │  │ Pixel Art│     │
│  └──────────┘  └──────────┘     │
│  ...                             │  ← max-h-[70vh] overflow-y-auto
│                                  │  ← custom scrollbar teal
└──────────────────────────────────┘
```

**Modal container:** `max-w-md`, `glass p-8 rounded-3xl`. The preset area wraps in a `div` with `max-h-[70vh] overflow-y-auto` and custom scrollbar class.

**Close button:** top-right corner, `X` icon, `hover:text-white/70 → text-white`. Calls `setShowAvatarModal(false)`.

**Divider:** `<hr className="border-white/10">` with a centered label `"ou escolha um preset"` in `text-[10px] text-white/30 uppercase tracking-widest`.

**Preset cards:** same `grid grid-cols-2 gap-3` pattern as current, each card shows a DiceBear SVG preview (`w-10 h-10 rounded-lg`) + label. Clicking calls `handlePresetAvatar(preset.url)`. Disabled/loading state: entire grid `pointer-events-none opacity-50` while `uploadingAvatar`.

### Preserved Logic
- `handleAvatarUpload`, `handlePresetAvatar`, `uploadingAvatar`, `setShowAvatarModal` — unchanged.
- All Framer Motion entry/exit animations on the modal overlay and panel — unchanged.
- Clerk metadata, tier system, cycle engine — untouched.

---

## Non-Goals
- No new API calls beyond existing DiceBear fetch in `handlePresetAvatar`.
- No drag-and-drop — click-triggered file input only.
- No changes to Cockpit, CockpitDashboard, or any other component.

---

## Implementation Order

1. `globals.css` — append select/option styles + custom scrollbar (safe, no component changes).
2. `PerfilDashboard.tsx` — expand `AVATAR_PRESETS`, add `fileInputRef`, restructure modal JSX.

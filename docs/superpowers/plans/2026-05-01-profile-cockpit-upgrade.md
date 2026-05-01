# Profile & Cockpit UI Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `<select>` contrast in dark/light mode and evolve the avatar modal into a full Gamer Edition experience with hero upload zone, 5 DiceBear presets, and a custom teal scrollbar.

**Architecture:** Two isolated file edits — global CSS appended at the end of `globals.css`, and the React component updated in-place inside `PerfilDashboard.tsx` (no new files, no new API calls). The existing `handleAvatarUpload` and `uploadingAvatar` state are reused as-is; a new `fileInputRef` connects the hidden file input to the hero button.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS v4, Framer Motion, Lucide-React, Clerk (`user.setProfileImage`), DiceBear v7 (SVG API)

---

## Files Changed

| Action | Path | What changes |
|---|---|---|
| Modify | `frontend/src/app/globals.css` | Append select/option dark+light styles and webkit scrollbar rules |
| Modify | `frontend/src/components/perfil/PerfilDashboard.tsx` | Add `useRef` import, `fileInputRef`, expand `AVATAR_PRESETS`, restructure `showAvatarModal` JSX |

---

## Task 1: Global CSS — Select Contrast & Custom Scrollbar

**Files:**
- Modify: `frontend/src/app/globals.css` (append after line 210)

### Context for this task
The project uses `html` (no class) as dark mode default, and `html.light` for light mode. All `<select>` elements in the app inherit system browser defaults, which renders option text invisible on dark backgrounds in many browsers (Chrome on macOS/Windows). This task appends explicit color rules and a thin teal scrollbar.

- [ ] **Step 1: Append the following CSS block to the end of `frontend/src/app/globals.css`**

```css
/* ── Select / Option legibility (cross-browser, dark default) ────── */
select {
  background-color: #09090b;
  color: #e4e4e7;
}

select option {
  background-color: #09090b;
  color: #e4e4e7;
}

html.light select {
  background-color: #f1f5f9;
  color: #1e293b;
}

html.light select option {
  background-color: #f1f5f9;
  color: #1e293b;
}

/* ── Custom thin scrollbar (webkit) — teal accent ────────────────── */
::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #007F8E;
  border-radius: 9999px;
}

::-webkit-scrollbar-thumb:hover {
  background: #009aac;
}
```

- [ ] **Step 2: Verify with TypeScript/build (CSS has no type check — just confirm no syntax errors)**

Run from `frontend/`:
```bash
cd frontend && npm run build 2>&1 | tail -20
```
Expected: build succeeds (or only pre-existing errors — no new errors from this CSS).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "fix(css): add dark/light contrast for select/option elements and teal scrollbar"
```

---

## Task 2: PerfilDashboard — Avatar Gamer Edition

**Files:**
- Modify: `frontend/src/components/perfil/PerfilDashboard.tsx`

### Context for this task
The component already has `handleAvatarUpload`, `uploadingAvatar`, `setShowAvatarModal`, all Framer Motion animations, and all Clerk auth logic. The modal currently shows only a flat `grid-cols-2` of 4 preset buttons with no upload option. This task:
1. Adds `useRef` to the React import and declares `fileInputRef`.
2. Replaces `AVATAR_PRESETS` with 5 entries (adds `big-smile`).
3. Restructures the `AnimatePresence` modal block with close button, hero upload zone, divider, and scrollable preset grid.

Nothing outside the modal block changes. The `handleAvatarUpload` and `handlePresetAvatar` functions are untouched.

### Step 2A — Update React import to include `useRef`

- [ ] **Step 2A: In `frontend/src/components/perfil/PerfilDashboard.tsx`, change line 4**

Find:
```typescript
import { useState, useEffect, useMemo } from "react";
```

Replace with:
```typescript
import { useState, useEffect, useMemo, useRef } from "react";
```

### Step 2B — Expand AVATAR_PRESETS constant

- [ ] **Step 2B: Replace the `AVATAR_PRESETS` constant (lines 43-48 approx)**

Find:
```typescript
const AVATAR_PRESETS = [
  { id: "pixel", name: "Pixel Art", url: "https://api.dicebear.com/7.x/pixel-art/svg?seed=" },
  { id: "bottts", name: "Robô", url: "https://api.dicebear.com/7.x/bottts/svg?seed=" },
  { id: "avataaars", name: "Humano", url: "https://api.dicebear.com/7.x/avataaars/svg?seed=" },
  { id: "adventurer", name: "Aventureiro", url: "https://api.dicebear.com/7.x/adventurer/svg?seed=" },
];
```

Replace with:
```typescript
const AVATAR_PRESETS = [
  { id: "avataaars",  name: "Humanos",      url: "https://api.dicebear.com/7.x/avataaars/svg?seed=" },
  { id: "pixel-art",  name: "Pixel Art",    url: "https://api.dicebear.com/7.x/pixel-art/svg?seed=" },
  { id: "bottts",     name: "Robôs",        url: "https://api.dicebear.com/7.x/bottts/svg?seed=" },
  { id: "big-smile",  name: "Pets/Bichos",  url: "https://api.dicebear.com/7.x/big-smile/svg?seed=" },
  { id: "adventurer", name: "Aventureiros", url: "https://api.dicebear.com/7.x/adventurer/svg?seed=" },
];
```

### Step 2C — Declare fileInputRef alongside other state hooks

- [ ] **Step 2C: Inside `export default function PerfilDashboard()`, after the existing `const [uploadingAvatar, setUploadingAvatar] = useState(false);` line, add**

```typescript
const fileInputRef = useRef<HTMLInputElement>(null);
```

The declaration block in context looks like this (add the ref immediately after `uploadingAvatar`):
```typescript
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);   // ← add this line
```

### Step 2D — Replace the AnimatePresence / modal block

This is the largest change. Replace the entire `<AnimatePresence>` block at the bottom of the component (currently lines ~735-754).

- [ ] **Step 2D: Find the existing AnimatePresence block**

```tsx
      <AnimatePresence>
        {showAvatarModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setShowAvatarModal(false)} className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }} className="relative w-full max-w-md glass p-8 rounded-3xl">
              <h3 className="text-xl font-bold text-white mb-6">Personalizar Perfil</h3>
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-3">
                  {AVATAR_PRESETS.map((preset) => (
                    <button key={preset.id} onClick={() => handlePresetAvatar(preset.url)} className="flex items-center gap-3 p-3 rounded-2xl bg-white/5 border border-white/5 hover:border-[#007F8E]/50">
                      <img src={`${preset.url}${preset.id}`} alt={preset.name} className="w-10 h-10 rounded-lg bg-zinc-800" />
                      <span className="text-xs font-bold text-white/70">{preset.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
```

Replace with:
```tsx
      <AnimatePresence>
        {showAvatarModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowAvatarModal(false)}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            />
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="relative w-full max-w-md glass p-8 rounded-3xl max-h-[90vh] flex flex-col"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-white">Personalizar Perfil</h3>
                <button
                  onClick={() => setShowAvatarModal(false)}
                  className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleAvatarUpload}
              />

              {/* Hero Upload Zone */}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingAvatar}
                className="w-full p-5 rounded-2xl bg-white/5 border border-white/10 hover:border-[#007F8E]/60 hover:bg-[#007F8E]/5 transition-all group disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="flex flex-col items-center gap-2">
                  {uploadingAvatar ? (
                    <Loader2 size={28} className="text-[#007F8E] animate-spin" />
                  ) : (
                    <Upload size={28} className="text-[#007F8E] group-hover:scale-110 transition-transform" />
                  )}
                  <span className="text-sm font-bold text-white/80">
                    {uploadingAvatar ? "Enviando..." : "Enviar Foto"}
                  </span>
                  <span className="text-[10px] text-white/30">Clique para selecionar um arquivo</span>
                </div>
              </button>

              {/* Divider */}
              <div className="flex items-center gap-3 my-6">
                <div className="flex-1 h-px bg-white/10" />
                <span className="text-[10px] text-white/30 uppercase tracking-widest whitespace-nowrap">
                  ou escolha um preset
                </span>
                <div className="flex-1 h-px bg-white/10" />
              </div>

              {/* Presets Grid — scrollable */}
              <div className="flex-1 min-h-0 max-h-[70vh] overflow-y-auto pr-1">
                <div className="grid grid-cols-2 gap-3">
                  {AVATAR_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      onClick={() => handlePresetAvatar(preset.url)}
                      disabled={uploadingAvatar}
                      className="flex items-center gap-3 p-3 rounded-2xl bg-white/5 border border-white/5 hover:border-[#007F8E]/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <img
                        src={`${preset.url}${preset.id}`}
                        alt={preset.name}
                        className="w-10 h-10 rounded-lg bg-zinc-800 flex-shrink-0"
                      />
                      <span className="text-xs font-bold text-white/70">{preset.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
```

### Step 2E — Type-check and visual verification

- [ ] **Step 2E: Run TypeScript type check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -v node_modules
```
Expected: no errors referencing `PerfilDashboard.tsx` (pre-existing errors in other files are acceptable).

- [ ] **Step 2F: Commit**

```bash
git add frontend/src/components/perfil/PerfilDashboard.tsx
git commit -m "feat(perfil): expand avatar presets to 5 styles and upgrade modal with hero upload zone"
```

---

## Post-Implementation Visual Checklist

Run `npm run dev` from `frontend/` and navigate to `/perfil`. Verify manually:

- [ ] Dark mode: `<select>` dropdowns show zinc-950 background with zinc-200 text in native OS dropdown
- [ ] Light mode (`html.light`): same selects show slate-100 bg / slate-800 text
- [ ] Custom scrollbar appears thin (4px) and teal anywhere a scrollbar is visible
- [ ] Avatar modal opens with close button `[X]` top-right
- [ ] Hero upload zone shows `Upload` icon + "Enviar Foto" text
- [ ] Clicking hero zone opens native file picker
- [ ] During upload: `Upload` icon replaced by spinning `Loader2`, button disabled, presets grid opacity-50
- [ ] Divider label "ou escolha um preset" visible between hero and grid
- [ ] 5 preset cards visible: Humanos, Pixel Art, Robôs, Pets/Bichos, Aventureiros
- [ ] Preset grid area is scrollable (verify by temporarily reducing `max-h` to `max-h-[100px]` to force scroll, then revert)
- [ ] Clicking a preset closes the modal after successful avatar update

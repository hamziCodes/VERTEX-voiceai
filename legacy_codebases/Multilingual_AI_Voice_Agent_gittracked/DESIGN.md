# VERTEX Design Language Specification (DESIGN.md)

This document defines the unified visual design language, spatial hierarchy, typography tokens, color system, and component patterns for all **VERTEX** ecosystem products (`VERTEX/studio`, `VERTEX/labs`, AI Voice Agents, CRM Systems, POS Ecosystems, and Mobile Apps).

---

## 1. Brand Lockup & Tone

- **Primary Display Mark**: `VERTEX` (Bold, uppercase, tracking-tight).
- **Domain Accent**: `/studio`, `/labs`, `/pos` (Lowercase, `JetBrains Mono` / `DM Sans` sub-accent).
- **Tagline**: *"We Build Digital Realities."*
- **Tone & Copy Register**: Honest, restrained enterprise software engineering. No sci-fi hype jargon, no fake metrics, no artificial office coordinates.

---

## 2. Typography System

| Usage | Font Family | Tailwind Class | Weight & Tracking |
| :--- | :--- | :--- | :--- |
| **Display Headings** | `DM Sans` | `font-display` | `font-bold` / `font-extrabold`, `tracking-tight` |
| **UI Body & Controls** | `Inter` | `font-sans` | `font-normal` / `font-medium`, `leading-relaxed` |
| **Telemetry & Specs** | `JetBrains Mono` | `font-telemetry` | `font-mono`, `text-xs`, `tracking-[0.2em]`, `uppercase` |

### Eyebrow Label Rule
All eyebrow section markers must use ALL CAPS monospace telemetry formatting:
```tsx
<span className="font-telemetry text-xs tracking-[0.2em] text-cyan-accent uppercase block">
  01 // SYSTEM CAPABILITY
</span>
```

---

## 3. Core Color System (Void Dark Mode)

### Base Surfaces
- **Void Black (Page Background)**: `#000000` (`bg-void-black` / `bg-black`)
- **Glass Panel Surface**: `#131318` / `rgba(255, 255, 255, 0.03)` with `backdrop-filter: blur(16px)`
- **Surface High**: `#1a1b22` / `rgba(255, 255, 255, 0.06)`

### Accent Palettes
- **Cyan Accent (Primary Focus)**: `#00c6ff` (`text-cyan-accent`, `border-cyan-accent/30`)
- **Electric Blue (Action)**: `#0070f3`
- **Violet Depth (Secondary)**: `#7928ca` (`text-secondary`)
- **Gold Telemetry (Status)**: `#f5a623` / `#ffaa00` (`text-gold-accent`)

### Gradients
- **Vertex Gradient**: `linear-gradient(135deg, #0070f3 0%, #7928ca 50%, #ff0080 100%)`
- **Text Gradient**: `linear-gradient(135deg, #00c6ff 0%, #0070f3 100%)`

---

## 4. Strict Design Directives ("No-AI-Slop")

> [!IMPORTANT]
> **No Capsule / Pill Buttons**: Never use `rounded-full` for buttons, badges, or tags. All interactive elements and chip tags must use crisp rectangular spec geometry (`rounded-md` or `rounded-sm`).

- **Corner Radii Standard**:
  - Buttons & Cards: `rounded-md` (6px) or `rounded-2xl` (16px for major panels).
  - Badges & Tech Stack Tags: `rounded-sm` (2px) or `rounded-md` (4px).
- **Borders**: Hairline, almost invisible borders (`border border-white/[0.06] hover:border-cyan-accent/25`).
- **Glow Intensity**: Faint, subtle mouse spotlight glimpses (`rgba(0, 198, 255, 0.02)`). Avoid heavy, blinding radial halos.

---

## 5. Standard Component Patterns

### A. Rectangular Primary Button
```tsx
<button className="px-6 py-3 min-h-[44px] text-xs font-telemetry uppercase tracking-widest font-semibold text-white rounded-md bg-gradient-to-r from-[#0070f3] via-[#7928ca] to-[#ff0080] hover:brightness-110 shadow-lg transition-all">
  Start a Project →
</button>
```

### B. Glass Panel Card with Faint Spotlight
```tsx
<div className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-[#16171d] via-[#121318] to-cyan-accent/[0.03] p-8 shadow-xl">
  <span className="font-telemetry text-xs tracking-widest text-cyan-accent uppercase block mb-2">
    TELEMETRY TAG
  </span>
  <h3 className="font-display text-2xl font-bold text-white uppercase">
    System Module Title
  </h3>
</div>
```

### C. Technical Stack Badge
```tsx
<span className="rounded-sm border border-white/15 bg-white/5 px-2.5 py-1 font-telemetry text-[11px] text-white uppercase tracking-wider">
  TypeScript
</span>
```

---

## 6. Layout & Responsiveness Rules

- **Mobile Viewport Height**: Use `min-h-[100dvh]` to prevent mobile browser address bar layout jumps.
- **Mobile Touch Ergonomics**: All interactive elements (buttons, links, inputs) must maintain a minimum `min-h-[44px]` touch target on mobile screens (`<768px`).
- **Horizontal Overflow**: Enforce `max-w-[100vw]` and `overflow-x: clip` (or `overflow-x: hidden` on layout wrappers) to eliminate horizontal jitter.

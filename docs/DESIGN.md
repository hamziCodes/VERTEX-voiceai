# WAVIA · Ripple design specification (v1.1, final)

Implementation spec for a coding agent. Two surfaces are covered:

1. **Instagram teaser, "Ripple"**: 1080 × 1350 px, dark aubergine, lime dot rings. Also covers the reel cover and Studio post that carry the same language.
2. **Engine dashboard, "Ripple Paper" (C2)**: 1280 × 800 px desktop mock, bone paper, serif editorial.

Both use the same four brand colours and the same mono label face. They differ in ground (dark vs paper) and display face (Bricolage Grotesque vs Instrument Serif). Companion files: `design-tokens.json` (machine-readable tokens), `wavia-teaser.html` and `wavia-dashboard.html` (reference implementations using CSS variables; the dashboard is responsive), and PNG exports `wavia-teaser-1080x1350.png` and `wavia-dashboard-1280x800.png`. All dashboard numbers are mock data and must stay labelled "Illustrative data" until replaced with real captures.

---

## 1. Colour

### 1.1 Brand palette

| Token | Hex | Role |
| --- | --- | --- |
| `aubergine` | `#1A0B2E` | Dark ground (teaser); all text and rules on paper (dashboard) |
| `lime` | `#C8F169` | Accent fill: dots, highlight pill, key-word highlight, time chips. Never text on bone |
| `lilac` | `#B8A4FF` | Secondary fill: voice core, mono labels on dark, agent reply block, wordmark dot |
| `bone` | `#F4EFE6` | Light ground (dashboard); body text on aubergine |
| `lilac-deep` | `#7A5BC4` | Fourth segment of the turn-timing bar only |

### 1.2 Supporting colours (dark dashboard variant and Studio tile)

| Token | Hex | Use |
| --- | --- | --- |
| `aubergine-raised` | `#2A1647` | Card surface on dark UI (not used in C2) |
| `aubergine-line` | `#3F2765` | Hairlines on dark UI (not used in C2) |
| `studio-paper` | `#FFF6E5` | Panel fill for illustrative Studio screenshot tile; matches the Studio pilot paper colour |

### 1.3 Pairing rules and contrast (approximate WCAG ratios)

| Foreground on background | Ratio | Verdict |
| --- | --- | --- |
| bone on aubergine | ~16:1 | Body and headline text on dark |
| aubergine on bone | ~16:1 | All text on paper |
| aubergine on lime | ~14:1 | Text inside lime pills/highlights |
| aubergine on lilac | ~8:1 | Text inside lilac blocks |
| lilac on aubergine | ~8:1 | Mono labels on dark |
| lime on aubergine | ~14:1 | Accent graphics and mono on dark |
| lilac on bone | ~1.9:1 | **Fail. Never use lilac as text or thin lines on bone** (fills only) |
| lime on bone | ~1.1:1 | **Fail. Lime on bone only as a fill behind aubergine text** |
| lilac-deep on bone | ~4.8:1 | Fill only (bar segment) |

### 1.4 Gradients and opacity

- **No colour gradients anywhere.** The look is flat colour plus pattern.
- Only two gradient-type functions exist, both structural:
  - Dot field: `radial-gradient(circle, #C8F169 4px, transparent 4.6px)` tiled at 28 × 28 px.
  - Vignette: `radial-gradient(circle at 50% 38%, rgba(26,11,46,0) 0, rgba(26,11,46,0) 18%, #1A0B2E 74%)`.
- Opacities used: 0.5 on the outermost illustrative ring in the dark dashboard variant; 0.75 on the "Illustrative data" footnote in the dashboard; 0.7 on the same in the dark variant.
- No shadows, except the core's ring trick (section 4.2).

---

## 2. Typography

Load from Google Fonts:

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;800&family=Instrument+Serif:ital@0;1&family=Space+Mono:wght@400;700&display=swap">
```

| Role | Family | Weights/style | Fallback stack |
| --- | --- | --- | --- |
| Teaser display and wordmark | Bricolage Grotesque | 800 | `system-ui, sans-serif` |
| Dashboard display, numerals, quote | Instrument Serif | 400, italic for emphasis | `Georgia, serif` |
| Labels, timings, events (both) | Space Mono | 400 and 700 | `ui-monospace, monospace` |

### 2.1 Teaser type scale (1080 × 1350)

| Element | Face | Size | Weight | Tracking | Line height | Case/colour |
| --- | --- | --- | --- | --- | --- | --- |
| Headline | Bricolage | 128px | 800 | -4px | 0.98 | lowercase, bone |
| Headline pill word | Bricolage | 128px | 800 | -4px | 1.05 | aubergine on lime |
| Wordmark "wavia" | Bricolage | 60px | 800 | -2px | normal | lowercase, bone |
| Top-right label | Space Mono | 20px | 400 | +2px | normal | uppercase, lilac |
| Footer label | Space Mono | 20px | 400 | +2px | normal | uppercase, lilac |

### 2.2 Dashboard type scale (1280 × 800, desktop)

| Element | Face | Size | Weight/style | Tracking | Line height |
| --- | --- | --- | --- | --- | --- |
| Masthead wordmark | Instrument Serif | 44px | 400 italic | 0 | normal |
| KPI numerals | Instrument Serif | 84px | 400 | -3px | 0.95 |
| KPI unit "s" | Instrument Serif | 40px | 400 italic | inherits | n/a |
| Live quote | Instrument Serif | 66px | 400 | -2px | 1.02 |
| Agent reply | Instrument Serif | 38px | 400 italic | 0 | normal |
| Mono labels (`.m`) | Space Mono | 11px | 400 | +1.5px | normal, uppercase |
| Event rows | Space Mono | 11px | 400 | 0 | normal |

Rules: wordmark is always lowercase `wavia`; mono labels are always uppercase; display type never uses bold on the dashboard (Instrument Serif has only 400).

---

## 3. Spacing, layout, shape

- **Teaser:** outer margin 60px left/right; top row baseline at y=54-72; headline anchored bottom (120px from bottom edge); footer label 54px from bottom.
- **Dashboard:** outer padding 30px top/bottom, 44px left/right. Three-column grid `300px 1fr 330px`, column gap 34px, top padding 22px under the masthead. Centre column is a flex column with 18px gaps.
- **Rules:** dashboard uses 2px aubergine top rule + 1px bottom rule on the masthead; 1px aubergine rules between KPI blocks and between event rows. No cards, no shadows, no rounded corners on the paper dashboard (the lime highlight and lilac block are square).
- **Radii:** teaser pill word `70px` (fully round); core `50%`; Studio tile panel `18px`; everything on the paper dashboard `0`.
- **Panel border (Studio tile):** 3px solid lime.

---

## 4. Teaser spec: "Ripple" (1080 × 1350)

Copy: headline **"a first listen is coming."** (lowercase; "listen" on the lime pill). Wordmark `wavia`. Top-right `01 — SIGNAL`. Footer `VOICE AI ENGINE · SOON`. Makes no product claim.

### 4.1 Layer stack (bottom to top)

1. Ground `#1A0B2E`.
2. Dot field `.d`, full bleed, masked into rings.
3. Vignette `.v`, full bleed.
4. Voice core `.o`.
5. Text: wordmark, top-right label, headline, footer.

### 4.2 Ripple recipe

- Dot field: lime dots, 4px radius with a 0.6px soft edge, on a 28px grid.
- Ring mask: `repeating-radial-gradient(circle at 50% 38%, #000 0 54px, transparent 54px 108px)`. Centre is (540, 513). Visible bands are 0-54, 108-162, 216-270 px and so on; hidden bands in between. Gives concentric rings of dots with a 108px period.
- Vignette: transparent to 18% of the gradient radius, rising to solid aubergine at 74%, so outer rings fade into the ground. Gradient size is the default `farthest-corner`.
- Core: 300 × 300 px lilac circle at left 390, top 370 (centre 540, 520, aligned with the ripple centre within 7px). Edge treatment: `box-shadow: 0 0 0 18px #1A0B2E, 0 0 0 22px #C8F169;` (an aubergine gap, then a 4px lime ring).

### 4.3 Reference CSS

```css
.post{width:1080px;height:1350px;position:relative;overflow:hidden;background:#1A0B2E;color:#F4EFE6;font-family:'Bricolage Grotesque',system-ui,sans-serif}
.dots{position:absolute;inset:0;background:radial-gradient(circle,#C8F169 4px,transparent 4.6px) 0 0/28px 28px;-webkit-mask-image:repeating-radial-gradient(circle at 50% 38%,#000 0 54px,transparent 54px 108px);mask-image:repeating-radial-gradient(circle at 50% 38%,#000 0 54px,transparent 54px 108px)}
.vignette{position:absolute;inset:0;background:radial-gradient(circle at 50% 38%,rgba(26,11,46,0) 0,rgba(26,11,46,0) 18%,#1A0B2E 74%)}
.core{position:absolute;left:390px;top:370px;width:300px;height:300px;border-radius:50%;background:#B8A4FF;box-shadow:0 0 0 18px #1A0B2E,0 0 0 22px #C8F169}
.wm{position:absolute;left:60px;top:54px;font-weight:800;font-size:60px;letter-spacing:-2px;display:flex;gap:10px;align-items:center}
.wm s{width:16px;height:16px;border-radius:50%;background:#B8A4FF}
.tr{position:absolute;right:60px;top:72px;font:400 20px 'Space Mono',monospace;letter-spacing:2px;color:#B8A4FF}
h1.head{position:absolute;left:60px;right:60px;bottom:120px;margin:0;font-weight:800;font-size:128px;line-height:.98;letter-spacing:-4px}
h1.head u{text-decoration:none;background:#C8F169;color:#1A0B2E;padding:0 18px;border-radius:70px;display:inline-block;line-height:1.05}
.foot{position:absolute;left:60px;bottom:54px;font:400 20px 'Space Mono',monospace;letter-spacing:2px;color:#B8A4FF}
```

---

## 5. Carry-over formats (same language, same tokens)

### 5.1 Reel cover (540 × 960, 9:16)

- Ground aubergine, text bone, accent lime.
- Top-left tag: Space Mono 700, 22px, +3px tracking, lime, at (44, 44). Example `02 · ON MIC`.
- Title bottom-left, 44px from left, 150px above bottom: Bricolage 800, 150px, line height 0.9, -3px tracking. Example "On / mic.".
- Waveform strip: 44px side margins, 60px above bottom, 70px tall, 5px gaps, lime bars with 3px radius, vertically centred. **Replace with the real recorded waveform for the actual reel.**

### 5.2 Studio post (1080 × 1350)

- Tag top-left as above (`03 · INSIDE STUDIO`), lime.
- Panel: left/right 60px, top 170px, height 640px, fill `#FFF6E5`, 3px lime border, 18px radius, 34px padding. **Panel text colour must be aubergine `#1A0B2E`.** (The first mock set the panel text to bone on cream, which is unreadable; this spec corrects it.)
- Caption: left 60px, top 860px, Bricolage 800, 110px, line height 0.92, -3px tracking, bone. Example "Inside / Studio."
- Footer note, only on mockups: Space Mono 18px, lime, "ILLUSTRATIVE UI — SWAP FOR REAL CAPTURE". Remove once a real Studio capture is used.

---

## 6. Dashboard spec: "Ripple Paper" (C2, 1280 × 800)

Desktop layout (≥1100px) matches the 1280 × 800 mock; below that it collapses (section 8).

### 6.1 Structure

```
page (bone, padding 30px 44px, flex column)
├─ masthead: wordmark (left) · title label (centre) · mode pill (right)
├─ tab nav: Live · Agents · Sessions · Providers · Latency · Events
└─ grid 300px | 1fr | 330px, gap 34px
   ├─ left:   3 KPI blocks (label + numeral)  + "Illustrative data" note
   ├─ centre: label · live quote · agent reply block · waveform
   └─ right:  turn-timing bar + caption · event ledger
```

### 6.2 Components

**Masthead** (`.h`): `border-top:2px solid #1A0B2E; border-bottom:1px solid #1A0B2E; padding:8px 0; display:flex; justify-content:space-between; align-items:baseline`. Left: `wavia` Instrument Serif italic 44px. Centre: mono label "Engine report · live session". Right: mode pill, mono label, `background:#1A0B2E; color:#F4EFE6; padding:5px 10px`, text "Live provider · mock data". The pill text should switch to "Offline mock" when the engine runs in offline mock mode.

**KPI block** (`.k`): `border-bottom:1px solid #1A0B2E; padding:10px 0`. Mono label above a 84px numeral. Three blocks in order: Turn latency p50 `0.84` with italic `s`; Interruptions handled `12`; Active sessions `3` (mock values).

**Live quote**: mono label "Now speaking · service desk demo", then the quote at 66px: `“What time do <span class="hl">you close</span> today?”` (the full sentence reads “What time do you close today?”; only the words “you close” carry the highlight). Highlight `.hl`: `background:#C8F169; padding:0 8px` (inline, square, aubergine text).

**Agent reply**: `background:#B8A4FF; padding:20px 24px; font-size:38px; font-style:italic`, text "We close at 6 p.m. today."

**Waveform**: SVG `viewBox="0 0 640 90"`, width 100%, height 90, `stroke:#1A0B2E; stroke-width:8` vertical bars on an 18px pitch, symmetric about y=45. The mock path:

```
M8 45V45M26 30V60M44 14V76M62 26V64M80 6V84M98 24V66M116 38V52M134 10V80M152 28V62M170 40V50M188 16V74M206 4V86M224 30V60M242 42V48M260 20V70M278 34V56M296 44V46M314 24V66M332 12V78M350 38V52M368 44V46M386 30V60M404 42V48M422 45V45
```

It is illustrative and only spans the left two-thirds of the width. In production, draw bars from real audio amplitude across the full width, with `role="img"` and an `aria-label`.

**Turn-timing bar**: mono label "Turn · 840 ms", then `display:grid; grid-template-columns:14fr 37fr 31fr 18fr; height:30px; margin:10px 0 6px`. Segment fills in order: VAD `#B8A4FF`, STT `#C8F169`, LLM `#1A0B2E`, TTS `#7A5BC4`. Caption below: `VAD 120 · STT 310 · LLM 260 · TTS 150` (mono, 22px bottom margin). Segment widths are proportional to milliseconds (120/310/260/150 of 840); compute them from data in production.

**Event ledger**: mono label "Event ledger", then rows: `font:11px 'Space Mono'; padding:7px 0; border-bottom:1px solid #1A0B2E`. Each row starts with a time chip `background:#C8F169; padding:1px 5px; margin-right:8px`. Mock rows:

```
00:01.92 vad.speech_start
00:03.10 vad.speech_end
00:03.42 stt.final
00:03.96 llm.first_token
00:04.31 tts.first_audio
```

Event names are illustrative; use the engine's real event names when wired up.

### 6.3 Reference CSS

```css
.dash{width:1280px;height:800px;overflow:hidden;background:#F4EFE6;color:#1A0B2E;font-family:'Instrument Serif',Georgia,serif;padding:30px 44px;display:flex;flex-direction:column}
.m{font:11px 'Space Mono',monospace;letter-spacing:1.5px;text-transform:uppercase}
.mast{border-top:2px solid #1A0B2E;border-bottom:1px solid #1A0B2E;display:flex;justify-content:space-between;align-items:baseline;padding:8px 0}
.grid{flex:1;display:grid;grid-template-columns:300px 1fr 330px;gap:34px;padding-top:22px}
.kpi{border-bottom:1px solid #1A0B2E;padding:10px 0}.kpi b{display:block;font-weight:400;font-size:84px;line-height:.95;letter-spacing:-3px}
.ev{font:11px 'Space Mono',monospace;padding:7px 0;border-bottom:1px solid #1A0B2E}.ev span{background:#C8F169;padding:1px 5px;margin-right:8px}
.hl{background:#C8F169;padding:0 8px;box-decoration-break:clone;-webkit-box-decoration-break:clone}
```

---

## 7. Content and voice rules

- Wordmark is lowercase `wavia`. Product name in running copy: WAVIA.
- Teaser headline is sentence-style lowercase: "a first listen is coming."
- Mono labels are uppercase and short; use "·" (middle dot) or "—" (em dash) as separators.
- Use typographic punctuation in copy: ’ for apostrophes, curly “ ” quotes (as in the quote above).
- Mock UI, mock data, mock waveform: always labelled ("Illustrative data", "ILLUSTRATIVE UI"). Make no claims about live provider behaviour, interruption quality, mixed-language performance or carrier coverage without evidence specific to that claim.

---

## 8. Navigation and responsive behaviour (final)

**Tab nav** (`nav.tabs`): sits directly under the masthead. Items: Live, Agents, Sessions, Providers, Latency, Events. Space Mono 11px, uppercase, +1.5px tracking, aubergine text, `padding:4px 10px`, 6px gap, `1px solid #1A0B2E` rule beneath (10px padding above and below). Active tab: `background:#C8F169` and `aria-current="page"`. No hover colour other than a visible focus ring: `outline:2px solid #1A0B2E; outline-offset:2px`. On narrow screens the row scrolls horizontally; it never wraps.

**Breakpoints** (implemented in `wavia-dashboard.html`):

| Width | Layout |
| --- | --- |
| ≥ 1101px | Three columns `300px 1fr 330px`, KPIs 84px |
| ≤ 1100px | One column; order: quote, reply, waveform → KPIs (3 across) → timing → events. KPI numerals 56px, quote 44px, reply 30px, page padding 20px |
| ≤ 560px | KPIs stack one per row; centre masthead label hidden; wordmark 34px |

**Waveform:** the reference draws illustrative bars across the full width from a deterministic function. In production, replace with bars computed from real audio amplitude; keep the 8px stroke, 18px pitch, symmetric about the centre line.

**Fonts:** self-host in production; keep the fallback stacks.

## 9. Final decisions (previously open)

1. **Two grounds, one system.** Dark aubergine is for brand and social surfaces (teaser, reel covers, Studio posts). Bone paper is for product UI (the engine dashboard). Same four colours and the same Space Mono labels everywhere; each surface uses exactly one display face (Bricolage Grotesque on dark, Instrument Serif on paper). Do not mix them within a surface.
2. **Studio pilot.** Ripple is the brand system going forward. The approved Studio pilot is left untouched until it is deliberately migrated. Suggested mapping for that migration (not yet approved): paper `#FFF6E5` → bone `#F4EFE6`; ink `#1C1408` → aubergine `#1A0B2E`; accent `#B45309` → lime fill with aubergine text for highlights, lilac for secondary blocks; Bricolage Grotesque / Instrument Sans → Instrument Serif display with Space Mono labels. Studio *post* tiles keep `#FFF6E5` panels because they depict the pilot UI as it exists today.
3. **Navigation:** defined in this section.
4. **Real captures:** the waveform, Studio panel, metrics and event names are illustrative and stay labelled until replaced.

## 10. Do and don't

- Do keep it flat: no gradients, glows or drop shadows.
- Do keep lime and lilac as fills; keep text aubergine on paper, bone on dark.
- Do keep 60px (teaser) / 44px (dashboard) outer margins.
- Don't put lilac or lime text on bone.
- Don't use bold on Instrument Serif; don't mix display faces within a surface.
- Don't use the dot-ripple motif on the paper dashboard; it uses rules and flat blocks.
- Don't publish a mockup element (illustrative UI, waveform or metric) as a product claim.

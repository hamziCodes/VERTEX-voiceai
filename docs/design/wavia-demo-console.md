# Wavia Demo Console Design Record

**Date:** 2026-10-16

**Status:** implemented and locally verified

**Surface:** `examples/web-client/index.html`

## Direction

The voice playground is a calm, dense operations console. It keeps the active
conversation visible while configuration and diagnostics remain one click or
one internal scroll away. The visual language uses restrained dark surfaces,
compact type, clear state color, and no decorative gradients or glow effects.

## Desktop structure

- Left: session controls, explicit provider/runtime mode, and collapsible
  pipeline setup.
- Center: microphone state, waveform, live transcript, and text-turn input.
- Right: Latency, Metrics, and Events tabs in one fixed inspector.
- At widths above 1180 px, the workspace fits the viewport and each panel owns
  its scrolling. The page itself does not scroll while Voice Playground is
  active.

## Responsive behavior

- At medium widths, the inspector moves beneath the control and conversation
  panels.
- At mobile widths, panels stack vertically and normal document scrolling is
  restored.
- The top navigation remains horizontally scrollable and the page does not
  produce horizontal overflow.

## Runtime truthfulness

The console labels offline mock and live provider modes from the server's
`session_ready` event. In mock mode it distinguishes a disabled transcript from
a configured fixed test transcript. VAD state is shown from explicit onset and
end transition events rather than inferred from microphone volume.

## Verification evidence

- `Codex Fix/evidence/phase-02/demo-desktop-1440x900.png`
- `Codex Fix/evidence/phase-02/demo-mobile-390x844.png`

Playwright verified panel fit, tab switching, unique element IDs, and no mobile
horizontal overflow. A live microphone session still requires Hamzi's local
permission and listening check.

# Mobile Console Redesign Design

Date: 2026-06-19

## Goal

Redesign the MRRC mobile page at `/mobile` into a more capable radio console for real phone use. The page should keep the current backend, WebSocket, audio, memory-channel, WDSP, and PTT behavior intact while improving visual hierarchy, touch ergonomics, state clarity, and responsive fit across common phone sizes.

The target user is an operator controlling a remote radio from a phone. The primary action is safe receive/transmit operation through PTT. Secondary actions are tuning, mode/band/filter changes, memory recall/save, DSP adjustment, audio gain, and navigation to CW/FT8/recordings.

## Scope

This redesign covers:

- `www/mobile_modern.html`
- `www/mobile_modern.css`
- `www/mobile_modern.js`

The redesign may add small helper functions and modest markup structure changes, but it must preserve hidden desktop-compatible elements required by `www/controls.js`.

This redesign does not cover:

- Rewriting `www/controls.js`
- Rewriting `www/tx_button_optimized.js`
- Changing the PTT audio cleanup flow
- Changing backend WebSocket protocols
- Changing memory-channel storage APIs
- Changing WDSP backend commands

## Existing Findings

Live review used the authenticated route `https://radio.vlsc.net:8891/mobile` with phone-sized viewports.

Observed issues:

- Large phones leave a large unused vertical gap between memory channels and the fixed PTT area.
- Small phones compress DSP buttons below comfortable touch height.
- Mode and band shortcut buttons show the next value, while the status bar shows the current value. This is efficient but confusing during operation.
- The frequency input appears directly over the frequency display and feels abrupt.
- The off-canvas menu works, but it is an old ungrouped list and still shows `MRRC V4.9.2`.
- Several UI regions use similar cyan treatment, making state priority less obvious.
- The page is locked to one viewport-height layout, so extra height is not used intentionally.

## Recommended Approach

Use an "operation console" redesign, not a full JavaScript architecture rewrite.

This means:

- Keep the existing global function contracts and script load order.
- Keep `tx_button_optimized.js` in charge of PTT.
- Keep hidden compatibility DOM nodes for `controls.js`.
- Restructure visible mobile markup only where it improves hierarchy.
- Use CSS grid/flex layout to distribute vertical space intentionally.
- Use small JavaScript changes for labels, menu state, and input presentation.

## Information Architecture

The first viewport should have five stable zones:

1. Header console
   - Menu
   - Frequency display
   - Power
   - Compact status rail

2. Signal and RF panel
   - S-meter
   - PWR
   - SWR
   - ATU/device state

3. Control deck
   - Current mode, band, and filter controls
   - CW and FT8 navigation
   - DSP controls with enough height for touch
   - AF gain

4. Tuning and memory
   - Slow/fast left tuning
   - Step selector
   - Slow/fast right tuning
   - Six memory slots

5. Fixed transmit dock
   - PTT as the dominant action
   - REC, TUNE, and CQ as secondary actions

The page should remain a tool surface, not a landing page.

## Interaction Design

### Frequency

The frequency display stays visually dominant. Tapping it opens a focused numeric input state that is clearly an editor, not a broken display. The input should:

- Retain support for kHz, MHz, and Hz-style entries.
- Offer a clear active state.
- Preserve Escape/cancel and Enter/apply behavior.
- Avoid obscuring status controls.

### Mode, Band, and Filter

Visible buttons should express current state first. If cycling behavior remains, show the target in a secondary treatment such as a small "tap next" hint or title/aria label, not as the main label.

Examples:

- Current: `LSB`
- Secondary hint: `next CW`

If space is too tight for a hint, prefer showing current state only.

### DSP

DSP should no longer collapse below touchable size on small phones. The redesign should use either:

- A two-row compact control layout, or
- A collapsible DSP detail row with a stable summary.

The default visible state should make WDSP enabled/disabled obvious and show at least NR2 and AGC state.

### Memory Channels

Keep the six slots. Improve:

- Filled versus empty state
- Recall feedback
- Long-press save feedback
- Text legibility for frequencies and modes

Do not change the service-oriented memory-channel manager.

### Transmit Dock

PTT stays large, fixed, and visually dominant. REC, TUNE, and CQ remain reachable but secondary. Do not change the PTT ownership boundary:

- `tx_button_optimized.js` remains responsible for PTT event handling.
- TX-to-RX buffer flush timing and queue cleanup must not be modified as part of this redesign.
- TUNE and CQ paths must retain equivalent stop/unmute/flush behavior.

## Visual Direction

Use a restrained dark radio-console style:

- Dark neutral base with less one-note cyan saturation.
- Cyan for frequency and live connected state.
- Amber for memory and caution states.
- Red only for transmit/PTT and danger.
- 1px borders and subtle active states.
- Radius no larger than existing major surface radius unless needed for the PTT dock.
- No decorative orbs, blobs, or marketing-style hero composition.

The result should feel like an instrument panel: compact, legible, stable, and high-confidence.

## Responsive Strategy

Validate at minimum:

- 375 x 667
- 393 x 852
- 430 x 932

Small-height phones:

- Header and RF panel shrink gracefully.
- DSP remains touchable or collapses to a summary.
- Memory remains visible above the transmit dock.
- No visible controls overlap.

Tall phones:

- Extra vertical space should be assigned intentionally, mostly to the central console spacing or larger PTT dock.
- Avoid large dead gaps between memory and PTT.

Tablet/narrow desktop:

- Keep the existing centered max-width mobile frame behavior.

## State Coverage

The implementation must cover:

- Logged-in page load
- WebSocket connected and disconnected styling
- Power on/off visual state
- RX versus TX visual state
- Frequency input open, apply, and cancel
- Mode/band/filter cycling
- Memory empty, filled, saved, and recalled states
- Menu open/close
- DSP enabled, disabled, and per-effect active states
- Small and large viewport layouts

## Accessibility And Ergonomics

- Primary touch targets should be at least 44 px high where practical.
- Secondary dense controls should not drop below 32 px high.
- Controls need stable dimensions to prevent layout shift.
- Button labels must not overflow their container.
- ARIA labels should describe current state and action.
- The menu close button must be reachable after the slide animation completes.

## Testing Plan

Use the live authenticated route after implementation:

1. Load `/mobile` at 393 x 852.
2. Confirm the first meaningful screen renders.
3. Confirm no console errors or relevant warnings.
4. Open and close the menu.
5. Open and cancel frequency input.
6. Cycle step control and restore it to `1kHz`.
7. Check 375 x 667 and 430 x 932 screenshots for no overlap or unusable controls.
8. Verify PTT/TUNE/CQ layout without triggering real transmit actions.

If a local server is used for static visual work, final verification must still use `https://radio.vlsc.net:8891/mobile`.

## Risks

- `mobile_modern.js` and `controls.js` share globals. Changes must avoid redeclaring globals from `controls.js`.
- Hidden compatibility nodes in `mobile_modern.html` may look unused but are required.
- PTT and TX/RX timing are fragile. Do not refactor transmit behavior during visual work.
- Service worker caching can mask frontend changes. Use cache-busting query versions or hard reload during verification.
- The live site requires login before testing.

## Implementation Boundary

The first implementation pass should be limited to:

- Visible mobile DOM structure.
- CSS layout and visual system.
- Button labeling and ARIA/state improvements.
- Menu grouping and version display cleanup.
- Frequency input presentation.

Any deeper JavaScript modularization should be a separate future task after the redesign is stable.

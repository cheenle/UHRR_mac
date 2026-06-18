# Mobile Console Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `/mobile` into a tighter, clearer radio-console interface while preserving backend, WebSocket, memory, WDSP, and PTT/audio behavior.

**Architecture:** Keep the existing plain HTML/CSS/JavaScript stack and script load order. Introduce a small static guard test, then update visible mobile markup, CSS layout, and state-label helpers in `mobile_modern.js`; do not modify `controls.js` or `tx_button_optimized.js`.

**Tech Stack:** Python 3 stdlib tests, Tornado-served static HTML, vanilla JavaScript, CSS custom properties, in-app Browser validation against `https://radio.vlsc.net:8891/mobile`.

---

## File Structure

- Create: `dev_tools/test_mobile_console_static.py`
  - Focused stdlib regression test for mobile page invariants and redesign hooks.
- Modify: `www/mobile_modern.html`
  - Add semantic layout wrappers and grouped menu sections while preserving hidden compatibility elements and script order.
- Modify: `www/mobile_modern.css`
  - Replace the one-note compact layout with a responsive operation-console layout, improved touch sizes, grouped menu styling, and frequency editor styling.
- Modify: `www/mobile_modern.js`
  - Change mode/band labels to show current state, add secondary next-state hints, update ARIA labels, improve frequency input open/close state, and refresh menu version text.

Do not modify:

- `www/controls.js`
- `www/tx_button_optimized.js`
- `www/rx_worklet_processor.js`
- Backend WebSocket handlers

---

### Task 1: Add Mobile Static Guard Test

**Files:**
- Create: `dev_tools/test_mobile_console_static.py`
- Test: `dev_tools/test_mobile_console_static.py`

- [ ] **Step 1: Write the failing static guard test**

Create `dev_tools/test_mobile_console_static.py` with this content:

```python
#!/usr/bin/env python3
"""Static invariants for the MRRC mobile console page."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "www" / "mobile_modern.html"
CSS = ROOT / "www" / "mobile_modern.css"
JS = ROOT / "www" / "mobile_modern.js"


REQUIRED_HIDDEN_IDS = [
    "canRXsmeter",
    "RXinstant",
    "Txinstant",
    "div-filtershortcut",
    "div-mode_menu",
    "ombre-body",
    "pop-upspinner",
    "div-latencymeter",
    "div-smeterdigitRX",
    "div-bitrates",
    "callsign",
    "C_af",
    "SQUELCH",
    "encode",
]


REQUIRED_LAYOUT_HOOKS = [
    "console-header",
    "console-status-rail",
    "rf-panel",
    "control-deck",
    "mode-band-row",
    "dsp-panel",
    "tuning-memory-zone",
    "transmit-dock",
    "menu-section",
]


def read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8")


def assert_in_order(source: str, needles: list[str]) -> None:
    cursor = -1
    for needle in needles:
        pos = source.find(needle)
        if pos == -1:
            raise AssertionError(f"Missing ordered item: {needle}")
        if pos <= cursor:
            raise AssertionError(f"Item is out of order: {needle}")
        cursor = pos


def test_hidden_compatibility_nodes_are_preserved(html: str) -> None:
    for element_id in REQUIRED_HIDDEN_IDS:
        if f'id="{element_id}"' not in html:
            raise AssertionError(f"Missing hidden compatibility node #{element_id}")


def test_ptt_and_audio_script_boundaries_are_preserved(html: str) -> None:
    if 'id="ptt-btn"' not in html:
        raise AssertionError("PTT button id must remain #ptt-btn")
    assert_in_order(
        html,
        [
            'src="controls.js',
            'src="modules/ptt_manager.js"',
            'src="modules/tune_cq.js"',
            'src="mobile_modern.js',
            'src="tx_button_optimized.js"',
        ],
    )


def test_console_layout_hooks_exist(html: str) -> None:
    for hook in REQUIRED_LAYOUT_HOOKS:
        if hook not in html:
            raise AssertionError(f"Missing mobile console layout hook: {hook}")


def test_menu_is_grouped_and_version_is_current(html: str) -> None:
    if html.count("menu-section") < 3:
        raise AssertionError("Menu should be grouped into at least three sections")
    if "MRRC V5.6" not in html:
        raise AssertionError("Mobile menu version should show MRRC V5.6")


def test_css_has_responsive_console_rules(css: str) -> None:
    for token in [
        ".console-header",
        ".rf-panel",
        ".control-deck",
        ".transmit-dock",
        "@media (max-height: 700px)",
        "@media (min-height: 860px)",
    ]:
        if token not in css:
            raise AssertionError(f"Missing CSS rule token: {token}")
    if re.search(r"\.dsp-btn\s*\{[^}]*min-height:\s*clamp\([^;]*,\s*[^;]*,\s*(2[0-9])px", css, re.S):
        raise AssertionError("DSP buttons must not clamp to a sub-32px max height")


def test_js_uses_current_state_labels(js: str) -> None:
    for token in [
        "renderCycleButtonLabel",
        "setFrequencyEditorOpen",
        "syncMobileMenuVersion",
    ]:
        if token not in js:
            raise AssertionError(f"Missing JS helper: {token}")
    forbidden_patterns = [
        r"bandBtn\.textContent\s*=\s*nextBand\.name",
        r"modeBtn\.textContent\s*=\s*nextMode",
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, js):
            raise AssertionError(f"Button still renders next state as primary label: {pattern}")


def main() -> int:
    html = read(HTML)
    css = read(CSS)
    js = read(JS)

    checks = [
        lambda: test_hidden_compatibility_nodes_are_preserved(html),
        lambda: test_ptt_and_audio_script_boundaries_are_preserved(html),
        lambda: test_console_layout_hooks_exist(html),
        lambda: test_menu_is_grouped_and_version_is_current(html),
        lambda: test_css_has_responsive_console_rules(css),
        lambda: test_js_uses_current_state_labels(js),
    ]

    failures = []
    for check in checks:
        try:
            check()
        except AssertionError as exc:
            failures.append(str(exc))

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print("PASS: mobile console static invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run test to verify it fails against current UI**

Run:

```bash
python3 dev_tools/test_mobile_console_static.py
```

Expected:

```text
FAIL: Missing mobile console layout hook: console-header
FAIL: Missing mobile console layout hook: console-status-rail
FAIL: Missing mobile console layout hook: rf-panel
FAIL: Missing mobile console layout hook: control-deck
FAIL: Missing mobile console layout hook: mode-band-row
FAIL: Missing mobile console layout hook: dsp-panel
FAIL: Missing mobile console layout hook: tuning-memory-zone
FAIL: Missing mobile console layout hook: transmit-dock
FAIL: Missing mobile console layout hook: menu-section
```

The exact list may include additional failures for CSS and JS helpers. The important result is non-zero failure before implementation.

- [ ] **Step 3: Commit the failing guard test**

Run:

```bash
git add dev_tools/test_mobile_console_static.py
git commit -m "test: add mobile console static guard"
```

Expected:

```text
[main <hash>] test: add mobile console static guard
```

---

### Task 2: Restructure Mobile Markup Into Console Zones

**Files:**
- Modify: `www/mobile_modern.html`
- Test: `dev_tools/test_mobile_console_static.py`

- [ ] **Step 1: Update visible layout wrappers**

In `www/mobile_modern.html`, keep all hidden compatibility elements before `.mobile-modern-container`.

Change:

```html
<header class="app-header">
```

to:

```html
<header class="app-header console-header">
```

Change the status bar opening tag:

```html
<div class="status-bar">
```

to:

```html
<div class="status-bar console-status-rail" aria-label="Radio status">
```

Change:

```html
<div class="meter-display-frame">
```

to:

```html
<section class="meter-display-frame rf-panel" aria-label="Signal and RF status">
```

and change its matching closing `</div>` before `<!-- Quick controls - 精简版 -->` to:

```html
</section>
```

Change:

```html
<section class="quick-controls">
```

to:

```html
<section class="quick-controls control-deck" aria-label="Radio controls">
```

Change:

```html
<div class="control-row">
```

to:

```html
<div class="control-row mode-band-row">
```

Change:

```html
<section class="dsp-controls-section" id="dsp-controls">
```

to:

```html
<section class="dsp-controls-section dsp-panel" id="dsp-controls" aria-label="DSP controls">
```

Wrap the frequency tuning and memory sections in a new zone:

```html
<section class="tuning-memory-zone" aria-label="Tuning and memory">
    <section class="frequency-tuning-grid">
        ...
    </section>

    <section class="memory-channel-strip" aria-label="Memory channels">
        ...
    </section>
</section>
```

This replaces the previous sibling layout where `frequency-tuning-grid` and `memory-channel-strip` were direct children of `<main>`.

Change:

```html
<footer class="ptt-section">
```

to:

```html
<footer class="ptt-section transmit-dock" aria-label="Transmit controls">
```

- [ ] **Step 2: Group the off-canvas menu**

Replace the existing `<ul class="menu-list">...</ul>` in `www/mobile_modern.html` with:

```html
<div class="menu-section" aria-label="Radio">
    <div class="menu-section-title">Radio</div>
    <a href="#" class="menu-item" data-action="bands">Band Selection</a>
    <a href="#" class="menu-item" data-action="modes">Mode Selection</a>
    <a href="#" class="menu-item" data-action="memory">Memory Management</a>
    <a href="#" class="menu-item" data-action="settings">Radio Settings</a>
</div>
<div class="menu-section" aria-label="Audio">
    <div class="menu-section-title">Audio</div>
    <a href="#" class="menu-item" data-action="audio">Audio Controls</a>
    <a href="#" class="menu-item" data-action="txeq">TX Equalizer</a>
    <a href="recordings.html" class="menu-item">Recordings</a>
</div>
<div class="menu-section" aria-label="Digital">
    <div class="menu-section-title">Digital</div>
    <a href="#" class="menu-item" data-action="digital">Digital Modes</a>
    <a href="cw_live.html" class="menu-item">CW Decoder</a>
    <a href="ft8_ultron.html" class="menu-item">FT8</a>
</div>
<div class="menu-section" aria-label="System">
    <div class="menu-section-title">System</div>
    <a href="#" class="menu-item" data-action="logbook">Logbook</a>
    <a href="#" class="menu-item" data-action="about">About</a>
    <a href="#" class="menu-item" id="fullscreen-btn" data-action="fullscreen">Fullscreen</a>
</div>
```

Change:

```html
<span class="version-text">MRRC V4.9.2</span>
```

to:

```html
<span class="version-text" id="mobile-version-text">MRRC V5.6</span>
```

- [ ] **Step 3: Run static test and expect remaining CSS/JS failures**

Run:

```bash
python3 dev_tools/test_mobile_console_static.py
```

Expected:

```text
FAIL: Missing CSS rule token: .console-header
FAIL: Missing CSS rule token: .rf-panel
FAIL: Missing CSS rule token: .control-deck
FAIL: Missing CSS rule token: .transmit-dock
FAIL: Missing CSS rule token: @media (min-height: 860px)
FAIL: Missing JS helper: renderCycleButtonLabel
FAIL: Missing JS helper: setFrequencyEditorOpen
FAIL: Missing JS helper: syncMobileMenuVersion
```

- [ ] **Step 4: Commit markup restructuring**

Run:

```bash
git add www/mobile_modern.html
git commit -m "feat: restructure mobile console markup"
```

Expected:

```text
[main <hash>] feat: restructure mobile console markup
```

---

### Task 3: Implement Responsive Console CSS

**Files:**
- Modify: `www/mobile_modern.css`
- Test: `dev_tools/test_mobile_console_static.py`

- [ ] **Step 1: Add console layout rules**

In `www/mobile_modern.css`, append this block after the existing `.ptt-sublabel` rule and before the WDSP settings block:

```css
/* ========== Mobile Console Redesign ========== */
.console-header {
    padding: clamp(6px, 1.1vh, 10px) clamp(8px, 2vw, 12px);
}

.console-status-rail {
    gap: 6px;
    padding-top: 4px;
}

.console-status-rail .status-item {
    min-height: 22px;
    padding: 3px 8px;
    border-color: rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.035);
}

.main-content {
    justify-content: flex-start;
}

.rf-panel,
.control-deck,
.dsp-panel,
.tuning-memory-zone {
    width: 100%;
}

.rf-panel {
    background: linear-gradient(180deg, rgba(31, 34, 46, 0.88), rgba(18, 19, 28, 0.94));
    border-color: rgba(255, 255, 255, 0.1);
}

.control-deck {
    display: flex;
    flex-direction: column;
    gap: clamp(5px, 0.8vh, 8px);
}

.mode-band-row {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: clamp(5px, 1.2vw, 8px);
}

.quick-btn {
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
}

.quick-btn .btn-primary-label,
.quick-btn .btn-secondary-label {
    display: block;
    line-height: 1.05;
    pointer-events: none;
}

.quick-btn .btn-primary-label {
    font-size: 13px;
    font-weight: 700;
}

.quick-btn .btn-secondary-label {
    margin-top: 2px;
    font-size: 9px;
    color: var(--text-muted);
    font-weight: 600;
}

.quick-btn.state-current {
    border-color: rgba(0, 212, 255, 0.38);
    background: linear-gradient(180deg, rgba(0, 212, 255, 0.12), rgba(37, 37, 53, 0.88));
}

.dsp-panel {
    padding: clamp(5px, 0.8vh, 8px) clamp(8px, 1.8vw, 12px);
}

.dsp-buttons-row {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
}

.dsp-btn {
    min-height: 34px;
    padding: 5px 3px;
}

.dsp-btn-label {
    font-size: 10px;
}

.dsp-btn-status {
    max-width: 38px;
    overflow: hidden;
    text-overflow: ellipsis;
}

.tuning-memory-zone {
    display: flex;
    flex-direction: column;
    gap: clamp(8px, 1.2vh, 12px);
}

.frequency-tuning-grid {
    padding-top: clamp(3px, 0.6vh, 6px);
}

.memory-channel-strip {
    padding-bottom: 0;
}

.transmit-dock {
    background: linear-gradient(180deg, rgba(18, 18, 26, 0.96), rgba(10, 10, 15, 1));
}

.transmit-dock .ptt-container {
    max-width: 430px;
    margin: 0 auto;
}

body.frequency-editor-open .freq-main {
    opacity: 0.16;
}

body.frequency-editor-open .app-header {
    position: relative;
}

.freq-input-visible {
    display: block !important;
}

.freq-input-hidden.freq-input-visible {
    width: min(260px, calc(100vw - 132px));
    height: 56px;
    top: 50%;
    transform: translate(-50%, -50%);
    font-size: 30px;
    background: rgba(12, 14, 22, 0.98);
}

.menu-section {
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);
}

.menu-section-title {
    padding: 6px 16px 8px;
    color: var(--accent-primary);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.menu-section .menu-item {
    border-bottom: none;
    padding: 12px 16px;
}

@media (max-height: 700px) {
    .console-header {
        padding-top: 4px;
        padding-bottom: 4px;
    }

    .rf-panel {
        padding: 4px;
    }

    .dsp-panel {
        padding-top: 4px;
        padding-bottom: 4px;
    }

    .dsp-buttons-row {
        grid-template-columns: repeat(5, minmax(0, 1fr));
    }

    .dsp-btn {
        min-height: 32px;
    }

    .dsp-btn-icon {
        display: none;
    }

    .quick-btn .btn-secondary-label {
        display: none;
    }

    .memory-channel-strip {
        gap: 4px;
    }
}

@media (min-height: 860px) {
    .main-content {
        justify-content: space-between;
    }

    .tuning-memory-zone {
        margin-bottom: clamp(8px, 2vh, 24px);
    }

    .ptt-button {
        height: clamp(86px, 10vh, 104px);
    }
}
```

- [ ] **Step 2: Remove the old small-height DSP override that hides labels**

In the existing `@media (max-height: 700px)` block, delete this old rule:

```css
.dsp-btn-label {
    display: none;
}
```

Keep the rest of the media block unless it conflicts with the new block.

- [ ] **Step 3: Run static test and expect only JS failures**

Run:

```bash
python3 dev_tools/test_mobile_console_static.py
```

Expected:

```text
FAIL: Missing JS helper: renderCycleButtonLabel
FAIL: Missing JS helper: setFrequencyEditorOpen
FAIL: Missing JS helper: syncMobileMenuVersion
```

- [ ] **Step 4: Commit responsive CSS**

Run:

```bash
git add www/mobile_modern.css
git commit -m "feat: add responsive mobile console styling"
```

Expected:

```text
[main <hash>] feat: add responsive mobile console styling
```

---

### Task 4: Update Mobile State Labels And Frequency Editor

**Files:**
- Modify: `www/mobile_modern.js`
- Test: `dev_tools/test_mobile_console_static.py`

- [ ] **Step 1: Add a reusable current-state button renderer**

In `www/mobile_modern.js`, insert this helper before `function updateBandButtonLabel(currentBand)`:

```javascript
function renderCycleButtonLabel(button, currentLabel, nextLabel, actionLabel) {
    if (!button) return;
    button.classList.add('state-current');
    button.dataset.currentLabel = currentLabel;
    button.dataset.nextLabel = nextLabel;
    button.innerHTML = '<span class="btn-primary-label">' + currentLabel + '</span>' +
        '<span class="btn-secondary-label">next ' + nextLabel + '</span>';
    button.title = '当前: ' + currentLabel + ' · 点按切换到 ' + nextLabel;
    button.setAttribute('aria-label', '当前' + actionLabel + ' ' + currentLabel + ', 点按切换到 ' + nextLabel);
}
```

- [ ] **Step 2: Update mode and band label functions**

Replace the body of `updateBandButtonLabel(currentBand)` with:

```javascript
function updateBandButtonLabel(currentBand) {
    const bandBtn = document.getElementById('band-btn');
    if (!bandBtn || !currentBand) return;
    const currentIndex = MOBILE_BANDS.findIndex(band => band.name === currentBand.name);
    const nextBand = MOBILE_BANDS[(currentIndex + 1) % MOBILE_BANDS.length];
    bandBtn.dataset.currentBand = currentBand.name;
    bandBtn.dataset.nextBand = nextBand.name;
    renderCycleButtonLabel(bandBtn, currentBand.name, nextBand.name, '波段');
}
```

Replace the body of `updateModeButtonLabel(mode)` with:

```javascript
function updateModeButtonLabel(mode) {
    const currentMode = normalizeMobileMode(mode);
    const modeBtn = document.getElementById('mode-btn');
    if (!modeBtn) return;
    const currentIndex = MOBILE_MODES.indexOf(currentMode);
    const nextMode = MOBILE_MODES[(currentIndex + 1) % MOBILE_MODES.length];
    modeBtn.dataset.currentMode = currentMode;
    modeBtn.dataset.nextMode = nextMode;
    renderCycleButtonLabel(modeBtn, currentMode, nextMode, '模式');
}
```

- [ ] **Step 3: Add frequency editor state helper**

Insert this helper before `function showFrequencyInput()`:

```javascript
function setFrequencyEditorOpen(isOpen) {
    document.body.classList.toggle('frequency-editor-open', !!isOpen);
    if (domElements.freqDisplay) {
        domElements.freqDisplay.classList.toggle('hidden-for-input', !!isOpen);
        domElements.freqDisplay.setAttribute('aria-hidden', isOpen ? 'true' : 'false');
    }
    if (domElements.freqInput) {
        domElements.freqInput.classList.toggle('freq-input-visible', !!isOpen);
        domElements.freqInput.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
    }
}
```

In `showFrequencyInput()`, replace:

```javascript
domElements.freqDisplay.classList.add('hidden-for-input');
domElements.freqInput.classList.add('freq-input-visible');
```

with:

```javascript
setFrequencyEditorOpen(true);
```

In `hideFrequencyInput(apply)`, replace:

```javascript
domElements.freqInput.classList.remove('freq-input-visible');
domElements.freqDisplay.classList.remove('hidden-for-input');
```

with:

```javascript
setFrequencyEditorOpen(false);
```

- [ ] **Step 4: Add menu version sync**

Insert this helper before `document.addEventListener('DOMContentLoaded', function() {`:

```javascript
function syncMobileMenuVersion() {
    const versionEl = document.getElementById('mobile-version-text');
    if (!versionEl) return;
    versionEl.textContent = 'MRRC V5.6';
}
```

Inside the `DOMContentLoaded` callback, after `initializeElements();`, add:

```javascript
syncMobileMenuVersion();
```

- [ ] **Step 5: Run static test and verify it passes**

Run:

```bash
python3 dev_tools/test_mobile_console_static.py
```

Expected:

```text
PASS: mobile console static invariants
```

- [ ] **Step 6: Commit JS state-label changes**

Run:

```bash
git add www/mobile_modern.js dev_tools/test_mobile_console_static.py
git commit -m "feat: clarify mobile console state labels"
```

Expected:

```text
[main <hash>] feat: clarify mobile console state labels
```

---

### Task 5: Run Live Browser QA And Fix Layout Regressions

**Files:**
- Modify if needed: `www/mobile_modern.html`
- Modify if needed: `www/mobile_modern.css`
- Modify if needed: `www/mobile_modern.js`
- Test: live authenticated `/mobile`

- [ ] **Step 1: Run local static guard**

Run:

```bash
python3 dev_tools/test_mobile_console_static.py
```

Expected:

```text
PASS: mobile console static invariants
```

- [ ] **Step 2: Load live route at 393 x 852**

Use the in-app Browser against:

```text
https://radio.vlsc.net:8891/mobile
```

Expected:

```text
Page title: Ham Radio Modern Mobile
URL: https://radio.vlsc.net:8891/mobile
The first viewport shows frequency, status, RF panel, controls, tuning, memory, and PTT dock.
No relevant console error or warning is present.
```

- [ ] **Step 3: Verify non-transmit interactions**

Use Browser interactions:

```text
Open Menu -> grouped Radio/Audio/Digital/System sections visible -> close menu.
Tap frequency display -> numeric input visible -> press Escape -> input hidden.
Tap step selector until it returns to 1kHz.
Do not click PTT, TUNE, CQ, or power during QA unless the user explicitly authorizes radio-affecting actions.
```

Expected:

```text
Menu opens fully after animation and close button is visible.
Frequency input opens without covering the status rail.
Step selector can be restored to 1kHz.
PTT dock remains visible and stable.
```

- [ ] **Step 4: Check responsive viewports**

Use Browser viewport sizes:

```text
375 x 667
393 x 852
430 x 932
```

Expected:

```text
No visible overlap.
DSP dense controls are at least 32px high.
Primary controls are at least 44px high where practical.
Tall screens do not have a large dead gap between memory channels and PTT.
Text remains inside buttons and cards.
```

- [ ] **Step 5: Apply focused CSS fixes if QA finds issues**

If QA finds a visual issue, make the smallest CSS-only fix first. Examples:

```css
.memory-channel-strip {
    align-content: end;
}

.quick-btn .btn-primary-label {
    font-size: clamp(12px, 2.8vw, 14px);
}

.dsp-btn {
    min-width: 0;
}
```

Run the static guard again after every fix:

```bash
python3 dev_tools/test_mobile_console_static.py
```

Expected:

```text
PASS: mobile console static invariants
```

- [ ] **Step 6: Commit final QA fixes**

If files changed during QA, run:

```bash
git add www/mobile_modern.html www/mobile_modern.css www/mobile_modern.js
git commit -m "fix: polish mobile console responsive layout"
```

Expected if there were changes:

```text
[main <hash>] fix: polish mobile console responsive layout
```

If no files changed during QA, do not create an empty commit.

---

## Final Verification

Run:

```bash
python3 dev_tools/test_mobile_console_static.py
```

Expected:

```text
PASS: mobile console static invariants
```

Use the in-app Browser and record:

```text
URL: https://radio.vlsc.net:8891/mobile
Viewport: 375 x 667, 393 x 852, 430 x 932
Checks: page identity, nonblank render, no framework overlay, console health, screenshot evidence, menu interaction, frequency input interaction, step restore.
```

Final response should include changed files, commands run, Browser QA results, screenshots if useful, and remaining risk that PTT/TUNE/CQ were not clicked to avoid unintended radio transmission.

# Legacy Documentation

This directory contains older or reference documentation that has been centralized from the repository root, `DESIGN/`, `SDD/`, and the former top level of `docs/`.

Use `docs/current/` for code-verified current behavior. Use this directory for historical context, design background, troubleshooting history, and migration source material.

## Layout

| Directory | Contents |
| --- | --- |
| `architecture/` | Older system architecture, component, and end-to-end analyses |
| `atr/` | ATR-1000, ATU, tuner learning, and display troubleshooting notes |
| `audio/` | PTT, audio latency, WDSP, WebAudio, and performance notes |
| `design/original-design/` | Former `DESIGN/` files |
| `sdd/original-sdd/` | Former `SDD/` files |
| `mobile/` | Mobile interface docs, manuals, and iPhone-specific analysis |
| `operations/` | Multi-instance and operational guides |
| `methodology/` | FDE and ALDV2 methodology material |
| `methodology/superpowers/` | Former Superpowers specs and plans |
| `reviews/` | Code review and audit reports |
| `root/` | Former root-level topic documents |
| `tooling/` | Former tool-specific guidance such as `CLAUDE.md` |

## Status

Files here may be useful and may still contain correct details, but they are not the default source of truth. When a file is refreshed against the current implementation, move the updated content into `docs/current/` or link it from the relevant current document.

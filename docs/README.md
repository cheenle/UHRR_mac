# MRRC Documentation

This directory is the documentation home for the MRRC codebase.

Start with `current/` for code-verified documentation:

- `current/README.md` - documentation map and source-of-truth policy
- `current/architecture/current-system.md` - current runtime architecture
- `current/design/capability-map.md` - implemented capability inventory
- `current/operations/runtime-and-verification.md` - run and verification notes
- `current/methodology/code-first-docs.md` - documentation maintenance method
- `current/methodology/vibe-coding-practice.md` - Vibe Coding practice core document map
- `current/audit/documentation-cross-check.md` - cross-check against older docs

Reference and historical documents are grouped under `legacy/`:

- `legacy/architecture/` - older architecture and component analyses
- `legacy/design/` - original `DESIGN/` documents
- `legacy/sdd/` - original `SDD/` documents; this is the core Vibe Coding practice record
- `legacy/audio/` - audio, PTT, latency, WDSP, and WebAudio notes
- `legacy/atr/` - ATR-1000 and ATU notes
- `legacy/mobile/` - mobile UI and user manuals
- `legacy/operations/` - older deployment and multi-instance notes
- `legacy/methodology/` - FDE and ALDV2 methodology material
- `legacy/root/` - former root-level topic documents
- `legacy/tooling/` - former tool guidance documents

Treat `docs/current/` as the first place to update when code behavior changes.
Treat `legacy/sdd/original-sdd/` as preserved core methodology material for the project's Vibe Coding practice.

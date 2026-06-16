# Code-First Documentation Method

## Goal

Keep MRRC documentation aligned with the running system instead of preserving stale architectural claims.

## Documentation Layers

| Layer | Directory | Purpose |
| --- | --- | --- |
| Current facts | `docs/current/architecture/` | Runtime architecture verified from code |
| Current design | `docs/current/design/` | Implemented capabilities and design constraints |
| Current operations | `docs/current/operations/` | How to run, verify, deploy, and diagnose |
| Methodology | `docs/current/methodology/` | How docs are maintained |
| Vibe Coding practice | `docs/legacy/sdd/original-sdd/` | Core practice record, project narrative, and decision trail |
| Audit | `docs/current/audit/` | Cross-checks against legacy docs and known stale claims |
| Historical/reference | `docs/legacy/` | Preserve until migrated, corrected, or retired |

## Update Rules

1. Start from code, not from old diagrams.
2. Identify the runtime surface: route, WebSocket, script include, import, config key, or command.
3. Document the boundary: main process, optional separate service, static website, development tool, or historical reference.
4. Mark stale claims explicitly in the audit document.
5. Do not delete old docs until an equivalent current document exists and references are checked.
6. Preserve the original SDD as core Vibe Coding practice material. Correct runtime drift in `docs/current/`, but do not flatten or discard the SDD narrative.

## Evidence Checklist

For each documented capability, verify at least one of:

- HTTP route in `MRRC`.
- WebSocket route in `MRRC`.
- Python import in `MRRC`.
- Script/link loaded by `www/index.html` or `www/mobile_modern.html`.
- Runtime config in `MRRC.conf`.
- Startup/deployment reference in `mrrc_control.sh`, `mrrc_multi.sh`, `Dockerfile`, or `docker-compose.yml`.

## Classification

Use these labels when auditing files:

- `current`: agrees with implementation and can be maintained.
- `mostly-current`: broadly correct but has some version/path/port drift.
- `stale`: contains claims that no longer match code.
- `reference`: useful background, not a runtime source of truth.
- `archive-candidate`: not needed for current runtime, but should be preserved or moved only after review.

## Change Workflow

When code behavior changes:

1. Update the closest `docs/current/` file in the same change.
2. If older docs now conflict, add or update an entry in `docs/current/audit/documentation-cross-check.md`.
3. If a new runtime file is added and Docker needs it, check `Dockerfile`.
4. If a new route or frontend page is added, update `architecture/current-system.md` and `design/capability-map.md`.
5. If the change touches PTT/audio, cross-check `docs/legacy/audio/PTT_Audio_Postmortem_and_Best_Practices.md` before editing behavior.
6. If the change affects project framing, architecture intent, or design method, cross-check `docs/legacy/sdd/original-sdd/` and update `docs/current/methodology/vibe-coding-practice.md` if the interpretation changes.

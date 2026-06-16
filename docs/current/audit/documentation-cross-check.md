# Documentation Cross-Check

This audit compares current code behavior against existing documentation. It is intentionally conservative: old docs are centralized under `docs/legacy/` and not treated as disposable.

## High-Trust Current References

| File | Status | Notes |
| --- | --- | --- |
| `AGENTS.md` | current | Best compact operational guidance: port `8877`, `/` and `/mobile` behavior, Docker mounts, FT8 gotchas, PTT guardrails |
| `docs/legacy/architecture/Component_Detailed_Analysis.md` | mostly-current | Good component-level description; check individual line references before relying on them |
| `docs/legacy/architecture/Comprehensive_Architecture_Analysis.md` | mostly-current | Good current architecture overview; still needs boundary labels for optional services |
| `docs/legacy/atr/ATR1000_Tuner_Auto_Learning.md` | mostly-current | Matches proxy-based ATR-1000 architecture and learning/tune concepts |
| `docs/legacy/audio/PTT_Audio_Postmortem_and_Best_Practices.md` | mostly-current | Matches current PTT design principles and must be checked before PTT/audio edits |

## Known Stale Or Conflicting Claims

| Source | Claim | Current Code Fact |
| --- | --- | --- |
| `docs/legacy/tooling/CLAUDE.md` | `ATU_SERVER_WEBSOCKET.py` is a critical/active ATU server | Current active path is `atr1000_proxy.py` plus Unix Socket bridge from `MRRC`; no such active server file is present in the current route chain |
| `docs/legacy/tooling/CLAUDE.md` | `atu.js`, `atu_autotune.js` as active ATU functionality | Main entrypoints do not load those files; mobile ATR logic is in `www/mobile_modern.js`, bridge is `/WSATR1000` and `/WSATU` |
| `docs/legacy/tooling/CLAUDE.md` | SSL certs may be root `UHRH.crt`/`UHRH.key` | Current default config uses `certs/radio.vlsc.net.pem` and `certs/radio.vlsc.net.key` |
| `dev_tools/test_installation.py` | SSL smoke test checks `UHRH.crt` and `UHRH.key` | Active `MRRC.conf` uses cert files under `certs/` |
| `dev_tools/test_connection.py`, related debug HTML | Default target port `8888` | Active default port is `8877` |
| `mrrc_control.sh` | `start_mrrc` uses `Python "$SCRIPT_DIR/MRRC"` | Direct `python3 ./MRRC` is the reliable baseline on current systems |
| `README.md` | Mobile access example uses `/mobile_modern.html` | This static path works, but the server route `/mobile` is the primary handler that explicitly reads `www/mobile_modern.html` |
| Several architecture docs | Voice assistant appears as a core MRRC runtime flow | Voice assistant is a separate service (`voice_assistant_service.py`, default `8878`), not a main `MRRC` route |
| `docs/legacy/architecture/System_Architecture_Design.md` | Audio format sections describe RX/TX primarily as Int16 PCM | Current implementation supports runtime Opus mode negotiation and Opus is loaded by both main entrypoints |

## Legacy Reference Groups

| Group | Keep For | Migration Target |
| --- | --- | --- |
| root `README*.md` | User-facing project overview | Keep at root, link to `docs/current/` and selected `docs/legacy/` references |
| `docs/legacy/root/AOD.md`, `docs/legacy/root/DSP.md`, `docs/legacy/root/FDE.md`, `docs/legacy/root/architecture_methodology_complete.md` | Architecture/method background | `docs/current/methodology/` or `docs/current/architecture/` |
| `docs/legacy/design/original-design/` | Original structured design docs | Fold useful current requirements into `docs/current/design/` |
| `docs/legacy/sdd/original-sdd/` | SDD-style documentation | Preserve as historical/reference until reconciled |
| `docs/legacy/methodology/aldv2/` | Methodology reference | Keep as reference, link from methodology when needed |
| `website/` | Public static website source | Keep separate from runtime docs; not served by `MRRC` |
| `ft8/` docs | ULTRON-specific docs | Keep under `ft8/`; only MRRC bridge facts belong in `docs/current/` |
| `www/VOICE_ASSISTANT_README.md` | Voice assistant UI notes | Move/update only with voice assistant service docs |

## Cleanup Guidance From Documentation Audit

Do not use file name age alone to delete files. Use these categories:

- Runtime required: loaded/imported by current entrypoints or routes.
- Entrypoint reachable: linked from `index.html` or `mobile_modern.html`.
- Optional service: separate process used by documented features.
- Development/debug: useful for local testing, not runtime.
- Historical/reference: useful design or project knowledge.
- Generated/cache: safe to remove only when not containing user data.

Likely generated/cache examples include `__pycache__/`, `video_build/node_modules/`, and log files. Do not treat `recordings/`, `MRRC_users.db`, or `certs/` as disposable generated files.

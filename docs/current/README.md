# Current MRRC Documentation

## Purpose

`docs/current/` is the code-first documentation set for the current MRRC runtime. It does not replace all historical design notes yet. It provides a stable, layered home for the documents that should track actual implementation.

## Structure

```text
docs/current/
├── README.md
├── architecture/
│   └── current-system.md
├── design/
│   └── capability-map.md
├── methodology/
│   └── code-first-docs.md
├── operations/
│   └── runtime-and-verification.md
└── audit/
    └── documentation-cross-check.md
```

## Source Of Truth

When documentation disagrees, use this priority order:

1. Current code: `MRRC`, `MRRC.conf`, `www/index.html`, `www/mobile_modern.html`, loaded JavaScript, and directly imported Python modules.
2. Runtime scripts and deployment files: `mrrc_control.sh`, `mrrc_multi.sh`, `Dockerfile`, `docker-compose.yml`.
3. `docs/current/`.
4. `docs/legacy/`, `website/`, and feature-specific documents.

## Current Runtime Summary

- Main server: `MRRC`, a Python/Tornado executable.
- Default config: `MRRC.conf`.
- Default HTTPS/WSS port: `8877`.
- Desktop entry: `/` serves `www/index.html`.
- Mobile entry: `/mobile` serves `www/mobile_modern.html`; static direct access to `/mobile_modern.html` also works through static routing.
- Static assets: `www/`.
- Auth: `FILE` by default through `MRRC_users.db`.
- Key backends: `audio_interface.py`, `hamlib_wrapper.py`, `wdsp_wrapper.py`, `atr1000_proxy.py`, `atr1000_tuner.py`, `ft8_integration.py`.

## Migration Policy

Do not delete older documents until references have been checked. Migrate in this order:

1. Keep current behavior in `docs/current/`.
2. Mark stale claims in `docs/current/audit/documentation-cross-check.md`.
3. Rewrite old docs into `docs/current/` only after the code-backed replacement exists.

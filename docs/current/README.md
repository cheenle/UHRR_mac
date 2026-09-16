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
│   ├── code-first-docs.md
│   ├── vibe-coding-practice.md
│   └── project-retrospective-2026-09.md   (全历程复盘：阶段/问题图谱/方法验证/展望)
├── operations/
│   ├── product-support-lifecycle.md       (★ 总览：开发发版→升级→诊断→AI分析→回复解决)
│   ├── runtime-and-verification.md
│   ├── one-click-upgrade.md               (一键升级：机制/排障/发布/安全边界)
│   ├── release-process.md                 (发版清单：构建→验收→清单→部署→线上复核)
│   ├── hotfix-and-patching.md            (热修通道：哪些文件可热修)
│   ├── support-bundle.md                 (🐞 一键诊断包：脱敏/接收端/口令)
│   └── windows-installer-config-guide.md (Windows 安装版配置向导)
├── audit/
│   └── documentation-cross-check.md
└── reliability/
    ├── README.md                          (可靠性/安全性案例索引)
    ├── RC-001-ioloop-wedge-and-tx-silence.md
    └── RC-002-launcher-upgrade-and-shutdown.md  (启动器升级/退出链路的 Windows 陷阱)
```

## Source Of Truth

When documentation disagrees, use this priority order:

1. Current code: `MRRC`, `MRRC.conf`, `www/index.html`, `www/mobile_modern.html`, loaded JavaScript, and directly imported Python modules.
2. Runtime scripts and deployment files: `mrrc_control.sh`, `mrrc_multi.sh`, `Dockerfile`, `docker-compose.yml`.
3. `docs/current/`.
4. `docs/legacy/`, `website/`, and feature-specific documents.

The original SDD is a special case: `docs/legacy/sdd/original-sdd/` is preserved as the core Vibe Coding practice document set. Its implementation claims still need code verification, but its method, decision trail, and design narrative should be treated as primary project context.

## Current Runtime Summary

- Main server: `MRRC`, a Python/Tornado executable.
- Default config: `MRRC.conf`.
- Default HTTPS/WSS port: `8877`.
- Desktop entry: `/` serves `www/index.html`.
- Mobile entry: `/mobile` serves `www/mobile_modern.html`; static direct access to `/mobile_modern.html` also works through static routing.
- Static assets: `www/`.
- Auth: `FILE` by default through `MRRC_users.db`.
- Key backends: `audio_interface.py`, `hamlib_wrapper.py`, `wdsp_wrapper.py`, `atr1000_proxy.py`, `atr1000_tuner.py`.
- 产品支持链路总览见 `operations/product-support-lifecycle.md`；自动分诊 skill 见
  `.pi/skills/mrrc-support-triage/SKILL.md`；公开答复页 <https://www.vlsc.net/mrrc/answers/>。
- Windows 安装版附加：`windows/launcher.py`（启动器/热修/一键升级）、`upgrade_core.py`（升级纯逻辑）、
  `patch_overlay.py`（热修覆盖层）、`support_bundle.py`（诊断包）、`rig_models.py`（hamlib 机型表）、
  `packaging/pyinstaller/`（打包）与 `packaging/hotfix/`（热修包生成/应用/验收）。

## Migration Policy

Do not delete older documents until references have been checked. Migrate in this order:

1. Keep current behavior in `docs/current/`.
2. Mark stale claims in `docs/current/audit/documentation-cross-check.md`.
3. Rewrite old docs into `docs/current/` only after the code-backed replacement exists.

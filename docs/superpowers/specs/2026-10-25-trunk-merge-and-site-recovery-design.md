# 主干合流与 6.2.0 站点回正（设计）

日期：2026-10-25
范围：只做"合流 + 站点回正"。站点补页（②）、文档处境页（③）、云接入行为对齐（④）
各自另有规格，本文不涉及。

## 1. 背景

老产品仓 `UHRR_mac` 现在有两条分叉的线，且各自被一份克隆推着走：

| 线 | 位置 | 提交数（相对分叉点 `e94beb6`） | 内容 |
| --- | --- | --- | --- |
| `feat/hub` | `/HAM/hub/mrrc` | 21 | Cloud Hub 接入（`cloud_hub.py` / `base_path.py` / `session_metrics.py` / `www/cloud.html`）、V6.2.0 发版、站点 6.2.0 指针 |
| `feat/macos-packaging` | `/HAM/mrrc` | 3 | `global-nav.js?v=9` 失效缓存修复 + 部署路径改用 `/var/tmp`、全站顶栏加 Cloud Hub 入口、macOS 打包链计划 |

后果已经出现在线上：

- `https://www.vlsc.net/mrrc/downloads/latest.json` 仍是 **6.1.18**，`Last-Modified: 2026-09-18`；
- `MRRC-Setup-6.2.0.exe` 在线上（HTTP 200，服务端 sha256 = `3b25a7d3…a0fd`，与仓库 `latest.json` 一致）——
  **包发了，指针没发**；
- `/HAM/website/mrrc` 这个符号链接指向 `/HAM/MRRC/website`，也就是 **macos 线那份**。
  下一次从 `www.vlsc.net` 工作区部署，会把站点指针再次打回 6.1.18。

根因不是遗漏一次部署，而是**两份克隆各推各的分支**：谁是主干没有确定，部署源随"当前在哪份克隆里敲命令"而变。

## 2. 目标

1. `main` 成为唯一主干，两条线的全部提交都在其中；
2. 线上 `/mrrc/` 的 `latest.json` 指向 6.2.0，且**服务器侧** sha256 与清单一致；
3. 消除"部署源取决于在哪份克隆里执行"的结构性原因。

## 3. 非目标

- 不重启、不改 `:8891` 上正在运行的老实例（属产品层，见 ④）；
- 不新增站点页面、不改 `docs/current/` 的处境页（②③）；
- 不移植 mrrc_modern 的远程协助与 frpc 回收（④）。

## 4. 设计

### 4.1 合流

```
main (e94beb6)
  ├─ ff→ feat/hub            （21 提交，含云接入 + V6.2.0 + 站点指针）
  └─ merge --no-ff feat/macos-packaging   （3 提交，含 nav v9 与部署路径修复）
```

选 `feat/hub` 作基底的理由：云接入、V6.2.0 发版、站点 6.2.0 指针都在它上面；
反向以 macos 线为基底则要把这 21 个提交重放一遍，且要重做一次发版产物校验。

**合流可行性已在临时工作树实测**（`git worktree add --detach feat/hub` + 试合并）：

| 检查 | 结果 |
| --- | --- |
| 文本冲突 | 0（18 个 `website/*.html` 自动合并） |
| `dev_tools/release_check.py` | 26 处版本锚点全部 = 6.2.0 |
| `pytest tests/ dev_tools/test_{cloud_hub,path_prefix,session_metrics,ptt_liveness}.py` | 217 passed |
| 合并后同时具备 | 6.2.0 指针 + `global-nav.js?v=9` + 四个云接入文件 |

### 4.2 工作树收口

- `/HAM/hub/mrrc` 保留为 `feat/hub` 工作树（hub 相关工作的现场）；
- `/HAM/mrrc` 切到 `main`，它就是站点部署源（符号链接 `/HAM/website/mrrc` 已指向这里，不再改动链接）；
- 今后**发版与部署只在 `main` 上做**，`feat/hub` 仅作分支保留。

### 4.3 部署

用仓库根的 `./deploy_website.sh`（rsync `website/` → `www.vlsc.net:/var/www/vlsc.net/mrrc`，
远端 `--rsync-path="sudo rsync"`）。

已核对的风险点：

- `--delete` 会删远端多余文件。两端 `downloads/` 清单**完全一致**（含 `MRRC-Setup-6.2.0.exe`），
  实际只会删掉两个 macOS 元数据文件 `docs/._EFHW_Deep_Research_2026_v2_f38b3486.pptx`
  和 `efhw/._EFHW_Deep_Research_2026_v2_f38b3486.pptx`；
- 66 MB 的 6.2.0 包两端 sha256 一致，rsync 会跳过，不会重传。

## 5. 验收

| 判据 | 命令 | 期望 |
| --- | --- | --- |
| 主干含两条线 | `git log --oneline -3 main` | 出现 `merge:` 提交 |
| 版本锚点 | `dev_tools/release_check.py` | 全绿 |
| 单测 | `pytest tests/ …` | 217 passed |
| 线上指针 | `curl -s https://www.vlsc.net/mrrc/downloads/latest.json` | `"latest": "6.2.0"` |
| 服务端字节 | `ssh … sha256sum /var/www/…/MRRC-Setup-6.2.0.exe` | `3b25a7d3…a0fd` |
| 首页版本串 | `curl -s https://www.vlsc.net/mrrc/ \| grep -o 'V6\.[0-9.]*'` | 含 `V6.2.0` |

## 6. 回滚

- 合流未推送：`git reset --hard e94beb6`；
- 合流已推送：`git revert -m 1 <merge>` 后重推（不再 force-push `main`）；
- 站点：任取主干上一个提交重跑 `./deploy_website.sh`（`website/` 全量快照，无增量状态）。

## 7. 遗留（另立规格）

- ② 站点补处境入口：按 `docs/current/` 的实际内容定页，不照抄 mrrc_modern 的盒子六页（本产品无盒子）；
- ③ `docs/current/` 补处境页（安装/升级/排障/求助），结构借 mrrc_modern，内容只写老产品真有的能力；
- ④ 云接入行为对齐：`cloud_hub.py` 458 行 vs mrrc_modern 747 行，缺远程协助
  （`help_request/heartbeat/close`）、frpc 回收（`_enumerate_frpc`/`_terminate`）、
  `_free_loopback_port`、`reload_frpc`、`read_tunnel_settings`；验证用 `:8891` 那台实例。

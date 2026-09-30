# MRRC SDD

The full SDD has been moved into the centralized documentation tree:

- `docs/legacy/sdd/original-sdd/README.md`

This document set is preserved as the core Vibe Coding practice record for MRRC. It contains the project framing, architecture intent, design narrative, and decision trail.

Current runtime facts are maintained under:

- `docs/current/`
- `docs/current/methodology/vibe-coding-practice.md`

## 远程接入（已被产品化设计取代）

本仓的 `mrrc_tunnel.sh` + `com.user.mrrc.tunnel.plist` + `install_tunnel_service.sh` 是**第 0 代**
远程接入：SSH 反向端口转发 `localhost:8891/8892 → www.vlsc.net`，由远端 nginx 反代出
`radio1.vlsc.net`。它需要**服务器系统账号 + `ssh-copy-id` 免密**，每开一个实例都要人工动中心机，
无法扩展到多用户与多实例自助接入。该机制现已定位为**历史**。

现行与规划：

- **现状（生产）**：`mrrc_modern` 的 `deploy_listen_proxy.sh` —— IPv6 直连 + nginx 幂等反代
  （`https://www.vlsc.net/mrrc_modern/listen`，无隧道）
- **演进目标**：MRRC Cloud Hub [`../../mrrc_hub/SDD/README.md`](../../mrrc_hub/SDD/README.md)
- **取证评审**：[`../../mrrc_hub/docs/2026-09-30-fleet-hub-design-review.md`](../../mrrc_hub/docs/2026-09-30-fleet-hub-design-review.md)
  —— 其 §1.2 的 B1 即本仓上述脚本，B2 即 `mrrc_modern` 的 IPv6 方案

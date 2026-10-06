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

现行与规划（2026-10-04 更新）：

- **现状（生产）之一**：`mrrc_modern` 的 `deploy_listen_proxy.sh` —— IPv6 直连 + nginx 幂等反代
  （`https://www.vlsc.net/mrrc_modern/listen`，无隧道）
- **现状（生产）之二**：**MRRC Cloud Hub 阶段 1 已在真实公网运行** —— 唯一入口
  `https://<呼号>.mrrc.vlsc.net/`（443 + 通配真证书；`:8899`/`:9988` 与海外边缘路径已随
  V0.21 取消），呼号自助门户 `https://portal.mrrc.vlsc.net/` 已公网上线（申请 → 核验批准 →
  一次性口令认领）；mrrc_modern **v1.25.0 起"批准后实例自动接入"已产品化**（签证书 →
  登记 → 起隧道，服务端每 30 s 自查）。实况事实见
  [`../../mrrc_hub/SDD/12-operational-model.md`](../../mrrc_hub/SDD/12-operational-model.md) §12.8/§12.9
- **本仓产品的接入能力**：四项 hub 前置能力已齐备（路径前缀 `base_path`、令牌不进 URL、
  会话遥测、PTT 三层释放），尚未上线；接入计划与现网上线步骤见
  [`../docs/current/design/hub-parity-plan.md`](../docs/current/design/hub-parity-plan.md)，
  hub 侧对本仓的现状记录见上述 §12.8.1
- **设计基线**：MRRC Cloud Hub [`../../mrrc_hub/SDD/README.md`](../../mrrc_hub/SDD/README.md)
- **取证评审**：[`../../mrrc_hub/docs/2026-09-30-fleet-hub-design-review.md`](../../mrrc_hub/docs/2026-09-30-fleet-hub-design-review.md)
  —— 其 §1.2 的 B1 即本仓上述脚本，B2 即 `mrrc_modern` 的 IPv6 方案

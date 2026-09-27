# EFHW 天线 × ATR-1000 天调 深度分析项目全程复盘

时间：2026-09-27 ~ 2026-09-28
对象：BG1SB EFHW（4 楼窗台馈电，振子约 21 m，南偏西 40° 下斜至约 3 m 高树腰；UNUN 49:1，磁环 2643251002，2:14 匝）+ ATR-1000 自动天调 + MRRC radio1
状态：收尾完成。学习库全波段校准，工具链沉淀为可复用资产。

---

## 1. 起因

80m 波段的学习参数在更换 EFHW 的 49:1 UNUN 后整体失效——每次 SWR 都调不到 1.5 以下。
由此引出一个更大的问题：**学习库里到底还有哪些参数是可信的？** 单靠"用着没出问题"
无法回答，必须把库里的每条参数拿到真实天线上逐点回放验证。

## 2. 过程时间线

### 阶段一：数据推演与画像（9-27 白天）
- 基于半月内最新学习数据推演天调 LC 参数，绘制 7–30 MHz SWR 曲线。
- 产出天线深度研究报告并上线：`website/efhw/zh/bg1sb-antenna.html`
  （https://www.vlsc.net/efhw/zh/bg1sb-antenna.html）。
- pskreporter 看板 7 天裸数据交叉分析（发射/接收双向），辐射仰角/方位倒推验证。
- ON80 区域降雨记录 × `atr1000_radio1.log` SWR 变化对比，量化雨致失谐。
- 报告归档：`docs/current/antenna/efhw-49-1-antenna-analysis-2026-09-27.md`、
  `efhw-spots-rain-cross-analysis-2026-09-27.md`。

### 阶段二：bypass 裸 SWR 扫频基础设施（9-27 傍晚）
- 需求：干燥无雨环境下，天调 bypass（L=0/C=0）逐 10 kHz 扫全部业余段，拿裸天线真值。
- 产出扫频引擎 `antenna_sweep.py`（回调注入、可单测）+ API `/api/antenna_sweep/*` +
  前端 `www/antenna_sweep.html`（桌面 index 📡 按钮、移动端菜单"📡 天线扫频"）。
- **误报剔除**：扫频中发现孤立 SWR=1.00 点——未调谐不可能突变为 1，判定为电表
  反射通道掉读。清洗规则按"游程"判定（连续 ≤3 点的 1.00 且两侧邻点 >1.35 才剔除），
  并对误差点实发复测验证。
- 补扫 3.8–3.9 MHz 与 6.5–7 MHz，实测基波谐振 **f1 = 6.50 MHz**（1.00 平台
  6.42–6.58），反推振子电气长度 ≈21.5–21.9 m，与物理架设吻合。
- 干燥基线结论：15m 1.25（免调）< 20m 1.90 < 10m 2.48 < 40m 3.47 < 30m/12m ≈5.5
  < 17m 12.5（反谐振）< 80m 16.2（结构性死段，f1 压在段外，处处是上升翼）。

### 阶段三：天调参数推演与实测闭环（9-27 晚）
- 继电器拓扑方向实测判定：5351.5 kHz 对打实验（L44/C34 实测 2.32，拓扑 A 预测 1.81 /
  拓扑 B 预测 4.6）→ **sw=0 "LC" = 串联 L + 负载侧并联 C**；L=ind×0.1 µH，C=cap×10 pF。
- 最小二乘拟合实测阻抗锚点：5351.5 kHz Z=59+j112；18.1 MHz Z=14.4+j23.5；
  6.5 MHz 谐振点 50+j0。
- 5.3 MHz / 18.1 MHz 测算 → 实测验证闭环。
- 产出测算页 `website/efhw/zh/bg1sb-tuner-calc.html`（输入频率即出 sw/ind/cap +
  预计 SWR，公式与推导全部公开）。
- **关键教训**：设备实学优于计算最优。60m 计算"L35/C41 最优"实测 1.46，设备自己
  扫的 L29/C43 实测 1.02——阻抗反推不确定度 ±5 Ω/±15 Ω 传导到 L/C 就是 ±3~5 步，
  测算只能当种子，终值以设备调谐为准。

### 阶段四：全波段种子体检与修复（9-28 凌晨）
- `dev_tools/seed_healthcheck.py`：59 簇学习库参数逐点实测回放。首跑 **OK=28 / bad=20**。
- 第一轮修复 `fix_bad_seeds.py` 只成功一半（3 直接改写 + 2 调谐确认），6 个调谐点
  静默失败。查日志定位两个叠加根因：
  1. **MRRC PTTSafetyMonitor TOT=120 s 不豁免 tune**：长调谐会话 120.9 s 被强制收
     PTT（`mrrc_radio1.log` 有明确记录），TX 一断设备的 tune 命令被静默忽略。
     注意 `WS_AudioTXHandler.stoppttontimeout` 对 tune 有豁免（`MRRC:919`），但
     PTTSafetyMonitor 没有——设计缺口。
  2. **确认学习需继电器稳定 >8 s**：脚本盲睡 22 s 后自己切频，触发 MRRC getFreq
     轮询的自动应用，把稳定窗打断（7180 设备已扫到 L12/C44@1.07，差 1.1 s 没确认上）。
- 第二轮 `fix_bad_seeds2.py`：每个调谐点前 `tune:false→true` re-arm 重置
  ptt_start_time；发 tune 后轮询日志等"调谐确认学习"出现（最长 45 s）才走下一频点。
  结果全绿：7160/7200 设备调谐→1.00，7180/7170/7190 复测 1.00，14M 四个 CL 点补测
  1.0–1.38（证明体检 nodata 是测量假象），21405 改写 LC L0/C4。
- **10m 全族拓扑翻转**：旧 LC L2/Cx 族实测全部 9.4–13.7（完全失效），设备重调确认
  今天是 **CL L1/C8~C13**。用 4 个实测锚点最小二乘拟合 C=10.5+3.09×(f−28.856)，
  171 个 10 kHz 点全族重播，抽测 28.1→1.00、29.5→1.00、28.9→1.61。

### 阶段五：proxy V5.9.0 tune 确认学习
- `atr1000_proxy.py` V5.9.0：完整调谐结束后 15 s 窗内，若 settled SWR 较调谐前改善
  ≥0.05 且 ≤1.8，把设备选定的最终参数 force 写库，**不受 3 W 学习功率门限制**——
  修复弱 tune 载波（~2 W）下手动调谐结果永不入库、被旧库参数覆盖的"白调"问题。
  判据含 swr_raw≥100（拒绝 swr_raw=0 的伪 1.0）、频率未变、继电器非直通。
- 自动调谐触发阈值定为 SWR>2.0（严格大于，2.0 本身不触发），去抖 3.5 s。

## 3. 经验收获（按价值排序）

1. **孤立 SWR=1.00 永远是怀疑对象**。未调谐突变为 1 是电表掉读，不是谐振；真谐振在
   10 kHz 步进下必然平滑成平台。清洗要按游程判定——相邻掉读点会互相掩护。
2. **安全机制的豁免清单要一致**。PTT 超时豁免了 tune，TOT 硬上限没豁免，长会话工具
   全军覆没。工具侧 workaround：每 100 s 内 re-arm 一次 tune（false→true 重置计时）。
   根治要改 `MRRC` PTTSafetyMonitor 增加 tune_playing 豁免（未做，待决策）。
3. **设备确认学习是状态机，不是命令**。8 s 稳定窗期间任何继电器变动（包括自己脚本
   切频触发的自动应用）都会作废本次确认。自动化必须"发 tune → 等确认日志 → 才切频"。
4. **学习库会整体漂移失效，且可能拓扑翻转**。10m 从 LC 翻到 CL 不是参数偏差而是
   网络拓扑变了（天线阻抗状态随天气/环境迁移）。唯一可靠的巡检是实测回放
   （seed_healthcheck），不是看库里的 swr_avg 记录值。
5. **测算页的价值是播种和解释，不是替代调谐**。±3~5 步的不确定度决定了它用来
   填空位、预判拓扑、解释"为什么这个频段要这么多 C"，终值永远以设备实调为准。
6. **MRRC getFreq 轮询 → sync_freq_to_atr1000 会自动应用学习参数**，与手动
   set_relay 打架。一切测量工具：proxy 侧 `set_freq no_tune` + 按"继电器回显归属"
   过滤污染样本。
7. **tune 音停止陷阱**：ws 立即 close 会丢 tune:false（曾致 18 分钟常发）。所有工具
   收尾必须 `tune:false + setPTT:false + sleep(1)` 再 close。
8. **改学习库必须走 socket learn action**——proxy 内存缓存优先，直接改
   `atr1000_tuner.json` 运行中的 proxy 看不到。
9. **扫频前必须停 mrrc_modern**（它有独立的 SWR 守卫直连同一台 ATR-1000，会污染
   bypass 测量）；扫前备份学习库、扫后 diff 应为零。
10. **WS ~90 s 掉线**，工具一律处理 WebSocketClosedError 重连。

## 4. 沉淀的资产

| 资产 | 位置 |
|---|---|
| 扫频引擎 + API + 前端 | `antenna_sweep.py`、`/api/antenna_sweep/*`、`www/antenna_sweep.html` |
| 扫频分析/清洗/绘图 | `dev_tools/analyze_sweep.py` |
| 学习库拟合填空 | `dev_tools/fit_tuner_params.py` |
| 种子体检 | `dev_tools/seed_healthcheck.py`（报告 `seed_health_report.json`） |
| 坏种子修复（两轮） | `dev_tools/fix_bad_seeds.py`、`fix_bad_seeds2.py` |
| 拓扑判定/60m 拟合/调谐验证 | `dev_tools/topo_probe_60m.py`、`fit_60m*.py`、`tune_60m.py`、`test_tune_confirm.py` |
| 阈值边界测试 | `dev_tools/test_swr_retune.py` |
| proxy V5.9.0 确认学习 | `atr1000_proxy.py` |
| 天线画像页 | https://www.vlsc.net/efhw/zh/bg1sb-antenna.html |
| 频率→L/C 测算页 | https://www.vlsc.net/efhw/zh/bg1sb-tuner-calc.html |
| 分析报告×3 | `docs/current/antenna/`（本目录） |
| 操作技能 | `.pi/skills/antenna-sweep/SKILL.md` |

## 5. 遗留与后续

- PTTSafetyMonitor 的 tune 豁免（根治 TOT 掐断）未实施，需用户决策——tune 期间
  豁免 TOT 意味着失去绝对发射时长兜底，需权衡。
- 28900 kHz 设备调谐两轮均未确认（原因未单独查明），现为插值 CL L1/C11 实测 1.61，
  可接受；下次体检会自动覆盖。
- 17m/10m 阻抗天气敏感，雨后应重跑一次 seed_healthcheck 对比漂移。
- 80m（3.8–3.9 MHz）当前阈值 2.0 下 1.7x 不触发调谐，属预期行为（用户拍板）。

---
name: antenna-sweep
description: MRRC 天线 SWR 扫频画像与天调学习库维护——ATR-1000 bypass 裸 SWR 全段扫描、掉读点清洗、谐振结构推演、天调参数拟合填充、种子体检与坏种子修复、干/湿环境对比。当需要测量天线裸 SWR 曲线、验证雨致失谐、复测可疑频点、填充/校准天调学习库、排查"调谐了但没生效"、或更新天线画像报告时使用。
license: GPL-3.0
metadata:
  repo: HAM/mrrc
  reports: docs/current/antenna/
  engine: antenna_sweep.py
---

# 天线扫频画像 × 天调学习库维护

两条主线：
1. **扫频画像**：bypass（L=0/C=0）逐点发射短促 tune 载波，记录裸天线 SWR/功率。
2. **学习库维护**：体检（实测回放每条参数）→ 修复（设备调谐/插值/直接改写）→ 验证。

## 组件

| 件 | 位置 |
|---|---|
| 扫描引擎（回调注入、可单测） | `antenna_sweep.py` |
| API（GET status/list/result，POST start/stop） | `MRRC` `AntennaSweepApiHandler` → `/api/antenna_sweep/*` |
| 前端（选段/步进/驻留、实时曲线、历史叠加） | `www/antenna_sweep.html`（index 📡 按钮 / 移动端菜单） |
| 代理开关 | `atr1000_proxy.py`：`set_learning`、`set_autotune`、`set_freq no_tune`、`learn force_update` |
| 结果 | `antenna_sweeps/sweep_<ts>.json` + `latest.json` |
| 分析/清洗/绘图 | `dev_tools/analyze_sweep.py` |
| 天调参数拟合填充（只填空位） | `dev_tools/fit_tuner_params.py [--apply]` |
| 种子体检（实测回放学习库） | `dev_tools/seed_healthcheck.py` → `seed_health_report.json` |
| 坏种子修复（调谐+补测+改写） | `dev_tools/fix_bad_seeds2.py`（改 TUNE_POINTS/PROBE_POINTS/DIRECT_FIX 复用） |
| 频率→L/C 测算（含公式推导） | https://www.vlsc.net/efhw/zh/bg1sb-tuner-calc.html |
| 报告 | `docs/current/antenna/` |

## 怎么跑

```bash
# 全段扫频（312 点约 20 分钟）
curl -sk -b cookies.txt -X POST -H "Content-Type: application/json" \
  -d '{"bands":["40m","30m","20m","17m","15m","12m","10m"],"step_khz":10,"dwell_s":1.2,"note":"环境备注"}' \
  https://localhost:8891/api/antenna_sweep/start
# 只复测指定频点（掉读点复测、单点验证）
-d '{"freqs_khz":[7130,14090,29300],"dwell_s":2.5}'
# 分析出图
venv/bin/python dev_tools/analyze_sweep.py antenna_sweeps/sweep_<ts>.json
# 种子体检（实测回放全库，约 10 分钟）
venv/bin/python dev_tools/seed_healthcheck.py --full
# 坏种子修复（先编辑顶部的 TUNE_POINTS/PROBE_POINTS/DIRECT_FIX）
venv/bin/python dev_tools/fix_bad_seeds2.py
```

引擎自动完成：关学习+关自动调谐守卫 → set_relay(0,0,0) bypass → tone 常开 →
逐点 QSY + PTT（0.4s 稳定 + dwell 采样取中位）→ 放 PTT → 恢复开关并重新应用
当前频率学习参数。任何异常/中止必释放 PTT、恢复开关。

## 铁律（都是事故换来的）

1. **扫频前必须停掉 mrrc_modern**（FT-710 侧 `server.py`）。它有独立的
   SWR>2.0≥1.5s@≥5W 自动完整调谐守卫和 ≥3W 学习门，直连同一台 ATR-1000。
   它一旦触发调谐，后续所有"bypass"点都带着 L/C 测，数据全废（2026-09-27
   复测污染事故：7140 测出 1.08 实为被调谐后的值）。
   恢复用环境变量快照重启（`ps eww` 取 env，venv 在 `../mrrc_modern/venv`）。
2. **孤立 SWR=1.00 是电表反射通道掉读，不是谐振**。真谐振在 10kHz 步进下
   必然平滑。清洗规则（`split_dropouts`）：连续 ≤3 点的 1.00 游程、两侧最近
   非 1.00 邻点都 >1.35 → 移入 `dropped_points`。真平台（如 15m 16 点宽、
   边缘渐变）不会误杀。相邻掉读点会互相掩护，必须按游程判定。
3. **MRRC PTTSafetyMonitor TOT=120s 不豁免 tune**（`WS_AudioTXHandler` 豁免了，
   SafetyMonitor 没有——设计缺口）。长会话工具必须在每个调谐点前 re-arm：
   `tune:false → sleep 0.8 → tune:true`（PTT 下降沿+上升沿重置 ptt_start_time），
   否则 120.9s 被强制收 PTT，设备 tune 命令被静默忽略（2026-09-28 六连失败事故）。
4. **确认学习是状态机**：设备调谐完成后继电器需稳定 >8s 才确认写库。期间任何
   继电器变动（包括自己脚本切频触发的 MRRC getFreq 自动应用）都作废本次确认。
   自动化必须"发 tune → 轮询日志等 `调谐确认学习` → 才切频"，不许盲睡固定时长。
5. **MRRC getFreq 轮询 → sync_freq_to_atr1000 自动应用学习参数**，与手动
   set_relay 打架。测量工具：proxy 侧 `set_freq no_tune` + 按"继电器回显归属"
   过滤污染样本（样本的继电器状态必须等于目标状态才采纳）。
6. **改学习库必须走 proxy socket 的 learn action**（`force_update` 可覆盖）——
   proxy 用内存缓存，直接改 `atr1000_tuner.json` 运行中的 proxy 看不到。
7. **tune 音停止陷阱**：ws 立即 close 会丢 tune:false（曾致 18 分钟常发）。
   所有工具收尾必须 `tune:false + setPTT:false + sleep(1.0)` 再 close。
8. **WS ~90s 掉线**：一律 catch WebSocketClosedError 重连并重发 tune:true。
9. 扫前备份 `atr1000_tuner.json`、扫后 diff（应为零变化——学习/调谐都已关）。
10. 验收点：`grep -c "自动触发完整调谐" atr1000_radio1.log` 在扫描窗口内为 0。
11. 10m 段 tune 音前向功率仅 1-2W，是掉读重灾区；需要精确数据时加大 dwell
    或对 10m 单独复测。

## 学习库维护方法论（2026-09-28 实战验证）

- **体检是唯一可靠的巡检**：库里的 swr_avg 是历史记录值，不代表今天。天线阻抗
  随天气/环境迁移，可能整段漂移甚至**拓扑翻转**（10m 曾从 LC L2/Cx 整族翻成
  CL L1/C8-13，旧参数实测 9.4-13.7）。
- **修复三手段优先级**：设备调谐确认（最可信）> 邻近实测锚点插值（复测验证后可用）
  > 直接改写（必须有实测依据并在注释里写明来源频点）。
- **测算 vs 实学**：阻抗反推不确定度 ±5Ω/±15Ω 传导到 L/C 是 ±3~5 步。测算页
  用来播种、预判拓扑、解释趋势；终值永远以设备调谐为准（60m 实证：计算最优
  L35/C41 实测 1.46，设备自扫 L29/C43 实测 1.02）。
- **拓扑方向实测判定**（2026-09-27 对打实验）：sw=0 "LC" = 串联 L + 负载侧并联 C；
  L=ind×0.1µH，C=cap×10pF（0-127 步）。
- 体检 nodata 点多为测量假象（继电器回显归属过滤过严/设备连接抖动），补测
  通过即无需改库。

## 结果判读（2026-09-27 干燥基线）

f1=**6.50MHz**（SWR=1.00 平台 6.42–6.58，实测）；振子 ≈21.5–21.9m。
15m 1.25（全段免调）< 20m 1.90 < 10m 2.48 < 40m 3.47（全段需天调，f1 压在
段外故处处上升翼）< 30m/12m ≈5.5 < 17m 12.5（反谐振）< 80m 16.2（结构性死段）。
详见总报告 `docs/current/antenna/efhw-49-1-antenna-analysis-2026-09-27.md`，
项目全程复盘 `docs/current/antenna/efhw-atr1000-project-retrospective-2026-09-28.md`。

## 拟合填充学习库

`dev_tools/fit_tuner_params.py [--apply]`：实测锚点（样本加权+离群剔除）波段内
线性拟合，只填空位（10kHz 栅格、±5kHz 内无实测），新记录带 `source:"fit"` +
`sample_count:0` + `needs_verify:true`——真实学习自然覆盖，偏差大时 SWR 守卫
自愈。无锚点波段不填。写完要重启/重载 proxy 才生效。

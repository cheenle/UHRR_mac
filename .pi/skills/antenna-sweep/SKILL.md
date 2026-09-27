---
name: antenna-sweep
description: MRRC 天线 SWR 扫频与画像分析——ATR-1000 bypass 裸 SWR 全段扫描、掉读点清洗、谐振结构推演、天调参数拟合填充、干/湿环境对比。当需要测量天线裸 SWR 曲线、验证雨致失谐、复测可疑频点、填充天调学习库空位、或更新天线画像报告时使用。
license: GPL-3.0
metadata:
  repo: HAM/mrrc
  reports: docs/current/antenna/
  engine: antenna_sweep.py
---

# 天线扫频与画像（bypass 裸 SWR 基线）

目的：在 ATR-1000 直通（L=0/C=0）下逐点发射短促 tune 载波，记录裸天线 SWR/功率，
形成天线阻抗画像底稿。干/湿各扫一次可量化雨致失谐。

## 组件

| 件 | 位置 |
|---|---|
| 扫描引擎（回调注入、可单测） | `antenna_sweep.py` |
| API（GET status/list/result，POST start/stop） | `MRRC` `AntennaSweepApiHandler` → `/api/antenna_sweep/*` |
| 前端（选段/步进/驻留、实时曲线、历史叠加） | `www/antenna_sweep.html`（index 📡 按钮 / 移动端菜单） |
| 代理开关 | `atr1000_proxy.py`：`set_learning`、`set_autotune`、`set_freq no_tune` |
| 结果 | `antenna_sweeps/sweep_<ts>.json` + `latest.json` |
| 分析/清洗/绘图 | `dev_tools/analyze_sweep.py` |
| 天调参数拟合填充 | `dev_tools/fit_tuner_params.py` |
| 报告 | `docs/current/antenna/` |

## 怎么跑

```bash
# 全段（312 点约 20 分钟）
curl -sk -b cookies.txt -X POST -H "Content-Type: application/json" \
  -d '{"bands":["40m","30m","20m","17m","15m","12m","10m"],"step_khz":10,"dwell_s":1.2,"note":"环境备注"}' \
  https://localhost:8891/api/antenna_sweep/start
# 只复测指定频点（掉读点复测、单点验证）
-d '{"freqs_khz":[7130,14090,29300],"dwell_s":2.5}'
# 分析出图
venv/bin/python dev_tools/analyze_sweep.py antenna_sweeps/sweep_<ts>.json
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
3. 扫前备份 `atr1000_tuner.json`、扫后 diff（应为零变化——学习/调谐都已关）。
4. 验收点：`grep -c "自动触发完整调谐" atr1000_radio1.log` 在扫描窗口内为 0。
5. 10m 段 tune 音前向功率仅 1-2W，是掉读重灾区；需要精确数据时加大 dwell
   或对 10m 单独复测。

## 结果判读（2026-09-27 干燥基线）

f1=**6.50MHz**（SWR=1.00 平台 6.42–6.58，实测）；振子 ≈21.5–21.9m。
15m 1.25（全段免调）< 20m 1.90 < 10m 2.48 < 40m 3.47（全段需天调，f1 压在
段外故处处上升翼）< 30m/12m ≈5.5 < 17m 12.5（反谐振）< 80m 16.2（结构性死段）。
详见总报告 `docs/current/antenna/efhw-49-1-antenna-analysis-2026-09-27.md`。

## 拟合填充学习库

`dev_tools/fit_tuner_params.py [--apply]`：实测锚点（样本加权+离群剔除）波段内
线性拟合，只填空位（10kHz 栅格、±5kHz 内无实测），新记录带 `source:"fit"` +
`sample_count:0` + `needs_verify:true`——真实学习自然覆盖，偏差大时 SWR 守卫
自愈。无锚点波段不填。写完要重启/重载 proxy 才生效。

# NR2（EMNR）SSB 语音保护优化 — 设计规格

**日期**: 2026-09-13
**状态**: 待用户审查
**范围**: `DSP/wdsp/emnr.[ch]`、`DSP/wdsp/nbp.[ch]`、`wdsp_wrapper.py`、`audio_interface.py`、`MRRC.conf`(+模板)
**依据**: 本轮根因调查（见 §1 证据），调试版库在 `/tmp/wdsp_dbg`，探针脚本在 `dev_tools/nr2_*.py`

---

## 1. 问题与根因（已用证据定位）

### 1.1 现象
NR2 开启后 SSB 语音"变形过度"：发闷、发虚、机器人化、音节间抽吸。

### 1.2 根因链
EMNR 的最小统计噪声估计把**信号本身**当成噪声 → 掩码整体塌陷（0.02~0.25）→ 语音被整段削 10~33 dB 且几乎不区分信噪比 → 紧随其后的 AGC（`max_gain=10000`、`out_target≈0.98`、`panel=0.06`）再用 30~60 dB 补偿增益把残渣与掩码起伏放大回满量程。

### 1.3 关键证据
| # | 证据 | 数据 |
|---|---|---|
| E1 | 干净单音（1 kHz/0.2/零噪声）内部状态 | 该 bin `lambda_y=3.244e4`、`lambda_d=3.342e4` → `gamma=0.971`（<1）；`mask=0.0218`（−33 dB）；端到端 −37.1 dB（gm0+AE）/ −62.6 dB（AE 关） |
| E2 | 真实语音+10 dB SNR 的掩码分布 | 最强 100 bin：`gamma` 中位 3.09 → mask 0.245；最弱 100 bin：`gamma` 0.058 → mask 0.253；静音段 −19.0 dB vs 语音段 −18.3 dB → **SNR 仅改善约 1 dB** |
| E3 | 类语音合成（无噪声） | 最强 40 bin：`lambda_d=67.3 > lambda_y=28.0` → `gamma=0.445` → mask 0.083（−21.6 dB） |
| E4 | 端到端频响（延迟对齐，相干 0.99） | NR2 OFF −6.0 dB（链路固有）；NR2 ON(gm0) −16.5 dB；NR2 ON(gm2) −19.2 dB |
| E5 | 掩码下限实验（因果验证） | 下限 −12 dB：单音从 −37.1 → −15.3 dB，静音段降噪仅从 −19.2 → −14.4 dB |
| E6 | 机制 | `LambdaD` 的偏置补偿 `bmin=1+2(D−1)/QeqTilda`（D=72、Qeq=2 时达 6~72 倍）+ D=1.536 s 最小搜索窗 → 平稳段（持续共振峰/长音）必然被高估为噪声 |

### 1.4 顺带查实的隐患
| # | 现象 | 证据 |
|---|---|---|
| B1 | `bp1` 带通在 "非 NR 驱动" 状态下输出**全零**（生产靠 EMNR 把 gain 置 2.0 才侥幸工作） | 独立进程复现：`bp_only`/`bp_g1` → −144.7 dB；场景A（`nr2_enabled=False` 初始化）→ −89.1 dB；场景C（运行中关 NR2 再 `set_bandpass`）→ −89.1 dB；场景E（开 NB → gain 2.0）→ −11.3 dB ✅。链路内 dump 证实 `pre_bp1` RMS 0.070 → `post_bp1` RMS 0.000。强制 `setGain_bandpass(g=1.0/2.0, update=1)` 均无法救回 → **与 gain 数值无关，属掩码激活路径问题**，不做针对性修补 |
| B2 | `fexchange0` 饥饿(`error=-2`)时 wrapper 用原始输入顶替，而原始输入比处理后高约 18 dB | 实时节拍 6 s 内 3 次（启动段）；离线快喂时占比 >60%。实测 −2 会造成 5.3 ms 响 click + 时间线跳变 |
| B3 | `SetRXAAGCFixed(ch, x)` 单位是 dB | `wcpagc.c: fixed_gain = pow(10, x/20)`；现有 `1.0` = +1 dB |

---

## 2. 设计目标（SSB 语音）

1. **保语音**：EMNR 对任一 bin 的衰减不得超过可配置上限（默认 −12 dB），杜绝"整段削 10~19 dB"。
2. **保降噪**：静音段噪声抑制 ≥ 12 dB（当前 19 dB，允许换取语音保真）。
3. **不放大伪影**：取消"先砍 20~30 dB 再补 30~60 dB"的增益级；AGC 补偿增益封顶 +20 dB。
4. **消除静音地雷**：SSB 带通不再依赖 `bp1`。
5. **消除 click**：`-2` 时保持上一块输出，绝不再注入原始输入。
6. 全部新参数向后兼容（缺省即老行为可通过配置复现）。

---

## 3. 方案设计

### 3.1 C 端：EMNR 语音保护（`DSP/wdsp/emnr.c`, `emnr.h`）

新增字段（`struct _emnr.g`）：
```c
double max_atten;   // 线性掩码下限 = 10^(db/20)；0 = 关闭（老行为）
double dry;         // 干湿混合：mask' = dry + (1-dry)*mask；0 = 纯湿
```

新增导出（`PORT`）：
```c
void SetRXAEMNRmaxAttenDb (int channel, double db);   // db<=0；内部 max_atten = pow(10, db/20)
void SetRXAEMNRdry       (int channel, double dry);   // 0..1
```

生效点：`calc_gain()` 末尾、`aepf()` 之后（保证是所有 gain_method 的最终掩码）：
```c
if (a->g.dry > 0.0 || a->g.max_atten > 0.0) {
    for (k = 0; k < a->g.msize; k++) {
        double mk = a->mask[k];
        if (a->g.dry > 0.0) mk = a->g.dry + (1.0 - a->g.dry) * mk;
        if (a->g.max_atten > 0.0 && mk < a->g.max_atten) mk = a->g.max_atten;
        a->mask[k] = mk;
        a->g.prev_mask[k] = mk;      // 决策导向环保持一致
    }
}
```
`calc_emnr()` 初始化两个新字段为 0（= 老行为，便于回退）。

> 说明：`dry` 与 `max_atten` 数学上近似等价（`dry` 额外轻抬中间值、无硬拐点）。二者都实现，默认只用 `max_atten`，`dry` 作为可选平滑档（`nr2_dry` 配置项）。

### 3.2 C 端：SSB 带通改由 `nbp0` 承担（`DSP/wdsp/nbp.c`, `nbp.h`）

新增导出：
```c
void SetRXANBPFreqs (int channel, double f_low, double f_high);
```
实现（对标已有的 `setSamplerate_nbp` 模式，无泄漏）：
```c
void SetRXANBPFreqs (int channel, double f_low, double f_high)
{
    NBP a = rxa[channel].nbp0.p;
    EnterCriticalSection (&ch[channel].csDSP);
    a->flow  = f_low;
    a->fhigh = f_high;
    calc_nbp_impulse (a);                        // fnfrun=0 → fir_bandpass；fnfrun=1 → fir_mbandpass
    setImpulse_fircore (a->p, a->impulse, 1);    // 1 = 立即激活
    _aligned_free (a->impulse);
    LeaveCriticalSection (&ch[channel].csDSP);
}
```
> 与 `setSamplerate_nbp`/`setSize_nbp` 完全同构（`calc_nbp_impulse` 重新分配 `a->impulse` → 拷入 fircore → 释放），不引入新的内存管理约定。
`calc_nbp_impulse()` 已同时覆盖两条分支：notch 关闭时用 `fir_bandpass(a->nc, flow, fhigh, rate, wintype, 1, gain/(2*size))`；notch 开启时用 `fir_mbandpass(...)` 在新的 300–2700 通带内重建 passband 表（自动把 notch 限制在 SSB 频带内，符合预期）。

**为什么用 nbp0 而不是修 bp1**：
- `nbp0` 是 `xrxa` 中**无条件运行**的 FIR（`create_nbp(1, ...)`），实测可用（1 kHz 净增益 −6.0 dB，符合设计），完全不存在 B1 的 gain/掩码激活问题；
- 带通移到 EMNR **之前**（nbp0 在链路早期，早于 emnr）→ 进入噪声估计器的带外噪声减少 → 掩码更准（对 SSB 是纯收益）；
- 消除 "NR2 关 → 静音" 地雷。

**兼容处理**：`wdsp_wrapper.set_bandpass()` 改为调用 `SetRXANBPFreqs`，并**不再调用 `SetRXABandpassRun(1)`**（bp1 完全交给 WDSP 的 `RXAbp1Set` 管理：NR2 开时 WDSP 自己会开它）。

### 3.3 Python 端：增益级与健壮性（`wdsp_wrapper.py`）

| 项 | 现状 | 改为 |
|---|---|---|
| `_setup_nr2()` / `set_nr2_level()` | 只设 gain_method/npe/ae | 追加 `SetRXAEMNRmaxAttenDb(ch, level→上限)`；可选 `nr2_dry` |
| AGC 补偿增益 | `max_gain` 默认 10000(+80 dB) | 新增 `set_agc_top(db)` → `SetRXAAGCTop`，默认 **+20 dB** |
| AGC 时间常数 | attack 4 ms / decay 250 ms / hang 250 ms | SSB 默认 **attack 6 ms / decay 500 ms / hang 500 ms**（减少音节间抽吸）；保留原有模式切换 |
| panel 增益 | 0.06 | 配置项 `panel_gain`，默认 **0.35**（把 AGC 输出 ~0.98 落到 ~−9 dBFS，兼顾 Opus/16-bit）。**注意：这是一个可听见的电平提升（约 +15 dB），需在 CHANGELOG/手册中明确，并可配置回 0.06** |
| AGC OFF 固定增益 | `SetRXAAGCFixed(ch, 1.0)`（=+1 dB） | 改传 **0.0**（0 dB，线性 1.0） |
| `-2` 处理 | 返回原始输入（高 18 dB → click） | **保持上一块输出**（首次无历史则输出静音）+ 计数与限频告警 |
| 带通 | `SetRXABandpassRun(1)` + `SetRXABandpassFreqs` | `SetRXANBPFreqs`（见 §3.2） |

NR2 等级 → 参数映射（**最大衰减为主轴**，`psi/zeta` 为辅助；gain_method 保持现状以避免回归）：

| level | 名称 | max_atten | psi | zeta | 场景 |
|---|---|---|---|---|---|
| 0 | OFF | — | — | — | 关闭 |
| 1 | MIN | −6 dB | 8 | 0.70 | 极温和，几乎不动语音 |
| 2 | LOW（默认） | **−12 dB** | 12 | 0.65 | 日常推荐 |
| 3 | MED | −16 dB | 14 | 0.60 | 中等噪声 |
| 4 | HIGH | −20 dB | 18 | 0.55 | 强噪声，接受更多变形 |

### 3.4 配置（`MRRC.conf` / `windows/MRRC.conf.template`）

新增（全部有默认值，缺省即 §3.3 的推荐值）：
```ini
# NR2 每 bin 最大衰减(dB)。0=不限制(旧行为)；越小越自然、降噪越弱
nr2_max_atten_db = -12
# NR2 干湿混合(0~1)：>0 时 mask' = dry+(1-dry)*mask（比硬下限更平滑）
nr2_dry = 0.0
# AGC 最大补偿增益(dB)：限制"砍完再狂补"的增益级
agc_top_db = 20
# 输出电势（panel）：AGC 输出 ~0.98 × 此值
panel_gain = 0.35
```
`audio_interface.py`：读入以上键；**同步更新 `PyAudioCapture._wdsp_config_hash` 的元组**（含 `nr2_max_atten_db`、`nr2_dry`、`agc_top_db`、`panel_gain`），否则运行中改配置不生效。

### 3.5 前端
v1 **不改**：`/CONFIG` 的 NR2 等级 0–4 已覆盖"语气保真度"主轴；新增键先走配置文件。UI 旋钮列入后续可选。

### 3.6 打包（必须同步，否则线上不生效）
- macOS/Linux：`cd DSP/wdsp && make` → `libwdsp.dylib|so`；现有的 `install`/`mrrc_setup.sh` 路径按仓库现状（系统库 `/usr/local/lib/`，注意 wrapper 的搜索顺序里 `/usr/local/lib` 在仓库目录之前）。
- Docker：确认镜像内是否从 `DSP/wdsp` 源码构建；若是，需保证新增导出的 C 文件被打进构建上下文（`Dockerfile` 目前只拷贝选定文件）。
- Windows：`vendor/wdsp/windows/bin/x64/` 的 DLL 需用同一 patch 重编（`win_pack.md` 增补说明）。

---

## 4. 验收标准（可执行）

| # | 检查 | 命令/脚本 | 通过标准 |
|---|---|---|---|
| A1 | 单音不再被塌陷 | `python3 dev_tools/nr2_internals.py`（调试库） | 1 kHz 处 mask ≥ 0.15（现 0.022） |
| A2 | 掩码开始利用信噪比 | `python3 dev_tools/nr2_mask.py` | 语音最强/最弱 bin 掩码差 ≥ 6 dB（现 ≈0） |
| A3 | 端到端权衡 | `python3 dev_tools/nr2_prod_ab.py --secs 8` | NR2 ON(level2)：静音段 ≤ −12 dB 且语音段 Δ ≥ −6 dB（现 −14.3 dB）；LSD 不劣于现状 |
| A4 | 静音地雷消除 | `nr2_scenario_probe.py A C D` | 增益 > −20 dB（不再静音） |
| A5 | 带通生效 | 新脚本 `dev_tools/nr2_band_tf.py`：白噪激励测 nbp 频响 | 300–2700 通带 ≈0 dB，带外 ≤ −30 dB |
| A6 | `-2` 无 click | 新脚本 `dev_tools/nr2_starve.py`：故意快喂制造饥饿 | 输出为上一块（无 +18 dB 突发），告警计数递增 |
| A7 | 回退路径 | `nr2_max_atten_db=0, agc_top_db=80, panel_gain=0.06` | 与旧行为一致（误差 < 1 dB） |
| A8 | 不破坏既有功能 | `python3 dev_tools/test_installation.py`；MRRC 启动、RX/TX、PTT、ATR-1000 仪表 | 无回归 |
| A9 | 听感 | `dev_tools/nr2_out/prod_*.wav`（新旧对照） | 用户主观确认"变形"消失 |

---

## 5. 风险与回退

| 风险 | 缓解 |
|---|---|
| 改 `nbp0` 频点影响 notch 逻辑（`bplow/bphigh`） | NF 手动陷波与 nbp0 共用 notch 数据库：改频点后 notch passband 会在 300–2700 内由 `calc_nbp_impulse`→`make_nbp` 重建，属预期行为；A8 中需实测 `set_notches_enabled(True)` + `add_notch(1000,100)` 仍生效 |
| panel/AGC 改动导致音量整体变化 | 全部走配置；A7 一键回退；`agc_top_db` 与 `panel_gain` 独立 |
| 掩码下限过高导致降噪变差 | 等级 0–4 分级 + `nr2_max_atten_db` 可调；A3 量化 |
| C 端改动破坏其它模式（CW/AM/FM/DRM） | 只动 EMNR 与 nbp 频点设置，不改链路结构；跑 `dev_tools/test_installation.py` + 各模式手工抽查 |
| 打包遗漏（Docker/Windows） | §3.6 列为必做项，实现计划中单列任务 |

**回退**：`/usr/local/lib/libwdsp.dylib` 先备份；配置键清零/改回即恢复旧行为（A7 验证）。

---

## 6. 不做（YAGNI）

- 不重写降噪算法、不引入 Python 侧谱减；不改 gain_method 体系（证据显示三者差异不显著，改动只增加回归面）。
- 不新增前端旋钮（v1 用配置 + 等级映射）。
- 不针对 `bp1` 的 gain=1.0 做修补（机制未完全定位，且新路径已绕开它）；仅在 §1.4 记录该隐患。
- 调试探针（`emnr_dump`/`bp1_dump`/`stage dump`）**不进生产源码**；需要时按本规格附录在 `/tmp` 重建调试库（已在 `/tmp/wdsp_dbg` 留有可用副本）。

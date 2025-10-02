# UHRR 发射（TX）/接收（RX）稳定性复盘与最佳实践

本文对在浏览器端使用 UHRR 时遇到的典型不稳定问题进行系统复盘，给出工程对策与“可工作的稳定基线”。重点聚焦 TX 的 100% 可靠起发与 RX 的低抖动。

---

## 1. 现象与根因汇总

### 1.1 PTT 按下无发射、松开才闪一下
- 现象：按住 TX 按钮期间无发射，松开瞬间电台“闪一下”。
- 根因链：
  1) 前端时序不当：先发 `setPTT:true`，但 TX 音频通道未初始化（未发送 `m:`）或首包未及时到达。
  2) 后端判定方式：仅用“时间阈值”（如 0.5s 内未收到音频→PTT 自动熄灭），对网络/线程抖动敏感。
  3) 竞争/延迟：`wsAudioTX` 未 OPEN 或 Opus 编码器首帧耗时，导致“PTT→首包”之间出现空窗。

### 1.2 TX 偶发失败（10 次里 1~2 次）
- 根因：同 1.1 的轻度版——空窗略大于后端阈值时被误判熄灭。

### 1.3 RX 音频滞后/抖动、发射后更明显
- 根因：接收缓冲未控深、累积；ScriptProcessor 主线程抖动；采样率不一致产生重采样抖动；TX 结束未清理尾部缓存。

### 1.4 发射音量过小或放大后失真
- 根因：前端存在固定 `/10` 衰减；去掉后如未控峰值容易削波。

### 1.5 TLS 证书报错（BAD_END_LINE/链条不完整）
- 根因：CR/LF 混用、行尾反斜杠；fullchain 拼入根证书；未用 `SSLContext` 标准加载。

---

## 2. 已落地对策（代码层）

### 2.1 TX 起发“确定性流程”（前端 + 后端协同）
- 目标：按下→立刻 PTT，同时确保后端在超时/计数窗口内必然收到音频，避免误判熄灭。
- 前端（`www/tx_button_optimized.js`）：
  1) 按下：立即 `setPTT:true`（最高优先级）
  2) 并行：`toggleRecord(true)` 发送 `m:rate,encode,op_rate,op_frm_dur`（TX_init）
  3) 预热：立即发送10个更强的预热帧（每10ms发送一帧）保证首秒内持续有音频
  4) 确认：PTT命令发送后增加确认机制，最多重试3次确保命令到达
  5) 松开：`s:`（停止/清尾）→ `setPTT:false`，立即切回 RX
- 后端（`UHRR`）：
  - 由“时间阈值”改为“未收帧计数超时”：每 0.2s 检查一次，连续 10 次未收到音频帧才熄灭 PTT；收到帧即清零计数。
  - PTT命令执行增加重试机制：最多尝试3次确保PTT命令成功执行
  - 控制路径 `WS_ControlTRX.on_message` 中 `setPTT` 快速处理，立即广播 `getPTT:<state>`。

### 2.2 RX 低抖动播放
- 引入 `AudioWorkletNode`（`www/rx_worklet_processor.js`）在音频线程播放：
  - 目标深度区间：32/64（更稳可 64/128，低延迟可 16/32）
  - 过深截尾、过浅补零
- `controls.js` 控深 `AudioRX_audiobuffer`，TX 结束清尾，避免滞后堆积。

### 2.3 TX 输入增益与软限幅
- 取消固定 `/10` 衰减，改为 1:1 输入；
- 用 `MIC GAIN` 滑块与后端/声卡增益做微调；
- 如需保护，可在编码前加软限幅（-3 dBFS）。

### 2.4 TLS 证书链与加载
- 只拼“服务器证书 + 中间证书”为 `fullchain.pem`；
- 统一 LF，移除行尾反斜杠；
- 使用 `ssl.SSLContext.load_cert_chain(certfile=fullchain, keyfile=key)`。

---

## 3. 可工作的稳定基线（建议默认）
- 采样/编码：端到端 24 kHz；Opus 60 ms 帧（可选 20 ms 降延迟）
- RX Worklet 缓冲：32/64（更稳用 64/128）
- 后端超时：未收帧计数 10×200ms（≈2 s），收到帧清零
- TX 输入：1:1 增益，必要时软限幅（建议保留控件）
- TLS：`fullchain.pem`（服务器+中间）、`<domain>.key`，`SSLContext` 加载

> 该基线下，TX 按下即发射；RX 抖动低、延迟稳定；TLS 兼容主流浏览器。

---

## 4. 操作/排错速查
- 按下不发射、松开闪：
  - 是否采用“按下即 PTT + 并行 TX_init + 立即发送10个预热帧”？
  - miss_count 阈值是否过低（现在是10次检查，每次200ms）
- RX 卡顿/延迟增长：
  - 提升 Worklet 缓冲（32/64→64/128）；固定 24 kHz；限制接收环形缓冲长度
- 发射音量：
  - `MIC GAIN`/声卡输出微调；若炸音，加软限幅或降 `MIC GAIN`
- 证书错误：
  - 仅拼服务器+中间证书；修正换行符；用 `SSLContext`；`openssl s_client` 验证链
- 端口占用：
  - `lsof -iTCP:<port> -sTCP:LISTEN` 清理旧进程，或用守护工具保证单实例

---

## 5. 进一步优化建议
- 前端：
  - UI 显示 TX/RX 码率、缓冲深度、miss_count、PTT 状态
  - PTT状态实时显示已实现，可考虑增加更多状态细节显示
- 后端：
  - 首帧“保护期”：PTT 刚开 200 ms 内更高容忍度，与计数法叠加
  - 日志按秒统计，降低噪声
- 编解码：
  - 低延迟需求下可用 20 ms 短帧，配合更小缓冲，但抖动容忍度下降

---

## 6. 参考与致谢
- 上游项目与文档启发：F4HTB/Universal_HamRadio_Remote_HTML5（Wiki）
  - https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5/wiki

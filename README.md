# Universal HamRadio Remote (UHRR)

面向短波电台的 Web 远程控制与音频流系统。前端基于 HTML5/JS，后端基于 Tornado + PyAudio + rigctld（Hamlib）。本版本已针对 macOS/移动端和 TLS 做了修复与优化，并显著改善了 TX/PTT 时序与 RX 抖动。

> ✅ **重要优化**：已解决TX到RX切换延迟问题（从2-3秒优化到<100ms），详情请参见 [docs/latency_optimization_guide.md](docs/latency_optimization_guide.md)

## 功能特性
- 浏览器端操作：频率、模式、PTT（按下立即发射、松开立即停止）
- 双向音频：TX 端 Opus 编码，RX 端低抖动播放（AudioWorklet），采样率 24 kHz
- TLS/证书：支持自有证书链（fullchain + 私钥）
- 后端：Tornado WebSocket，PyAudio 采集/播放，rigctld 控制电台
- **增强的PTT可靠性机制**：按下即发送PTT命令，并立即发送预热帧确保后端收到音频数据
- **优化的TX/RX切换**：几乎实时的模式切换（<100ms延迟）
- **移动端优化**：针对触摸屏设备优化的UI和交互

## 快速开始（macOS）
1. 依赖
   - Python 3.12+
   - Hamlib/rigctld 已安装并可用
   - PyAudio（基于 PortAudio）
2. 启动 rigctld（示例，按你的实际串口/参数调整）：
   ```bash
   rigctld -m 335 -r /dev/cu.usbserial-230 -s 4800
   ```
3. 配置 TLS 证书（可选但推荐）
   - 将你的证书放入 `certs/`：
     - `certs/fullchain.pem`（服务器证书 + 中间证书）
     - `certs/radio.vlsc.net.key`（私钥）
   - 编辑 `UHRR.conf`：
     ```ini
     [SERVER]
     port = 443
     certfile = certs/fullchain.pem
     keyfile = certs/radio.vlsc.net.key
     ```
4. 启动服务
   ```bash
   python ./UHRR
   ```
   - 控制台应显示 `HTTP server started.`
   - 若占用端口，请先清理旧进程
5. 访问
   - `https://<你的域名或IP>/`（若使用443）或 `https://<host>:8888/`

## 目录结构要点
- `www/`：前端页面与脚本
  - `controls.js`：音频与控制主逻辑（包含 TX Opus 编码、RX Worklet 播放、码率显示、PTT命令确认与重试等）
  - `tx_button_optimized.js`：TX 按钮事件与时序（包含增强的PTT可靠性机制和延迟优化）
  - `rx_worklet_processor.js`：AudioWorklet 播放器（低抖动）
- `UHRR`：后端主程序（Tornado + WebSocket + SSLContext）
- `audio_interface.py`：PyAudio 采集/播放封装与客户端分发
- `hamlib_wrapper.py`：与 rigctld 通信的辅助逻辑
- `certs/`：证书相关
  - `fullchain.pem`、`radio.vlsc.net.key`（生产使用）
  - `legacy/` 存放历史证书（已迁移）
- `dev_tools/`：测试/调试脚本与页面（非生产）
- `logs/`：运行日志
- `docs/`：技术文档
  - `System_Architecture_Design.md`：系统架构设计文档
  - `PTT_Audio_Postmortem_and_Best_Practices.md`：PTT/音频稳定性复盘
  - `latency_optimization_guide.md`：TX/RX切换延迟优化指南

## 关键配置
- `UHRR.conf`
  - `[SERVER] port`：监听端口（生产建议 443）
  - `[SERVER] certfile/keyfile`：fullchain 与私钥路径
  - `[CTRL].interval_smeter_update`：S 表更新周期
  - `[AUDIO] inputdevice/outputdevice`：音频设备名
  - `[HAMLIB] rig_pathname/rig_rate/rig_model`：电台串口与参数

## 音频与时序策略
- TX：
  - 前端 `OpusEncoderProcessor`：`opusRate = 24000`，`opusFrameDur = 60ms`
  - 后端 `WS_AudioTXHandler` 接收并播放；PTT 超时保护（无数据 2s 自动断开）
  - **增强的PTT可靠性机制**：按下即发送PTT命令，并立即发送10个预热帧确保后端收到音频数据
- RX：
  - 后端 `AudioRXHandler.tailstream` 批量下发减少抖动
  - 前端 `AudioWorkletNode` 播放，设置缓冲深度（优化后 16/32 帧，平衡延迟与稳定性）
  - **优化的缓冲区管理**：TX释放时立即清除RX缓冲区，实现<100ms的切换响应

## TLS/证书注意事项
- fullchain.pem 应仅包含"服务器证书 + 中间证书"，不要拼根证书
- 若从 Windows/某些面板导出，请统一换行（LF），去除行尾反斜杠
- 后端已使用 `ssl.SSLContext` 加载证书链与私钥

## 常见问题排错
- 端口占用：
  ```bash
  lsof -iTCP:443 -sTCP:LISTEN -n -P
  kill -9 <PID>
  ```
- 证书错误（bad end line）：
  - 用 `sed -e 's/\r$//'` 规范换行
  - 确认 `-----BEGIN/END CERTIFICATE-----` 行完整
- TX 按下不立即发射：
  - 确认页面电源按钮已开启，WebSocket 已连接
  - 后端采用增强的PTT可靠性机制：按下即发送PTT命令，并立即发送10个预热帧确保后端收到音频数据
  - 后端使用计数超时法（连续10次未收到音频帧才熄灭PTT，每次检查间隔200ms）替代时间阈值法
- RX 抖动：
  - 保持 24k 端到端一致
  - 可调整 Worklet 缓冲（例如 16/32 或 32/64）
- TX到RX切换延迟：
  - 已优化缓冲区清除机制和PTT命令处理，实现<100ms切换响应
  - 详情请参见 [延迟优化指南](docs/latency_optimization_guide.md)

## 文档
- **[系统架构设计文档](docs/System_Architecture_Design.md)**: 完整的系统架构设计、组件关系、接口协议、部署方案和技术规范
- **[PTT/音频稳定性复盘](docs/PTT_Audio_Postmortem_and_Best_Practices.md)**: TX/RX 稳定性问题深度分析与最佳实践
- **[TX/RX切换延迟优化指南](docs/latency_optimization_guide.md)**: 延迟问题分析与优化方案详细文档

## 开发与测试
- 所有测试/调试脚本位于 `dev_tools/`，不参与生产部署
- 推荐在独立分支进行实验性修改

## 许可与合规
- 本项目遵循 **GNU General Public License v3.0 (GPL-3.0)** 许可证
- **项目来源**: 基于 [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5) 开源项目进行开发和改进
- **修改声明**: 对原始代码进行了稳定性优化、架构升级和功能增强，详见[系统架构设计文档](docs/System_Architecture_Design.md#142-项目来源声明)
- **分发要求**: 必须提供完整源代码并保留许可证和版权声明



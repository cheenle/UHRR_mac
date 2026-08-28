# iOS 前后台切换恢复实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [x]`）语法来跟踪进度。

**目标：** 修复 iPhone Chrome 反复切换前后台后 RX 声音、TX 和控制链路失效的问题。

**架构：** 为三个 WebSocket 增加实例所有权检查，并将恢复动作收敛到一个可去重的前台恢复流程。RX 只在音频上下文和数据流同时健康时复用，TX 支持不重建麦克风的 socket-only 重连，控制心跳与 PTT 轮询改为单例。

**技术栈：** 浏览器 JavaScript、Web Audio API、WebSocket、Node.js `vm`/`assert` 测试。

---

## 文件结构

- 修改 `www/controls.js`：连接实例隔离、音频上下文健康检查、统一恢复函数、单例控制定时器。
- 修改 `www/mobile_modern.js`：统一注册前后台、pageshow、online 和触摸恢复入口。
- 修改 `www/mobile_modern.html`：提升脚本查询版本，避免 iPhone 使用旧资源。
- 创建 `dev_tools/test_mobile_lifecycle.js`：可控浏览器替身回归测试。
- 创建 `docs/superpowers/specs/2026-08-28-ios-foreground-recovery-design.md`：设计与安全边界。

### 任务 1：锁定旧 socket 回调竞态

**文件：**
- 创建：`dev_tools/test_mobile_lifecycle.js`
- 修改：`www/controls.js:248-819`

- [x] **步骤 1：编写失败的测试**

测试构造旧 RX socket 和新 RX socket，触发旧 socket 的 `onclose` 后运行定时器，断言不会再次调用 `AudioRX_start()`，也不会关闭新 AudioContext。

```javascript
oldSocket.onclose();
clock.runAll();
assert.strictEqual(startCount, 0);
assert.strictEqual(newContext.closeCount, 0);
```

- [x] **步骤 2：运行测试验证失败**

运行：`node dev_tools/test_mobile_lifecycle.js`

预期：FAIL，旧 socket 的关闭回调安排了新一次 RX 重建。

- [x] **步骤 3：实现最少修复**

将创建时的 socket/context 捕获到局部变量，回调入口及异步 AudioWorklet 完成处检查：

```javascript
if (closedSocket !== wsAudioRX) return;
if (rxSocket !== wsAudioRX || rxContext !== AudioRX_context) return;
```

并把 `AudioRX_start()` 的完整健康判断移动到销毁 AudioContext 之前。

- [x] **步骤 4：运行测试验证通过**

运行：`node dev_tools/test_mobile_lifecycle.js`

预期：PASS。

### 任务 2：隔离控制和 TX 连接并收敛定时器

**文件：**
- 修改：`dev_tools/test_mobile_lifecycle.js`
- 修改：`www/controls.js:996-1300,2159-2253`

- [x] **步骤 1：编写失败的测试**

新增测试断言旧控制/TX socket 回调不改变当前连接，重复 `checklatency()` 只建立一个循环，控制连接只建立一个 PTT 查询 interval。

```javascript
checklatency();
checklatency();
assert.strictEqual(clock.pendingHeartbeatCount(), 1);
assert.strictEqual(clock.pttIntervalCount(), 1);
```

- [x] **步骤 2：运行测试验证失败**

运行：`node dev_tools/test_mobile_lifecycle.js`

预期：FAIL，当前实现可创建重复心跳或处理旧连接回调。

- [x] **步骤 3：实现最少修复**

事件处理器绑定 socket 实例；定时器执行前验证实例所有权。删除 `ControlTRX_start()` 中重复的 `pttQueryInterval`，仅保留连接成功后的 `pttStatusCheckInterval`。为心跳保存唯一 `_latencyTimer`，PONG 超时捕获发出 PING 的 socket。

新增只替换 TX WebSocket 的函数：

```javascript
function AudioTX_reconnectSocket() {
    var socket = new WebSocket(__wsURL('/WSaudioTX'));
    wsAudioTX = socket;
    if (ap) ap.wsh = socket;
    bindAudioTXSocket(socket);
}
```

- [x] **步骤 4：运行测试验证通过**

运行：`node dev_tools/test_mobile_lifecycle.js`

预期：PASS。

### 任务 3：实现去重的 iOS 前台恢复

**文件：**
- 修改：`dev_tools/test_mobile_lifecycle.js`
- 修改：`www/controls.js:620-720`
- 修改：`www/mobile_modern.js:780-810,1394-1450`

- [x] **步骤 1：编写失败的测试**

新增测试覆盖 `interrupted` 上下文恢复、closed RX 重建、TX socket-only 重连，以及两个并发恢复调用共享同一个 Promise。

```javascript
const first = resumeAudioAfterBackground('visibilitychange');
const second = resumeAudioAfterBackground('pageshow');
assert.strictEqual(first, second);
assert.strictEqual(rxContext.resumeCount, 1);
assert.strictEqual(txContext.resumeCount, 1);
```

- [x] **步骤 2：运行测试验证失败**

运行：`node dev_tools/test_mobile_lifecycle.js`

预期：FAIL，当前代码不恢复 `interrupted` 且不去重。

- [x] **步骤 3：实现最少恢复流程**

使用共享恢复 Promise，检测 RX/TX 上下文和麦克风轨道状态；控制 OPEN 时立即 PING，TX 在前后台或网络恢复后使用 socket-only 重连。移动端事件只调用统一调度入口，触摸入口恢复所有可恢复状态。

- [x] **步骤 4：运行测试验证通过**

运行：`node dev_tools/test_mobile_lifecycle.js`

预期：PASS。

### 任务 4：缓存版本和完整验证

**文件：**
- 修改：`www/mobile_modern.html:275-280`

- [x] **步骤 1：提升资源版本**

将 `controls.js` 和 `mobile_modern.js` 查询版本提升到同一新版本，确保 iPhone Chrome 请求新代码。

- [x] **步骤 2：运行语法和回归测试**

运行：

```bash
node --check www/controls.js
node --check www/mobile_modern.js
node dev_tools/test_mobile_lifecycle.js
node dev_tools/test_mobile_recording_status.js
python3 -m unittest dev_tools.test_recording_session -q
```

预期：全部退出码为 0。

- [x] **步骤 3：运行诊断**

对 `www/controls.js`、`www/mobile_modern.js` 和测试文件运行 LSP/项目诊断，确认无本次新增阻断错误。

- [x] **步骤 4：审查差异并仅暂存本次文件**

运行 `git diff --check` 和限定路径的 `git diff`。不得暂存设备配置、网站、Windows 打包或文件中与本任务无关的既存改动；对混有用户改动的文件使用补丁暂存。

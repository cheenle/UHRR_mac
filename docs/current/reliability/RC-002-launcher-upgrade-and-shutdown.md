# RC-002：启动器升级与退出链路上的五类 Windows 陷阱

> 状态：**已修复并验证**（V6.1.2 – V6.1.11，单元测试 101 项全绿 + 真机端到端实测通过）
> 发现方式：**Win11 VM 上的真机端到端验收**（`dev_tools/vm_upgrade_e2e.ps1`），不是代码审阅。
> 相关：`docs/current/operations/one-click-upgrade.md`（使用/排障）、`CHANGELOG.md` V6.1.2–V6.1.11。

## TL;DR

Windows 控制台进程 + 冻结的 PyInstaller 程序 + 提权安装器三者叠加时，有四类"看着完全正常、
实际静默失效"的失效模式：**进程关不掉、线程被解释器收尾打断、跨进程锁、编码差异**。
它们共同的特征是**没有任何用户可见报错**（哨兵被消费、日志不写、页面无变化），
只能靠"真机 + 分阶段证据链"发现。

---

## §1 主线程正常退出 = 升级被打断（Fatal Python error）

**现象**：`watch_upgrade` 已经开始处理升级（日志可见），随后进程直接死，安装器没起来。

**根因**：升级前必须停掉服务子进程（否则安装器替换文件失败，见 §3）。但停掉子进程会让
**主线程立刻从 `proc.wait()` 返回** → `main()` 正常返回 → CPython 开始解释器收尾 →
此时 `input()` 读线程（`wait_for_upgrade_key`）与日志转发线程还在用缓冲区 →
`Fatal Python error: _enter_buffered_busy: could not acquire lock for <_io.BufferedReader ...>`。

**修复**：
1. `_UPGRADING` 事件**必须在停服务之前**置位（晚了就来不及）；
2. 失败路径（异常 / `ShellExecuteW` 返回 ≤32）显式 `clear()`，保证主线程还能正常收尾；
3. `main()` 尾部：`_UPGRADING` 或 `_UPGRADE_BUSY` 置位时**永不正常退出**，
   由 `_exit_for_upgrade()` 里延迟 2 秒的 `os._exit(0)` 受控结束进程。

**回归测试**：`tests/test_launcher_tee.py::test_flag_set_before_stopping_server`
（断言源码中 `_UPGRADING.set()` 出现在 `_stop_server_for_upgrade()` **之前**）。

## §2 子进程先崩会把在飞的升级带死

**现象**：`upgrade.request` 被消费（文件消失），但升级没有任何动静，进程也已退出。

**根因**：服务子进程如果**自己**先退出（崩溃、被关掉），`proc.wait()` 同样立刻返回 →
主线程正常退出 → **处理到一半的 watch 线程被一起带走**。

**修复**：新增 `_UPGRADE_BUSY`：watch 一读到请求就置位；`main()` 尾部发现
"有升级在飞"就等待（上限 15 分钟），不再直接返回。

**回归测试**：`test_main_waits_for_inflight_upgrade_request`。

## §3 控制台进程关不掉 → 静默安装被 Abort

**现象**：Inno 日志 `Some applications could not be shut down.` →
`Defaulting to Abort for suppressed message box` → `User canceled the installation process.`

**根因**：`/CLOSEAPPLICATIONS` 靠 **Restart Manager** 发 `WM_CLOSE`；
控制台程序没有消息循环，收不到也处理不了 → 32 秒后超时 → `/SUPPRESSMSGBOXES`
对 Abort/Retry/Ignore 对话框自动选 **Abort**。

**修复**：
- 升级前启动器**先停自己的服务子进程**并等它退出；
- 安装命令补 `/FORCECLOSEAPPLICATIONS` 兜底；
- 启动器拉完安装器后 `os._exit` 让出自己被占用的文件（它也是被 RestartManager 点名的对象）。

## §4 跨进程抢同一个临时文件（`threading.Lock` 的边界）

**现象**：45 MB 下载到 43/45 MB 后报
`PermissionError [WinError 32] ... MRRC-Setup-6.1.9.exe.part -> ...exe`。

**根因**：现场存在**两个 `MRRC-Launcher` 实例**（重启脚本 + 安装器 `[Run]` 各拉起一个）。
`threading.Lock` **只在进程内有效**，两个进程各自下载同一个 `.part`；
一个下载完执行 `os.replace` 时，另一个正开着这个文件 → Windows 直接拒绝。

**修复**：临时文件按进程命名 `.part<pid>`；`os.replace` 加 6 次重试（杀软/索引器短暂占用
也能过去）；失败只清理**自己的**临时文件。

**回归测试**：`test_download_busy_does_not_block_forever`（锁被占返回 `busy` 而非阻塞）。

## §5 编码差异：BOM 让请求失效、GBK 杀线程

两个独立但同源的问题：

1. **BOM**：`json.load` 遇 UTF-8 BOM 直接抛错。记事本 / `Set-Content -Encoding utf8`
   （PowerShell 5.1）默认写 BOM → 手工写的 `upgrade.request` **静默失效**。
   → `_read_json` 改 `utf-8-sig`（有 BOM 也能读，没有也一样）。
2. **GBK**：Windows 控制台默认代码页 GBK，而服务端日志里有 emoji（🔍）。
   转发线程里的 `print(text)` 抛 `UnicodeEncodeError` → **线程死掉** →
   诊断包里的 `logs\server-stdout.log` **从此断更**（一个安静的功能损坏）。
   → 启动器 `_force_utf8_stdio()`：`sys.stdout/stderr.reconfigure(encoding="utf-8",
   errors="replace", line_buffering=True)` + `PYTHONIOENCODING=utf-8`；
   转发用 `_safe_print()`（编码失败降级为 ASCII，**绝不抛**）。

**行缓冲的额外教训**：升级收尾是 `os._exit`（不刷新缓冲区），没有 `line_buffering=True`
时用户**看不到任何升级进度**——"静默"变成了"没反馈"。

## §6 连接阶段没有超时 → 阻塞锁把升级线程拖死

**现象**（真机复现）：页面显示有新版本、服务端日志也有 `收到升级请求`，
但 `upgrade.request` 一直没人消费，`MRRC-Setup-6.1.9.exe.part` 停在 **0 字节**。

**根因**：启动时的后台预下载线程卡在 **连接/DNS 阶段**——`urllib` 的 `timeout` 覆盖
socket 读写，**不覆盖 DNS 解析**。该线程长期持有 `_DOWNLOAD_LOCK`（当时是阻塞锁）→
升级看护线程拿到第一个请求后在锁上**无限等待** → 后续请求全部无人处理。

**修复**：
- 锁改 `acquire(timeout=1.0)`，拿不到立即返回 `{"ok": False, "reason": "download_busy…"}`
  → 上层 `watch_upgrade` 保留请求、稍后重试（**失败不丢指令**）；
- 模块级 `socket.setdefaulttimeout(30)`。

**证据（修复前后同一台机器）**：

| 观察 | 修复前 | 修复后 |
|---|---|---|
| `.part` 字节数 | 永远 **0** | 0→1→2→…→44 MB 持续增长 |
| `upgrade.request` | 躺着无人消费 | 被消费；失败自动重试 |
| 最终结果 | 无 | `lastResult: ok / 6.1.9 / 安装后启动确认成功` |

## §7 方法教训（写给未来的自己）

1. **"静默"是这个链条上最危险的属性**：四类问题都没有用户可见报错。
   凡是没有"成功确认"环节的设计（谁证明升级成功？），必然要花几倍时间排查 →
   本次的解法是**由新版自己确认**（`confirm_pending_upgrade`）。
2. **真机验收不可替代**：这 10 个问题里没有一个是代码审阅能发现的；
   而"分阶段证据链"（哨兵是否被消费 / `.part` 是否增长 / 是否有 install 日志 /
   `state.json` 的 `lastResult`）比"再读一遍代码"快一个数量级。
3. **测试脚手架本身也会成为阻塞**：SSH 会话结束会回收 `Start-Process` 拉起的子进程
   → 必须用**计划任务**（`/IT /RL HIGHEST`）才能得到"用户会话 + 提权"的真实环境；
   PowerShell 5.1 含中文脚本必须 **UTF-8 with BOM**，`Tee-Object` 没有 `-Encoding`。
4. **锁的作用域要被写清楚**：`threading.Lock` 是**进程内**的；涉及多实例的共享文件
   （`.part`）必须用"按进程命名"或文件锁，而不是线程锁。
5. **凡是阻塞等待都要有超时**，包括"拿锁"和"发网络请求"这两件最容易忘记的事。

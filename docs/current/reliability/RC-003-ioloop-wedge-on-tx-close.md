# RC-003：IOLoop 楔死 2h23m —— TX 拆流（Pa_StopStream）阻塞在事件循环线程上

> **元信息**
>
> - 日期：2026-10-04（13:49:32 冻结，16:06 发现）
> - 影响版本：V6.1.18 及之前（F6 修复后合入下一版本）
> - 影响实例：`radio1`（IC-M710，HTTPS/WSS 端口 8891，macOS 主机，PID 99049）
> - 严重级别：可用性（高）+ 发射安全（中低：释放路径被排在阻塞调用之后，见 §5）
> - 修复标记：**F6 系列**（F6 `close()` 有界化 + `close_async()`；F6b s:/on_close 异步释放 PTT；
>   F6c 原生线程栈转储看门狗）+ **F7**（陈旧 frpc 清理补齐 POSIX，调查期间顺带发现）
> - 关联文档：`RC-001-ioloop-wedge-and-tx-silence.md`（同族前案）、`AGENTS.md`「PTT Safety」「IOLoop thread-safety」

---

## 1. 现象与时间线

**现象**：网页/WebSocket（8891）完全无响应——curl 连得上、8s 无任何字节；但进程活着，
CPU 正常，音频采集 100% 健康、Opus 编码正常、天调代理照常收发。

### 1.1 关键时间线（2026-10-04，日志精确对齐）

| 时间 | 事件 |
| ------ | ------ |
| 08:36 | 实例启动（PID 99049），运行正常约 5 小时 |
| 13:49:28 | `setPTT:true` → TX 流打开成功（`p.open 0.07s`），14260 kHz 发射 115W |
| 13:49:32 | 用户松 PTT：控制通道 `setPTT:false` → **PTT 已释放**（ATR 13:49:33 起 0W） |
| 13:49:32 | 同一时刻音频通道收到 `s:` → `🛑 立即停止音频播放并关闭PTT` → **卡死在这一行之后** |
| 13:49:33+ | 天调代理仍停在 TX 数据流模式（stop 请求经 MRRC 的 WS 中继转发，而中继已死）→ 每 20s 一次 `⚠️ TX 模式 20秒无数据，发送一次 SYNC 尝试唤醒` |
| 13:54:32 | 空闲关机线程（独立线程）`setPower(0)`：`Power status tracked as 0` —— 这是冻结后日志里**唯一**的非音频输出 |
| 16:06 | 发现：8891 假死 2h23m；`py-spy dump` 抓到 MainThread 栈 |

### 1.2 现场证据

```
Thread 0x1F90C7080 (active): "MainThread"          ← Tornado IOLoop，自 13:49:32 卡住
    stop_stream (pyaudio/__init__.py:500)           ← pa.stop_stream()，C 调用不返回
    close (audio_interface.py:1445)                 ← PyAudioPlayback.close()
    on_message (MRRC:1136)                          ← WS_AudioTXHandler 's:' 分支
```

| 手段 | 结果 |
| ------ | ------ |
| `curl -sk https://127.0.0.1:8891/` | 8s 超时（TCP 能连上，无响应） |
| `netstat -an \| grep 8891` | 多条 `CLOSE_WAIT`，接收队列滞留 ~1.5KB 请求数据 —— 请求进来了但没人处理 |
| `lsof -p 99049` | 监听正常、残留若干 `CLOSED` 连接（泄漏的 fd） |
| 音频线程 / rigctld / 天调 Unix Socket | **全部正常** —— 只有 IOLoop 死 |
| 日志 | 13:49:32 之后再无任何 HTTP/WS 处理；音频健康行每 30s 一条连续到发现时刻 |

**为什么一次都没看到看门狗 dump**：`arm_ioloop_watchdog` 的心跳自身跑在 IOLoop 上——
事件循环**永久**楔死时它永远排不上队，第 1 层检测形同虚设（AGENTS.md 原描述
"wedge 时会 dump 全部线程栈"只对"卡顿后恢复"成立）。这是 F6c 的直接动因。

---

## 2. 根因分析（端到端因果链）

### 2.1 直接原因：阻塞 C 调用跑在 IOLoop 线程上，且无超时

```
用户松 PTT（浏览器同时发控制通道 setPTT:false 与音频通道 s:）
  → WS_AudioTXHandler.on_message('s:')（IOLoop 线程）
  → PyAudioPlayback.close()
  → Pa_StopStream()（PortAudio C 调用）不返回
  → Tornado IOLoop 单线程事件循环被独占
  → 8891 端口假死：HTTP / WebSocket / 控制通道 / 天调中继全部失能
      （音频采集、rigctld、天调代理都在各自的线程/进程里，照常运行）
```

### 2.2 同一族的第三处遗漏

| 修复 | 内容 | 位置 |
| ------ | ------ | ------ |
| F2 | `stream.write()` 挪到专用 writer 线程 | `audio_interface.py` `PyAudioPlayback` |
| F3 | rigctld 阻塞 IO 挪出 IOLoop（控制通道的 setPTT/getFreq/…） | `MRRC` `WS_ControlTRX` |
| F4/F4b | TX 初始化 + `p.open()` 挪到执行器；帧缓存补放 | `MRRC` `_start_tx_init_async` |
| **F6（本次）** | **`close()`（含 `Pa_StopStream`/`Pa_CloseStream`/`Pa_Terminate`）有界化；** | `audio_interface.py` `PyAudioPlayback` |
| | **s:/on_close 调用点改 `close_async()`；释放 PTT 走执行器** | `MRRC` `WS_AudioTXHandler` |
| | **原生线程栈转储看门狗（永久楔死也能留现场）** | `MRRC` `arm_ioloop_watchdog` |

RC-001 §6 教训 1 早已写明："应按『枚举所有在 IOLoop 线程上的阻塞点』排查"——
F2/F4 修完之后，`close()` 这条路径没有被同一次枚举覆盖到。

### 2.3 为什么 `Pa_StopStream` 不返回（环境层，未完全定论）

可证的只有"阻塞在 C 调用中"：

- PyAudio 的 `stop_stream()` 是 `pa.stop_stream()` 的薄封装（`pyaudio/__init__.py:500`），
  没有超时参数；
- 已知交互风险：F2 引入的 writer 线程若仍停在阻塞 `write()` 里，此时从另一个线程
  `stop_stream()` 同一 stream 属 PortAudio 不支持的跨线程操作（本修复已规避）；
- 设备/HAL 侧（USB 声卡热插拔、CoreAudio 状态异常）同样可能让 stop 挂起——与 RC-001
  的"环境毒害音频子系统"是同一类嫌疑，本次现场没有可用证据进一步区分（进程被卡在
  C 调用里，唯一线索就是那一个栈帧）。

**结论**：根因不是"为什么这台机器上 stop 卡住了"，而是"一个可能永不返回的调用被放在
了事件循环线程上、没有超时、后面还排着安全动作"。F6 按此修复，使环境层再出问题也不会
再变成服务级故障。

---

## 3. 修复措施

### 3.1 F6：`PyAudioPlayback.close()` 有界返回（`audio_interface.py`）

- `stop_stream()/close()/terminate()` 全部放进**一次性线程**，`done.wait(timeout=3s)`
  超时即放弃（泄漏该流），调用者**绝不被阻塞**；
- 写线程 1s 内未退出（卡在阻塞 `write()`）→ 交给看护线程等它退出后再拆流，**不**从
  别的线程碰同一 stream（规避 §2.3 的跨线程竞态）；
- 新增 `close_async()`：IOLoop 调用点专用，立即返回；
- `close()` 幂等（`_closed`）。

### 3.2 F6b：s:/on_close 释放路径去阻塞（`MRRC`）

- 两处 `self.audio_playback.close()` → `close_async()`；
- 两处 `CTRX.setPTT("false")` → `MAIN_IOLOOP.run_in_executor(None, _release_ptt_async)`
  （setPTT 自带 3×3s rigctld 阻塞 IO；F3 只修了控制通道，音频/连接关闭路径漏了）；
- 删除 s: 分支手写的"乐观"`getPTT:false` 广播 —— 状态改由 setPTT 确认后自行广播
  （R3 安全约束：释放方向绝不乐观预设，失败要能翻回 true 并发 `pttError`）。

### 3.3 F6c：看门狗加原生转储（`MRRC`）

- 心跳每拍重臂 `faulthandler.dump_traceback_later(30s, repeat=True)`（独立 C 线程，
  不依赖 IOLoop）；心跳健康时每 2s 重置、永不触发，**心跳一停摆即倾倒全部线程栈**；
- 保留原有"卡顿结束时的迟到检测"转储（覆盖瞬时卡顿）。

### 3.4 F7：陈旧 frpc 清理补齐 POSIX（`cloud_hub.py`，调查期间顺带发现）

同一晚排查"隧道还活着吗"时发现：本机有 **5 个 frpc** 抢同一个 proxy 名
（99050/21607/23064/23256/25305，分别来自 08:36 起每次启动），日志每 10s 一条
`proxy already exists`，而隧道实际由**早已失去父进程的孤儿** frpc 持有。根因：
`_kill_stale_frpc()` 第一行是 `if os.name != "nt": return` —— 只写了 wmic/taskkill，
POSIX 平台直接跳过（而该函数的 docstring 早就描述了这个后果）。

- 拆出 `_stale_frpc_pids(config_path, ps_output=None)`：平台无关地列出"命令行点名了**本实例
  自己**配置文件"的 frpc 进程（POSIX `ps -eo pid=,command=`，Windows wmic；`ps_output`
  是测试注入缝）；
- `_kill_stale_frpc()`：POSIX 走 SIGTERM → 宽限 3s（按 `ps -o state=` 判活，不把
  zombie 当活）→ SIGKILL；只杀点名本实例配置的进程，同机另一实例的 frpc 不受影响；
- 清理动作对运维可见（`print`，本产品 logger 级别是 WARNING，info 不进日志）；
- 守卫：`dev_tools/test_cloud_hub.py` 新增用例（只选中本实例 / 不误杀另一实例 / 空输出 /
  不再在 POSIX 一行 return）。

实测：重启后 frpc 从 5 个降到 1 个，frpc 日志转为 `start proxy success`，
`already exists` 停止出现。

### 3.5 F8：证书 SAN 支持老直连入口（`ssl_bootstrap.py` + `cloud_hub.py` + `MRRC`）

同一晚还查清了那个持续刷屏的 `SSL CERTIFICATE_UNKNOWN`：`radio.vlsc.net` 的 AAAA
解析到**本机自己的 IPv6**（老书签直连），而实例从 08:36 起服务的 Cloud Hub 证书 CN 是
`bg6lh-legacy.mrrc.vlsc.net` —— 域名不匹配，Chrome 直接拒绝（日志约每 0.5s 一条）。

- `ssl_bootstrap.sign_for(..., extra_names=...)`：SAN = 入口名 + extra（去重/去空白）；
  不传 extra 行为与从前完全一致；
- `cloud_hub.connect(..., extra_names=...)` 透传；`MRRC` 从 `[SERVER] cert_extra_names`
  读取（逗号分隔）—— 这三个名字名下的其它实例默认不受影响；
- 守卫：`tests/test_ssl_bootstrap.py`（SAN/CN/去重/0600）+ `dev_tools/test_cloud_hub.py`
  的透传断言。

**关键教训（实测踩到并已跑通）**：hub 侧把实例证书按 label 存下来做**上游校验**
（`/enroll` 写入 `/etc/mrrc-hub/instance-certs/<label>.pem`），而公网看到的入口证书是
边缘的 Let's Encrypt（与实例证书无关）。"上游校验"的具体机制：hub 的 nginx
`proxy_ssl_verify on` + `proxy_ssl_name $mrrc_tls_name` + `proxy_ssl_trusted_certificate
/etc/mrrc-hub/trust-bundle.pem`，而 `gen_hub_routes.py` 把信任包重建为"系统 CA + 每个
**仍在注册表里**的实例证书"——所以**只重签站端证书 → hub 入口立刻 502**（本次第一次
尝试实测 502，回滚后立即恢复 302）。

**完整换证书流程（本次已按此完成）**：

1. 站端：同私钥重签（SAN = 入口名 + `[SERVER] cert_extra_names`）并向 hub `/enroll`
   重新登记（用 portal 给的 `enroll_secret`）——这一步不影响在跑的服务（旧证书仍在服务）；
2. hub：`sudo /usr/local/sbin/gen_hub_routes.py && sudo nginx -t && sudo systemctl reload nginx`；
3. 站端重启，加载新证书（TLS 上下文只在启动时建立）。

把第 2 步插进第 3 步的重启窗口，对外中断就只剩“一次站端重启”的量级。
验证判据：hub 入口 302 + `openssl s_client -servername radio.vlsc.net` 的 SAN 含两个名字
- hub 的 trust-bundle 里能找到新证书指纹。本次（`bg6lh-legacy`）三项全部通过。

---

## 4. 验证方法

### 4.1 判定手段（都可复用）

| 手段 | 用法 |
| ------ | ------ |
| `sudo py-spy dump --pid <pid>` | 不重启、不改代码，直接看每个线程停在哪个 Python 帧（本案一眼定位） |
| `curl` + `netstat` | "TCP 连得上但无响应" + `CLOSE_WAIT` 且接收队列有数据 = 事件循环停摆的签名 |
| 线程对照 | 音频/rigctld/天调线程全部健康 → 排除设备/进程级故障，锁定 IOLoop |
| `.prev` 日志 | 重启前先 `cp` 一份死亡现场（`mrrc_multi.sh` 启动时也会轮转） |
| 守卫测试 | `python3 dev_tools/test_audio_close_liveness.py`（假 stream 永久阻塞 `stop_stream`，钉住 close 有界/幂等/写线程竞态/调用点无裸调） |

### 4.2 复测数据

- 守卫测试在修复前 **8 项不合格**（含真实复现：`close()` >10s 不返回），修复后
  全部通过；阻塞场景 3.01s 内返回并打印 `⚠️ TX stream stop/close 超过 3s 未返回…`；
- `tests/` 全部 15 个用例、`dev_tools/test_ptt_liveness.py`、`dev_tools/test_cloud_hub.py`
  全绿；
- 修复后实例启动日志出现 `IOLoop watchdog armed (… native dump window=30s)`。

### 4.3 下次楔死的预期现场

即使 IOLoop 再次被永久阻塞，日志里应出现（无需人工 py-spy）：

```
Timeout (0:00:30)!
Thread 0x... (most recent call first):
  File "...", line ..., in <阻塞点>
  ...
```

---

## 5. 安全影响分析

| 风险 | 严重度 | 处置 |
| ------ | -------- | ------ |
| 端口假死 2h23m，无法操作电台 | 高（可用性） | F6/F6b 根治（TX 拆流不再碰 IOLoop） |
| **释放 PTT 排在阻塞调用之后**：s: 分支的 `CTRX.setPTT("false")` 在 `close()` 之后，close 卡住 → 该行永不执行 | 中（安全） | F6b 异步化；本案未酿成事故纯属运气（控制通道先到并独立释放了 PTT） |
| PTT 滞留发射 | 未发生 | 控制通道 13:49:32 释放成功（ATR 0W）；兜底链 TOT(120s) → 空闲关机(300s) 未被动用 |
| 天调 TX 流状态滞留（代理每 20s SYNC 刷日志） | 低 | MRRC 重启即恢复；stop 请求的中继属于 IOLoop，同因失能 |

**既有安全设计在本案中的表现**：三层 PTT 安全（活性闸门 / TOT 硬上限 / 释放重试）都依赖
"MRRC 主进程能调度自己的线程"——本案恰好没伤到它们（被楔死的是 IOLoop 线程，不是整个
进程）。但**端口的可用性本身就是安全能力**：假死期间无法收 PTT、无法改频、无法人工干预。

---

## 6. 经验教训（模式沉淀）

1. **"阻塞点枚举"必须按调用图走完，而不是按事故清单打补丁**。F2/F3/F4 每次只修一个
   被咬到的地方，`close()` 一直躺在 IOLoop 上。正确姿势：列出所有在 IOLoop 线程可达的
   阻塞调用（音频、串口、网络、子进程），逐个加"执行器 + 超时"。
2. **看门狗不能和被监视的对象跑在同一个线程上**。心跳自检测只能发现"卡过又恢复"；
   永久楔死要靠独立线程（`faulthandler.dump_traceback_later` 是 C 线程）或外部探针。
3. **"永不返回"的调用比"慢"的调用危险一个量级**。慢会自己被日志和超时暴露；不返回
   只会安静地杀死整条事件循环。任何封装了 C 库/阻塞 IO 的调用都应有有界等待兜底。
4. **安全动作不能排在可能阻塞的清理动作后面**。松 PTT 的语义是"立即放行"，任何
   "先把音频收拾干净再说"的排序都可能在清理卡住时变成"永不放行"。
5. **不可捕获信号是停止流程的盲区**。卡在 C 调用里的 Python 进程收 SIGTERM 后不会执行
   信号处理器（`mrrc_multi.sh restart` 因此要等 `kill -9` 兜底）——重启脚本的
   优雅停止不能假设进程总能响应。
6. **泄漏一个流好过死一个服务**。资源清理遇到"清理动作本身可能挂"时，宁可放弃资源、
   记录告警、让进程继续服务。

---

## 7. 排查工具箱（速查）

```bash
# 1. 端口假死还是进程死了？
curl -sk --max-time 8 -o /dev/null -w "%{http_code} %{time_total}\n" https://127.0.0.1:8891/
ps -o pid,stat,%cpu,etime -p $(pgrep -f "MRRC\.radio1\.conf")

# 2. 事件循环停摆签名（TCP 连得上 + CLOSE_WAIT 有滞留数据）
netstat -an | grep 8891 | head

# 3. 卡在哪一行（先存档，别急着重启）
sudo py-spy dump --pid $(pgrep -f "MRRC\.radio1\.conf") | head -30

# 4. 保留现场日志（重启会轮转成 .prev）
cp mrrc_radio1.log /tmp/mrrc_radio1.frozen.log

# 5. 永久楔死的自动现场（F6c 起，无需人工）
grep -n "Timeout (0:00:30)!" mrrc_radio1.log

# 6. TX 拆流告警（F6 起）
grep -n "TX stream stop/close 超过\|TX 写线程未在" mrrc_radio1.log

# 7. 本次事故判定链（对照日志）
grep -n "🛑\|🧹\|PTT释放已异步下发\|Power status tracked" mrrc_radio1.log
grep -n "TX模式开始\|TX模式结束\|20秒无数据" atr1000_radio1.log
```

---

## 8. 后续监控与决策触发线

- 启动日志应包含 `native dump window=30s`（F6c 生效判据）；
- 出现 `⚠️ TX stream stop/close 超过 3s 未返回` → 设备/HAL 层正在劣化，按 RC-001 §7
  查蓝牙/CoreAudio，并考虑在面板上加"音频设备异常"提示；
- 出现 `Timeout (0:00:30)!` + 线程栈 → 新的 IOLoop 阻塞点已经暴露，按栈修复并追加
  F 标记，不必再靠人工 py-spy；
- 若同类"清理动作卡死"再出现第三次 → 把"清理动作必须可中断/可超时"提取为独立最佳实践文档
  （可靠性索引 §横向主题 的既定规则）。

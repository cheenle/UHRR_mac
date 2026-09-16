# 一键升级（Windows 安装版）

> 上下游：本文是《[产品支持生命周期](product-support-lifecycle.md)》的**第 2 步（版本升级）**实施细则；
> 上游 [发版流程](release-process.md)，下游 [诊断包](support-bundle.md)。

> 实现版本：**V6.1.0 起进包**；V6.1.2–V6.1.11 修复了 10 个在真机端到端验收中暴露的坑
> （见下面"排障"表与 `docs/current/reliability/RC-002-launcher-upgrade-and-shutdown.md`）。
> **V6.0.10 及更早没有升级逻辑**：那些用户需要手动装一次 6.1.x，之后才能一键升。

用户侧：移动端菜单 **⬆️ 软件更新** / 桌面工具栏 **⬆️** → 看到"有新版本"→ 点【立即升级】；
或直接在启动器窗口**输入 U 回车**。会弹**一次 UAC**（管理员确认），装完自动重启服务。

---

## 1. 开关

| 配置 | 作用 |
|---|---|
| `[UPDATE] enabled = False` | 完全不检查（含热修） |
| `[UPDATE] autoDownload = False` | 只提示有新版，不后台预下载 |
| `MRRC_NO_UPDATE_CHECK=1` | 环境变量，覆盖一切（调试/离线可用） |
| `MRRC_UPDATE_MANIFEST=<url>` | 覆盖清单地址（内网镜像 / 测试用，不动生产清单） |

---

## 2. 实际运行机制（排障必读）

### 2.1 启动器启动时（`windows/launcher.py`）

1. `check_for_hotfix()` → 拉 `patch.json`，热修覆盖层落到 `%LOCALAPPDATA%\MRRC\patch\`
   （**先于**升级检查，所以"热修修 `upgrade_core`"能立刻生效，无需重装）；
2. `confirm_pending_upgrade()` → 若 `version.txt >= state.staged.version`：
   记 `lastResult = ok` + 删掉暂存安装包 + 清 `staged`（**升级成功由新版自己确认**，
   因为升级时老启动器已经主动退出，没人能替它确认）；
3. `check_for_upgrade()` → 拉 `latest.json`（读不到回退 `patch.json` 的旧行为）
   → `plan_upgrade()` 决策（拒绝降级 / `minSupported` 门禁 / `mandatory`）
   → 有新版本则**只提示 + 后台预下载**（绝不打断收听）。

### 2.2 用户点【立即升级】/ 按 U

4. 服务端 `UpdateApiHandler`（本机免口令；非本机需登录）先做 **PTT 门禁**，
   发射中返回 **423**；通过则写哨兵 `updates\upgrade.request`（值是**具体版本号**；按 U 写 `latest`）；
5. 启动器 `watch_upgrade` 线程（1 秒轮询）接手，统一两条路径：

```
读哨兵（消费后立即删除，避免重复触发）
  └─ 已暂存且版本/sha 匹配？ ──是─→ 直接用（离线也能升）
                             └─否─→ 拉清单 → 需要就下载（见 2.3）→ 校验 SHA256 → 原子改名
  └─ PTT 门禁（问本机 /api/update，服务端不可达视为安全）
  └─ run_upgrade()
       ① _UPGRADING.set()            ← 必须在停服务之前！见 RC-002 §1
       ② 停掉自己拉起的服务子进程     ← 否则 Inno 的 RestartManager 关不掉控制台进程，静默 Abort
       ③ 已提权→直接 Popen 安装器；未提权→ShellExecuteW "runas"（弹一次 UAC）
          参数固定：/VERYSILENT /SUPPRESSMSGBOXES /NORESTART
                    /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /LOG=…
       ④ 返回 installing → watch 调 _exit_for_upgrade()：延 2 秒 os._exit(0)
          （必须让出被占用的 exe/dll，且不能走正常退出——见 RC-002 §1）
6. 安装器 `[Run]` 段的**静默启动项**（`Check: WizardSilent`）拉起新版 MRRC；
7. 新版启动 → 回到第 2 步 `confirm_pending_upgrade()` → 记 **`ok`**。

### 2.3 下载（`upgrade_core.download_installer`）

- `.part<pid>` 临时文件（**按进程区分**，多启动器实例互不干扰）→ SHA256 校验 → `os.replace`（**6 次重试**）；
- 进程内 `_DOWNLOAD_LOCK` 用 **`acquire(timeout=1.0)`**：拿不到立刻返回 `download_busy`
  让上层重试（**绝不能阻塞**——否则后台预下载卡死会连带把升级看护线程拖死，见 RC-002 §2）；
- 模块级 `socket.setdefaulttimeout(30)`：**连接/DNS 阶段也有超时**；
- 失败只删自己的 `.part`，并记 `lastResult = download_failed` + 原因（**绝不动现有安装**）。

### 2.4 状态文件（都在 `%LOCALAPPDATA%\MRRC\updates\`）

| 文件 | 内容 |
|---|---|
| `state.json` | `staged{version,sha256,path,size,at}` 与 `lastResult{status,version,detail,at}` |
| `upgrade.request` | 升级请求（启动器消费后立即删除） |
| `MRRC-Setup-<ver>.exe` | 已校验的暂存安装包 |
| `install-<ver>.log` | Inno Setup 日志（**失败时第一个看它**） |

`lastResult.status` 取值：

| status | 含义 |
|---|---|
| `ok` | 安装后启动确认成功（唯一成功态） |
| `installing` | 已启动静默安装（老启动器即将退出，成败由新版确认） |
| `uac_denied` | 用户拒绝了 UAC（`ShellExecuteW` 返回 5） |
| `ptt_active` | 发射中被拒（页面路径 423） |
| `sha_mismatch` | 安装包校验失败（已丢弃，未安装） |
| `download_failed` | 下载失败（含 `download_busy` / 超时 / 权限）；失败后**自动重试** |
| `missing_staged` | 安装包还没下完就触发（会重试，不丢请求） |
| `install_failed` | 安装器失败或安装后 `version.txt` 未更新 |

---

## 3. 排障：真机验收抓到过的 10 个坑（症状 → 根因 → 修复）

> 全部由 Win11 VM 上的真机端到端验收抓出（`dev_tools/vm_upgrade_e2e.ps1`）；
> 编号对应 `CHANGELOG.md` 的 V6.1.2–V6.1.11。

| # | 症状 | 根因 | 修复 |
|---|---|---|---|
| 1 | 安装器日志 `User canceled the installation process`、回滚 | Inno `/CLOSEAPPLICATIONS` 靠 RestartManager 发 `WM_CLOSE`，**控制台进程没有消息循环**关不掉 → `/SUPPRESSMSGBOXES` 自动选 Abort | 升级前**先停自己的服务子进程** + 命令加 `/FORCECLOSEAPPLICATIONS` |
| 2 | 已提权时哨兵被消费、无 UAC、无日志，永久卡住 | 已提权进程再走 `ShellExecuteW("runas")` 在非交互窗口站上会**卡死** | `_is_elevated()` 为真时**直接 `subprocess.Popen`** |
| 3 | 升级成功但没人确认（`lastResult` 一直空） | 老启动器升级时主动退出，没人能确认 | 新版启动时 `confirm_pending_upgrade()` 自证 `ok` |
| 4 | 记事本/PowerShell 写的 `upgrade.request` 被忽略 | `json.load` **遇 BOM 抛错** → 请求静默失效 | `_read_json` 用 `utf-8-sig` |
| 5 | 诊断包里 `server-stdout.log` 断更 | Windows 控制台是 **GBK**，服务端日志里的 emoji（🔍）让 `print` 抛 `UnicodeEncodeError`，**杀死转发线程** | 启动器 stdio 统一切 UTF-8 + `_safe_print` 降级不抛 |
| 6 | 静默升级装完 MRRC 不回来 | `[Run]` 只有 `postinstall skipifsilent` | 补一条 `Check: WizardSilent` 的启动项（`runasoriginaluser`） |
| 7 | `Fatal Python error: _enter_buffered_busy`，安装被打断 | 停服务让主线程从 `proc.wait()` 醒来 → 标志检查晚一步 → 走正常退出 → 解释器收尾与 `input()`/转发线程抢缓冲 | `_UPGRADING.set()` **早于**停服务；失败路径 `clear()` |
| 8 | 哨兵被消费但升级静默丢失（服务恰好自己先崩） | `proc.wait()` 立刻返回 → 进程退出把处理到一半的 watch 线程**带死** | `_UPGRADE_BUSY`：watch 一接到请求就置位，`main()` 有升级在飞则等待 |
| 9 | `.part` 停在 **0 字节**，点按钮毫无反应 | 后台预下载卡在**连接/DNS**（读超时覆盖不到）→ 长期占着**阻塞锁** → 升级线程无限等锁 | 锁改 `acquire(timeout=1.0)`（不阻塞）+ `socket.setdefaulttimeout(30)` |
| 10 | 下到 43/45 MB 后 `PermissionError [WinError 32]` | `threading.Lock` **只在进程内有效**，而现场有**两个启动器实例** → 两个都下同一个 `.part` → 一个改名时另一个正开着它 | `.part<pid>` 按进程命名 + `os.replace` 重试 + 只清自己的临时文件 |

另外两个打包/日志类修复：

- **`upgrade_core` 漏出包**（MRRC 是 datas 里的数据文件、函数内 import 分析不到）→
  服务端 `/api/update` 报 `ModuleNotFoundError` → 加入 spec 的 `_APP_MODULES`；
- **启动器日志丢行**：`_force_utf8_stdio` 没开行缓冲，而升级收尾是 `os._exit`（不刷缓冲）
  → 用户在窗口里看不到任何进度 → 改 `line_buffering=True`。

### 常见问答

**为什么一定要弹一次 UAC？** 安装包写 `Program Files` + HKLM 卸载键，必须提权。
提权的一次点击是**人为闸门**；除此之外全自动。

**点了没反应怎么办？** 先看启动器窗口有没有 `[update]` 行，再看
`updates\state.json` 的 `lastResult`：
- `download_failed/download_busy` → 网络抖动，**等它自动重试**或再点一次；
- `missing_staged` → 安装包还没下完，**等一下再点**（会自动继续）；
- `ptt_active` → 松开 PTT 再点。

**升级失败会不会把 MRRC 弄坏？** 不会：失败只删临时文件；下一次启动会打印
`[update] 上次升级 X 似乎没完成（当前 Y），可重试`；实在不行用页面【回退到上一版】。

**怎么拿到日志？** 启动器窗口内容 + 页面 **🐞 遇到问题 → 生成并上传**（会带
`state.json`、`install-<ver>.log`、`logs\server-stdout.log`、脱敏配置）。

---

## 4. 回退到上一版

`latest.json` 的 `previous` 段指向站点上保留的旧安装包；页面【回退到上一版】写同样的哨兵，
走同一条静默安装路径（同样一次 UAC）。

⚠️ 发布时**两个包都必须入库**（`MRRC-Setup-<最新>.exe` 与 `MRRC-Setup-<上一版>.exe`）：
站点部署是 `rsync --delete`，**没进 git 的服务器文件会被清掉**，回退按钮就会 404。

---

## 5. 安全与信任边界（诚实记录）

- 只走 **HTTPS + 清单内 SHA256** 固定校验；**无代码签名**（需证书，列为后续硬化项）
  → 信任锚 = 站点 TLS；
- 安装时的 **UAC 是最后一道人工闸门**；静默安装参数固定，**不接受网络下发参数**；
- `latest.json` 与 `patch.json` 的失败一律"忽略并继续用旧版"，绝不阻断启动。

---

## 6. 真机验收记录（V6.1.8 → V6.1.9，Win11 VM）

```
version.txt = 6.1.9
state.json : {"staged": null,
              "lastResult": {"status": "ok", "version": "6.1.9",
                             "detail": "安装后启动确认成功"}}
install-6.1.9.log:
  -- Run entry -- Run as: Original user
  Filename: C:\Program Files\MRRC\MRRC-Launcher.exe
  Attempting to restart applications.
  Need to restart Windows? No
  Deinitializing Setup.
```

六个环节全部走通：**点按钮 → 写请求 → 自动下载+SHA256 → 提权静默安装 → 自动重启 → 新版自证 `ok`**。

可复现脚本：`dev_tools/vm_upgrade_e2e.ps1`（参数化基线/目标版本；含 `MRRC_UPDATE_MANIFEST`
指向 `file://` 本地清单，可完全离线验证，不受站点网络影响）。

---

## 7. 发布清单（维护者）

见 `docs/current/operations/release-process.md`（一条命令 + 关键约束 + 线上复核）。
一句话版：
`./dev_tools/release_windows.sh`——构建 → 产物上热修验收 → 取回 → 归档上一版 →
生成 `latest.json` → 部署 → **线上 SHA256 复核**。

# 一键升级到最新版设计（Windows 安装版）

> 状态：已获用户批准（2026-09-16）。用户选择方案 **B：一键升级**——
> 点一下 → 下载 → 校验 → 静默安装 → 自动重启（接受一次 UAC）。
> 已定：保持 `Program Files` 安装（不迁移）+ 只保留**上一版**用于回滚。

## 1. 目标与非目标

**目标**

- 联网时，用户点一次（或按一个键）就能升到最新版，不必自己找下载链接；
- 升级包默认**后台自动下载并校验**，用户只需决定"什么时候装"；
- 能热修的先热修（几十 KB，无感）；只有安装包级变化才走完整升级；
- 失败不破坏现有安装；提供一键回退到上一版。

**非目标**

- 不做增量差分升级（45 MB 全量足够，YAGNI）；
- 不做自动回滚（避免版本震荡）；
- 不做代码签名（需证书；列入后续硬化项）；
- 不改安装位置/权限模型（保持 `Program Files` + 一次 UAC）。

## 2. 版本语义（唯一权威）

- 安装版本 = `packaging/windows/MRRC.iss` 的 `MyAppVersion`，构建时写入安装目录 `version.txt`；
- 热补丁**不改**安装版本：用 `requires`（最低安装版本）+ `patch/applied.json`（已应用版本）判重；
- 比较规则：`latest > installed` 才提示升级；`installed < minSupported` 时禁用热修、必须走完整包；
- **拒绝降级**：`latest ≤ installed` 一律不动作。

## 3. 清单 `latest.json`（站点根 `downloads/`）

```json
{
  "latest": "6.0.9",
  "installer": { "url": "https://www.vlsc.net/mrrc/downloads/MRRC-Setup-6.0.9.exe",
                 "sha256": "…", "size": 45344400 },
  "hotfix":    { "url": "https://www.vlsc.net/mrrc/downloads/hotfix-6.0.9.zip",
                 "sha256": "…", "requires": "6.0.3", "notes": "…" },
  "previous":  { "version": "6.0.7",
                 "url": "https://www.vlsc.net/mrrc/downloads/MRRC-Setup-6.0.7.exe",
                 "sha256": "…" },
  "mandatory": false,
  "minSupported": "6.0.3",
  "releasedAt": "2026-09-16T15:00:00+08:00",
  "notes": "面向用户的一句话更新说明"
}
```

- `installer` 缺失 → 只做热修；`hotfix` 缺失 → 只提示升级安装包；
- 读不到 `latest.json`（404/超时）→ 回退读现有 `patch.json`（向后兼容，行为与今天一致）。

## 4. 启动器状态机（`windows/launcher.py`）

```
launch()
 ├─ 读 version.txt → installed
 ├─ fetch latest.json（10s 超时；失败 → 静默，继续启动；若已是旧协议则回退 patch.json）
 ├─ [热修通道] hotfix.latest > applied 且 installed >= requires → 现有 apply_hotfix_pack()
 ├─ [版本通道] installer.latest > installed：
 │     ├─ 若 updates\<ver>.exe 已存在且 SHA256 匹配 → 直接置 staged
 │     └─ 否则后台线程：下载到 updates\<ver>.part → 校验 → rename .exe
 │                     → 写 updates\state.json {staged:true, version, sha256, at}
 │                     → 控制台打印 “可升级到 <ver>，按 U 立即升级”
 ├─ 启动 MRRC-Server（不打断用户；升级是否执行由用户决定）
 ├─ 轮询 updates\upgrade.request（1s，来源：页面里的"立即升级"按钮）
 ├─ 读控制台按键（非阻塞）：U = 立即升级，S = 跳过本次
 └─ 用户选择升级 → run_upgrade(staged)
      1) 若 PTT 活跃 → 拒绝并提示（绝不发射中重启）
      2) 优雅停服务（现有 stop_process()）
      3) 提权静默安装：
         ShellExecuteW(None,"runas", setup_exe,
           "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS
            /LOG=\"%LOCALAPPDATA%\\MRRC\\updates\\install-<ver>.log\"", cwd, 1)
         等待进程退出（WaitForSingleObject 语义：subprocess + .wait()）
      4) 退出码 0 且 version.txt 变成新版本 → 重新执行本启动器（拉起新版）
         否则 → 打印 install-*.log 尾部 20 行；保持旧版可用（不自动回滚）
```

**关键实现点**

- `ShellExecuteW` 提权：`ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, cwd, 1)`
  返回 `>32` 表示成功启动；用户拒绝 UAC 会返回 `5`（ERROR_ACCESS_DENIED）→ 明确提示；
- 下载必须**原子**：先写 `.part`，校验通过再 `os.replace()`；失败删 `.part`，
  绝不动现有安装；
- `state.json` 与 `upgrade.request` 都在 `%LOCALAPPDATA%\MRRC\updates\`，都是简单 JSON/标记文件
  （比 IPC 可靠，Windows 上无需额外依赖）；
- 全程单线程主循环 + 一个下载线程；不引入 asyncio。

## 5. 配置开关

```ini
[UPDATE]
enabled = True          ; False = 完全不检查（等价于旧 MRRC_NO_UPDATE_CHECK=1）
autoDownload = True     ; False = 只提示有新版，不预下载
channel = stable        ; 预留（beta 可指向 latest-beta.json）
```

环境变量 `MRRC_NO_UPDATE_CHECK=1` 仍生效（覆盖一切）。

## 6. 页面入口（服务端 + 前端）

- 服务端新增只读接口：
  `GET /api/update` → `{installed, latest, mandatory, notes, staged, lastResult, logTail}`
- 「立即升级」按钮（移动端菜单 + 桌面工具栏各一个入口）：
  `POST /api/update/upgrade` → 服务端写 `updates/upgrade.request`（内容 `{version, at}`）
  → 前端提示"已通知启动器，窗口会弹出 UAC 确认"；
- 升级结果回显：启动器把结果写 `updates/state.json.lastResult`
  （`ok` / `uac_denied` / `install_failed` / `ptt_active` / `sha_mismatch`），页面读取显示。

## 7. 发布流程改动（维护者侧）

`dev_tools/release_windows.sh` 末端新增：

1. 产物归档命名：`MRRC-Setup-<ver>.exe`（保留一份 `MRRC-Setup.exe` 指向最新，
   兼容老书签）；上一版重命名为 `MRRC-Setup-<prev>.exe` 保留在站点；
2. 生成 `latest.json`（installer/hotfix/previous 三段 + notes + minSupported）；
3. 部署 → 线上复核：两个安装包的 `content-length` + SHA256 与本地一致；
4. `patch.json` 继续独立发布（热修），`latest.json` 是总入口。

## 8. 安全与信任边界（诚实记录）

- 仅 HTTPS + 清单内 SHA256 固定校验；**无 Authenticode 签名** → 信任锚 = 站点 TLS；
- 安装时 UAC 是人工确认闸门；静默安装参数固定，不接受来自网络的参数；
- `latest.json` 与安装包同源同站，任一被篡改都无法通过 SHA256 校验（除非同时改清单，
  那就等价于站点被攻破——与今天的手工下载同风险等级）；
- 明确记录：若要消除该风险，需代码签名证书（后续硬化项）。

## 9. 测试

- `tests/test_upgrade_manifest.py`（纯逻辑）：
  - 版本比较（`6.0.10 > 6.0.9`、`v6.1 > 6.0.9`）；
  - 决策表：`installed=6.0.7, latest=6.0.9` → 提示升级；`installed≥latest` → 无动作；
    `installed<minSupported` → 禁用热修、提示完整包；
  - SHA256 不匹配 → 放弃且不产生 `.exe`（只留/删 `.part`）。
- `dev_tools/test_upgrade_flow.py`：用一个假 `latest.json`（指向本地 HTTP 服务）+ 假安装包
  （可直接跑 `cmd /c exit 0` 的占位 exe）驱动 `run_upgrade()` 的下载/校验/装配路径
  （不触发真实安装，验证状态机与回显）。
- VM 端到端（必须）：
  1. 在 VM 里另建一个 6.0.8 版安装包（改 `MyAppVersion` 后跑 `build.ps1`，约 2 分钟）；
  2. `latest.json` 指向它（托管在 VM 本地 HTTP 或线上临时路径）；
  3. 旧版启动器 → 提示升级 → 按 U → UAC → 静默安装 → `version.txt=6.0.8` + 服务起来。

## 10. 验收清单

- [ ] 有新版时：提示 + 后台自动下载 + 校验通过（不打断收听）
- [ ] 按 U / 点页面按钮 → 停服务 → UAC → 静默升级 → 自动拉起新版
- [ ] SHA256 被篡改 → 拒绝，现有安装不受影响，页面显示 `sha_mismatch`
- [ ] 用户拒绝 UAC → `uac_denied`，旧版照常运行
- [ ] 发射中（PTT）→ 拒绝升级并提示
- [ ] 断网 → 静默跳过，不影响启动
- [ ] `[UPDATE] enabled = False` / `MRRC_NO_UPDATE_CHECK=1` → 完全不检查
- [ ] 回退：`previous` 存在时，页面提供「回退到 6.0.7」→ 同一条静默安装路径

---
name: windows-installer
description: MRRC Windows 安装包（MRRC-Setup.exe / Inno Setup）的构建、校验与排障——在 Win11 KVM VM 上跑 packaging/windows/build.ps1（PyInstaller×3 → iscc）、证明产物真的含本次代码、诊断构建中途 VM 失联/OOM、venv 被删、"打了包但行为没变"、缺 DLL 或静态资源、PowerShell 5.1 与 GBK 编码陷阱。当需要出 Windows 安装包、VM 构建失败、或怀疑产物是旧的时使用。
license: GPL-3.0
metadata:
  repo: HAM/mrrc
  orchestrator: dev_tools/release_windows.sh
  build-script: packaging/windows/build.ps1
  hamlib-vendoring: packaging/windows/collect_hamlib.ps1
---

# Windows 安装包构建（MRRC）

## 谁在驱动它

正常发版**不要手敲这套流程**——`./dev_tools/release_windows.sh` 已经编排好了。
本技能是它的排障手册。手动重建时：

```
Mac ──ssh──► ham.vlsc.net（KVM 宿主）──ssh──► cheenle@192.168.122.133（win11 VM）
                                              默认 shell 是 PowerShell 5.1
```

`packaging/windows/build.ps1` 的门禁顺序（任一步失败即中止，`Invoke-Checked`，见其 :6）：

1. `python -m py_compile` 全部 Python
2. `python -m unittest discover -s tests -v`（全量套件）
3. `dev_tools/test_config_encoding.py`
4. 三个 PyInstaller spec：`packaging/pyinstaller/mrrc_server.spec`、`mrrc_launcher.spec`、
   `atr1000_proxy.spec`
5. 从 `MRRC.iss` 读 `MyAppVersion` 写 `dist/windows/MRRC/version.txt`（:79-86）
6. NR3 的 `rnnoise.dll` 用 gcc 现场编译（:101-118，注释在 :110；**刻意不走 `Invoke-Checked`**
   ——gcc 的 `-I`/`-O` 会被 PowerShell 函数参数绑定误解析；失败只告警）
7. `iscc packaging/windows/MRRC.iss` → `dist/windows/MRRC-Setup.exe`

**`libwdsp.dll` 不是 `build.ps1` 的一步，而是先决条件**：VM 上先跑
`packaging/windows/build_wdsp_dll.ps1` 生成它（见 `win_pack.md` / `release-process.md` §3），
`build.ps1:48-67` 只检查 `vendor/{opus,hamlib,wdsp}/windows/bin/x64/` 里有没有、缺了
**只警告不中止**——所以"构建成功"不等于包里带了 DSP。

`MRRC.iss` 只打包 `dist\windows\MRRC\*`（`ignoreversion recursesubdirs createallsubdirs`）
——**原生 DLL 必须先落到 `vendor/{opus,hamlib,wdsp}/windows/bin/x64/`**，否则包里没有它们；
hamlib（含 `rigctld.exe`）用 `packaging/windows/collect_hamlib.ps1` 收集。见 `win_pack.md`。

## 证明产物真的含本次代码（**不要**只看退出码）

`release_windows.sh:84` 只把 `build exit=$LASTEXITCODE` 打进日志。**退出码不是证据**——
`Invoke-Checked` 中止的是*子* PowerShell，外层脚本会继续往下走。只认产物：

```powershell
Get-Item C:\mrrc\dist\windows\MRRC-Setup.exe | Select-Object Length, LastWriteTime
Get-FileHash C:\mrrc\dist\windows\MRRC-Setup.exe -Algorithm SHA256
Get-Content C:\mrrc\dist\windows\MRRC\version.txt     # 必须 == 本次 iss 版本
```

Mac 侧取回后再比对一次：`shasum -a 256 dist/windows/MRRC-Setup.exe` 必须等于 VM 的 `Get-FileHash`。

**`strings`/`grep` 看不进压缩的 PYZ**——缺失的符号和存在的符号长得一模一样。要证明符号在包里，
走归档（VM 的 venv 有 PyInstaller）：

```python
# bundle_check.py —— 在 VM 上跑：.\venv\Scripts\python.exe bundle_check.py
import marshal, types
from PyInstaller.archive.readers import CArchiveReader
r = CArchiveReader(r"C:\mrrc\dist\windows\MRRC\MRRC-Server.exe")
# 注意：PyInstaller 6 里 r.toc 是 dict，不是 list；r.toc[0] 会 KeyError: 0
try:
    code = marshal.loads(r.extract("server"))       # 入口"脚本"是 CArchive 条目，不是 PYZ 模块
except Exception:
    code = marshal.loads(r.extract("server")[8:])   # 可能带 8 字节头
seen = set()
def walk(c):
    seen.update(c.co_names)
    for k in c.co_consts:
        if isinstance(k, types.CodeType): walk(k)
walk(code)
print("你要验的符号" in seen)
```

## 热修覆盖面 = 打包时被踢出 PYZ 的那批模块

`packaging/pyinstaller/mrrc_server.spec:137` 刻意把 `_APP_MODULES`（:28-47）排除出 PYZ，
好让 `patch_overlay.py` 能在运行时用 `%LOCALAPPDATA%\MRRC\patch` 里的 `.py` 覆盖它们。
**新增一个需要可热修的模块，必须同时加进 `_APP_MODULES`**——`upgrade_core` 漏过一次，
VM 实测报 `ModuleNotFoundError`。

## 在产物上跑热修通道验收

`release_windows.sh:87` 会在打包产物上跑 `packaging/hotfix/verify_hotfix.py`。
它从 `%LOCALAPPDATA%\MRRC\` 找配置、按启动器的方式解包到 `patch\`、再启动 `MRRC-Server.exe` 验证。
手动跑（VM 上仓库根是 `C:\mrrc`，即 `release_windows.sh` 的 `VM_REPO`——**不是**
`%USERPROFILE%\mrrc`）：

```powershell
Set-Location C:\mrrc
& C:\mrrc\venv\Scripts\python.exe packaging\hotfix\verify_hotfix.py `
    --app "C:\mrrc\dist\windows\MRRC" --repo "C:\mrrc"
```

## VM 上的陷阱（多数在本仓库实测过）

1. **SSH 会话一断，`Start-Process` 起的子进程会被回收**（Windows job object）。
   长任务别用裸 `ssh ... Start-Process`；用计划任务：
   `schtasks /create /tn X /tr <命令行> /RL HIGHEST /RU <user> /IT` 再 `schtasks /run /tn X`。
   **`/tr` 里别塞引号。**
2. **含中文的 `.ps1` 必须存成 UTF-8 单 BOM**，否则 PowerShell 5.1 按 GBK 读，脚本直接语法错。
3. **`Tee-Object` 没有 `-Encoding` 参数**——写了会报参数不存在。
4. **PowerShell 5.1 的 `&&` 非法**，用 `;`。`2>` 重定向写出的是 UTF-16LE，
   `grep` 前先 `iconv -f UTF-16LE -t UTF-8`。多跳 ssh 的引号嵌套是个坑，
   **总是把命令写成 `.ps1` 本地文件 → scp → `-File` 执行**。
5. **`ham.vlsc.net` 的 `/tmp` 是 454 MB tmpfs**。大文件先传到 `~` 再 `sudo mv` 进去。
   本仓库的产物（exe ~45 MB）不会撞线，但源码包+多份归档要留神。
6. **VM 的网络对 ~45 MB 下载不稳**。离线验收可以用
   `MRRC_UPDATE_MANIFEST=file://…` 指本地清单跑，避免卡在下载上。
7. **venv 会在解压源码时被删掉**：解压前 `Move-Item C:\mrrc\venv C:\mrrc_venv_keep`，
   解压后移回来。venv 真没了就按 `win_pack.md` 的完整重装序列来——
   否则 `.\venv\Scripts\Activate.ps1` 不存在，构建立刻失败。
8. **`requirements-build.txt` 变过就要重装依赖**（保下来的 venv 里是旧依赖）。
9. **"本地绿、VM 红"通常是打开文件没关**：测试留下未关闭的文件句柄时，macOS/Linux 允许
   删除打开的文件，Windows 报 `PermissionError: [WinError 32] ... being used by another process`
   （`TemporaryDirectory.cleanup()` 阶段）。在 `tearDown` 里关掉它。
   **把它当真实的跨平台 bug，不要当 VM 怪癖。**
10. **TX 音频永远无法在这台 VM 上验证**：KVM 的 USB 透传破坏同步 OUT 调度
    （MME 与 WASAPI 一样乱；RX 采集与 FT4222 批量传输不受影响）。别在这儿调 TX 噼啪声，
    去物理 Windows 机器上验。
11. **电台 USB 被拔掉会连带 COM 口和音频设备一起消失**，直到重新附加透传设备。
12. **宿主可能在中途 OOM 掉整个 VM**（*此条出自 `mrrc_modern` 在同宿主的实测，2026-09-12*）：
    症状依次是 `ssh` 报 `No route to host` → `virsh -c qemu:///system domifaddr win11`
    说 domain not running → `/var/log/libvirt/qemu/win11.log` 结尾 `shutting down, reason=crashed`
    → `sudo dmesg -T | grep -i oom` 看到 `Killed process ... (qemu-system-x86)`。
    处置：把 VM 缩到 10 GB 并给宿主加 swap，`virsh start win11` 前先看 `free -m`
    （可用 <1 GB 就还会再死一次）。

## 常见症状对照

| 症状 | 原因 / 处置 |
| --- | --- |
| 脚本打印构建完成但没有新 exe | 退出码不是证据（见上）；看 `Get-Item` 的 mtime + 大小 + `Get-FileHash` |
| 包里缺 opus/hamlib/wdsp 的 DLL | 原生 DLL 没先落到 `vendor/*/windows/bin/x64/`；hamlib 用 `collect_hamlib.ps1` 收 |
| 装了包但行为没变 | 符号不在包里（走 `CArchiveReader` 验）；或改的是 `_APP_MODULES` 里的模块但没进列表 |
| `ModuleNotFoundError` 只在热修后出现 | 该模块**没**在 `mrrc_server.spec` 的 `_APP_MODULES` 里 |
| `Activate.ps1` 找不到 | venv 在解压时被删（陷阱 7） |
| 含中文的 `.ps1` 报语法错 | 存成了无 BOM（陷阱 2） |
| 长任务在 ssh 断开后消失 | job object 回收（陷阱 1）；改用 `schtasks` |
| VM 中途失联 | 宿主 OOM（陷阱 12） |
| 本地绿、VM 报 `WinError 32` | 测试泄漏了打开的文件句柄（陷阱 9） |
| VM 上 TX 噼啪 | KVM 同步 OUT 坏（陷阱 10）；去物理机验，别改代码 |

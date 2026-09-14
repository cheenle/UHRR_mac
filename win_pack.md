# Windows 安装包打包流程

> 用途：在 Windows 构建机（参考 `../mrrc_modern` 的 Win11 KVM）上构建 `MRRC-Setup.exe`。
> 本文按 `../mrrc_modern/win_pack.md` 的同样结构整理。

## 1. 环境要求

- Windows 10/11 x64
- Python 3.12+（`python` 在 PATH）
- Inno Setup 6（`C:\Program Files (x86)\Inno Setup 6\iscc.exe`）
- 仓库根目录下已建 `venv` 并安装依赖

## 2. 一次性准备

```powershell
cd C:\mrrc
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m pip install -r packaging\windows\requirements-build.txt
```

把需要的 Windows 原生 DLL 放到 `vendor/` 对应目录：

| 功能 | 文件路径 |
|------|----------|
| Opus 音频 | `vendor\opus\windows\bin\x64\opus.dll` |
| Hamlib 电台控制 | `vendor\hamlib\windows\bin\x64\libhamlib.dll` 或 `hamlib.dll` |
| WDSP 数字信号处理 | `vendor\wdsp\windows\bin\x64\libwdsp.dll` 或 `wdsp.dll` |

缺失 DLL 时构建脚本只会警告，仍能出包；但运行时会缺少对应功能。

### 2.1 构建 WDSP DLL（**必做**，否则 Windows 上 WDSP 完全不可用）

历史上 `vendor\wdsp\windows\bin\x64\` 一直是空的：WDSP 的 macOS/Linux 构建走 Makefile，
Windows 只有 MSVC 工程而且编不过（MSVC 专有写法 + MSVCRT 符号冲突），所以 6.0.0 之前的
Windows 包根本没带 WDSP 库。现在用 **MSYS2/MinGW-w64** 编（已脚本化）：

```powershell
cd C:\mrrc
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\windows\build_wdsp_dll.ps1
```

脚本会：清掉 macOS/Linux 残留 `.o` → 编 60 个 `.c`（排除 JNI 桥）→ 校验
`SetRXAEMNRmaxAttenDb`/`SetRXAEMNRdry`/`SetRXANBPFreqs` 等导出 → 确认运行时只依赖
`KERNEL32.dll`/`msvcrt.dll` → 复制到 `vendor\wdsp\windows\bin\x64\libwdsp.dll`。

前置：MSYS2 装在 `C:\msys64`，带 `mingw-w64-x86_64-gcc` 与 `mingw-w64-x86_64-fftw`。
FFTW 用静态 `libfftw3.a` 链接（`-static`），所以不需要额外 Windows DLL。

**源码侧的 Windows 可构建性修复**（已包含在源码包里，patch 存档）：

- `DSP/patches/2026-09-13-windows-mingw-build.patch`：平台守卫 `defined(linux) || defined(__APPLE__)`
  补上 `__MINGW32__`、`iobuffs.h` 的 `struct _iob` 改名避开 MSVCRT 同名符号、
  POSIX shim 的 `EnterCriticalSection`/`CloseHandle` 等在 mingw 下前缀化避免与 libkernel32 冲突。
  应用：`cd DSP/wdsp && patch -p1 < ../../DSP/patches/2026-09-13-windows-mingw-build.patch`。
- 已应用于仓库里的 `DSP/wdsp/` 源码（源码包即 patched 状态，通常无需再跑 patch）。

> 踩坑记录：① PowerShell 脚本带中文注释 **必须存 UTF-8 with BOM**，否则 PS 5.1 按 GBK 读会语法崩；
> ② `-static` 不能省，否则包里要再带 `libwinpthread-1.dll`/`libfftw3-3.dll`；
> ③ 用 `objdump -p libwdsp.dll` 看 `DLL Name` 与导出表，比 `nm` 直观。
>
> 经验：NR2 最关键的一半修复（估计器固定 MMSE）在 Python 侧，不依赖新 DLL；
> 但“每 bin 最大衰减”“SSB 带通走 nbp0（消除 NR2 关闭后静音）”“干湿混合”必须有新 DLL。

## 3. 每次打包

```powershell
cd C:\mrrc
.\venv\Scripts\Activate.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

产物：

- `dist\windows\MRRC\` — 已组装的绿色程序目录
- `dist\windows\MRRC-Setup.exe` — Inno Setup 安装包

## 4. 启动器行为

安装后用户通过 `MRRC-Launcher.exe` 启动：

1. 在 `%LOCALAPPDATA%\MRRC\` 创建配置目录。
2. 首次运行从模板生成 `MRRC.conf`，并把证书/数据库/频道记忆文件放到配置目录。
3. 生成 10 年期自签 TLS 证书到 `%LOCALAPPDATA%\MRRC\certs\`。
4. 首次运行自动生成本机登录账号，写入 `%LOCALAPPDATA%\MRRC\MRRC_users.db`，并生成 `%LOCALAPPDATA%\MRRC\MRRC Quick Start.txt`。
5. 尽量自动选择 Windows 串口（优先非 `COM1` 的第一个串口），音频默认用稳定的名称片段 `USB Audio`。
6. 把 `vendor\*\windows\bin\x64` 加入进程 `PATH`。
7. 启动 `MRRC-Server.exe <MRRC.conf>`。
8. 等待 HTTPS 端口响应，自动打开浏览器。

普通用户最简流程：安装后点 `MRRC`，浏览器打开后接受自签证书提示；登录用户名默认是 `admin`，首次生成的密码会显示在启动窗口、本机登录页，以及开始菜单 `Login Info` 打开的 quick start 文件中。

## 5. 注意事项

- MRRC 通过 `rigctld` 控制电台。Windows 用户需要自行运行 Hamlib 提供的 `rigctld.exe`，例如：
  ```powershell
  rigctld.exe -m 30003 -r COM3 -s 4800 -C stop_bits=2 -T 127.0.0.1 -t 4532
  ```
- ATR-1000 天调代理为可选组件：`ATR1000-Proxy.exe`。Windows 默认通过 localhost TCP 连接代理：
  ```powershell
  ATR1000-Proxy.exe --device 192.168.1.63 --port 60001 --transport tcp --tcp-host 127.0.0.1 --tcp-port 60100
  ```
  对应 `MRRC.conf` 的 `[INSTANCE_SETTINGS] atr1000_proxy_transport=tcp / atr1000_proxy_port=60100`。
- 本机 macOS/Linux 无法交叉编译 Windows 原生 DLL，因此打包前必须先在 Windows 上准备好 `vendor/` 中的 DLL。

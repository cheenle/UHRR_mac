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
- ATR-1000 天调代理为可选组件：`ATR1000-Proxy.exe`。默认 MRRC 通过 Unix Socket 连接代理；在 Windows 上如需使用，建议把代理配置为 TCP 模式或命名管道。
- 本机 macOS/Linux 无法交叉编译 Windows 原生 DLL，因此打包前必须先在 Windows 上准备好 `vendor/` 中的 DLL。

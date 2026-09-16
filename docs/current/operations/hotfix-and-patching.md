# 热修补丁（hotfix）与不重新打包修 bug

> 目标：**修一个小 bug 不再需要重新打包、重新上传 45 MB、让用户重装**。
> 适用范围与硬限制都写在这里，配套工具在 `packaging/hotfix/`，核心机制在 `patch_overlay.py`。

## 1. 实测结论（决定方案的那次实验，2026-09-14）

用 PyInstaller 6.22.3 的 onedir 包做覆盖实验：

| 尝试 | 结果 |
|------|------|
| 同名 `.py` 放 exe 同目录 | ✗ 仍是冻结版 |
| 放 `_internal/` | ✗ 仍是冻结版 |
| 放当前工作目录（cwd） | ✗ 仍是冻结版 |
| 用 `PYTHONPATH` | ✗ 仍是冻结版 |
| `sitecustomize.py` | ✗ 冻结运行时连 `site` 都不导入，脚本不执行 |
| **未被冻结**的模块放 `_internal/` | ✅ **成功从磁盘导入** |

根因：PyInstaller 把 `PyiFrozenFinder` 插进 `sys.path_hooks`
（`PyInstaller/loader/pyimod02_importers.py`），**PYZ 里的模块名一律先被截走**。
而 `sys.path` 是 `[_internal/base_library.zip, _internal/lib-dynload, _internal]`
（exe 目录不在其中），所以没进 PYZ 的模块会由文件系统加载。

于是打包策略改为：**应用自己的代码不进 PYZ**（`packaging/pyinstaller/mrrc_server.spec`
里 `_APP_MODULES` + `pyz = PYZ([...不含它们...])`，同时用 hiddenimports 保住依赖分析），
作为数据文件放到 `_internal/app/`，运行时由 `packaging/pyinstaller/frozen_entry.py`
加入 `sys.path`。

## 2. 覆盖层（overlay）

根目录按优先级：

1. 环境变量 `MRRC_PATCH_DIR`（启动器会设置）
2. 配置文件同级的 `patch/` —— 冻结安装即 **`%LOCALAPPDATA%\MRRC\patch`**（用户可写，**不需要管理员**）
3. 源码模式：仓库根下的 `patch/`

内部布局与内置资源同构：

```
%LOCALAPPDATA%\MRRC\patch\
  app\      ← 覆盖 _internal\app\：MRRC、wdsp_wrapper.py、audio_interface.py …
  www\      ← 覆盖 _internal\www\：controls.js、mobile_modern.html …
  vendor\   ← 覆盖 DLL：wdsp\windows\bin\x64\libwdsp.dll 或直接平铺 libwdsp.dll
  applied.json   （脚本/启动器记录已应用内容，供排查）
```

生效方式：

| 覆盖内容 | 何时生效 |
|---|---|
| `www/**` | 刷新浏览器即可（www 强制 no-cache） |
| `app/*.py`、`app/MRRC`、`vendor/*.dll` | **重启 MRRC-Launcher / 服务** |

启动日志会打印一行证据：

```
🧩 补丁覆盖层已启用: C:\Users\...\AppData\Local\MRRC\patch（2 个文件：app/wdsp_wrapper.py, www/controls.js）
```

也可以随时查询（WebSocket）：`getPatchStatus`（详细，含 SHA256）/ `patchList`（仅文件名）。

## 3. 三种投递方式

### 3.1 启动器自动（6.0.3+，推荐）

`MRRC-Launcher.exe` 启动时读 `https://www.vlsc.net/mrrc/downloads/patch.json`：

```json
{
  "latest": "6.0.4",
  "url": "https://www.vlsc.net/mrrc/downloads/hotfix-6.0.4.zip",
  "sha256": "…",
  "requires": "6.0.3",
  "notes": "修复 …",
  "files": ["app/wdsp_wrapper.py", "www/controls.js"]
}
```

满足 `latest > 本机版本` 且 `本机版本 >= requires` 才下载；**SHA256 不符就放弃**；
任何失败都只打印一行警告，不影响启动。解压到覆盖层后照常启动服务 → 用户无感完成修复。

关闭方式：配置文件 `[HOTFIX] enabled = False`，或环境变量 `MRRC_NO_UPDATE_CHECK=1`。

### 3.2 手动/离线：`apply_hotfix.ps1`

```powershell
# 覆盖层模式（无需管理员，6.0.3+）
powershell -ExecutionPolicy Bypass -File apply_hotfix.ps1 -Pack hotfix-6.0.4.zip

# 就地模式（仅 6.0.2 及更早，需要管理员；只能放 www/ 与 DLL）
powershell -ExecutionPolicy Bypass -File apply_hotfix.ps1 -Pack hotfix-x.zip -InPlace
```

就地模式会拒绝 `app/*` 条目并明确说明原因：**6.0.2 及更早把 Python 代码冻结在 exe 的
PYZ 里，磁盘覆盖无效** —— 这类修复必须装 6.0.3+ 或完整重装（不"假装修好了"）。
写入前会把被替换的文件备份成 `*.bak-<版本>`。

### 3.3 制作补丁：`make_hotfix.py`

```bash
# 改完文件后（也可用 --range v6.0.2..HEAD 自动挑）
python3 packaging/hotfix/make_hotfix.py --version 6.0.4 \
    --notes "修复 S 表在 iOS 上的闪烁" www/controls.js wdsp_wrapper.py

# 发布
cp dist/hotfix/* website/downloads/ && ./deploy_website.sh
```

产物是 `hotfix-<ver>.zip`（含逐文件 SHA256 的 `manifest.json`）与 `patch.json`。
工具按 spec 里的 `_APP_MODULES` 校验**只接受真正可热修的文件**：

| 改了什么 | 能否热修 |
|---|---|
| `www/**` | ✅ |
| 松散应用模块 `.py`（`_APP_MODULES` 列表） | ✅ |
| `MRRC` 主程序（→ `app/MRRC`） | ✅ |
| `vendor/**/*.dll` | ✅ |
| `requirements.txt`、新增依赖、C 扩展、`windows/launcher.py`、`atr1000_proxy.py` 等 | ❌ 必须重新打包（工具会拒绝并说明） |

## 4. 完整重建仍然要做的场景

- 新增/升级 Python 依赖（PyInstaller 需要重新收集）
- 改动 C 扩展或 WDSP 之外的本地库
- 启动器（`MRRC-Launcher.exe`）与 `ATR1000-Proxy.exe` 本体（它们仍是冻结入口）
- Inno 安装器本身的设置（`MRRC.iss`）

完整重建成本（已有脚本，`ham.vlsc.net` 的 Win11 KVM）：DLL 约 20 s、PyInstaller+iscc 约 1.5 min，
取回并部署约 3 min。真正的代价在用户端 45 MB 下载 —— 这正是热修通道要省掉的部分。

## 5. 安全边界

- 补丁包只从本站 HTTPS 拉取，且必须匹配 `patch.json` 里的 SHA256；校验失败即放弃。
- 解压时拒绝绝对路径与 `../` 穿越（`apply_hotfix_pack` 里显式检查）。
- 覆盖层里的 Python 代码以服务进程权限运行 —— 信任锚等同于安装包本身（同一来源、同一 HTTPS）。
- 覆盖层与安装目录分离，出问题只需删掉 `%LOCALAPPDATA%\MRRC\patch` 即可回退到内置版本；
  就地模式则用 `*.bak-<版本>` 回滚。

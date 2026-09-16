# 发版流程（Windows 安装版 + 站点清单）

> 上下游：本文是《[产品支持生命周期](product-support-lifecycle.md)》的**第 1 步（开发发版）**实施细则；
> 下一步是 [版本升级](one-click-upgrade.md)。

> 适用范围：发布 `MRRC-Setup.exe`（Windows 安装版）、`latest.json`（一键升级清单）、
> `patch.json`（热修清单）到 `https://www.vlsc.net/mrrc/`。
> 相关：`docs/current/operations/one-click-upgrade.md`、`hotfix-and-patching.md`、
> `win_pack.md`（Windows 构建环境）、`dev_tools/release_windows.sh`。

## 0. 一句话版

```bash
./dev_tools/release_windows.sh      # 构建 → 产物上热修验收 → 取回 → 归档上一版
                                    # → 生成 latest.json → 提交 → 部署 → 线上复核
```

**站点复核是硬要求**：必须用 **服务器侧** `sha256sum` 对比清单里的 `installer.sha256`
（本机到站点的下载链路可能很慢/超时，但"服务端字节"才是用户拿到的东西）。

---

## 1. 版本语义（唯一权威）

| 载体 | 作用 |
|---|---|
| `packaging/windows/MRRC.iss` 的 `MyAppVersion` | **安装版本**（写进 `dist\windows\MRRC\version.txt`） |
| `version.txt`（安装目录） | 运行时唯一权威版本，升级决策只认它 |
| `patch.json` 的 `latest` | **热修通道**版本（不改安装版本） |
| `latest.json` 的 `latest` | 可得的最新安装版 |

硬约束：

1. **安装版本必须 > 热修通道最新版本**，否则启动器会反复重放旧热修；
2. 拒绝降级（`plan_upgrade` 里 `version_tuple` 比较）；
3. `minSupported` 决定多老的安装还能拿到热修；低于它的用户会被要求装完整包；
4. 版本号同时要改：`MRRC.iss`、`www/mobile_modern*.html`（页脚 + CSS `?v=`）、
   `README.md`、`website/**`（含 zh）——`grep -rn "V6\.[0-9]" website README.md` 兜底。

---

## 2. Windows 构建（只能在 Windows 上做）

本机（macOS）**没有** wine/qemu → 构建在 `ham.vlsc.net` 上的 Win11 KVM 里做：

```powershell
# VM: C:\mrrc （venv=C:\mrrc\venv，MSYS2=C:\msys64，产物 C:\mrrc\dist\windows）
Expand-Archive C:\tmp\mrrc_build_src.zip -DestinationPath C:\mrrc -Force   # 源码包由仓库打包
powershell -File packaging\windows\build_wdsp_dll.ps1                      # 先出 libwdsp.dll
powershell -File packaging\windows\build.ps1                               # PyInstaller + Inno
python packaging\hotfix\verify_hotfix.py --app C:\mrrc\dist\windows\MRRC --repo C:\mrrc
```

`verify_hotfix.py` 是**产物级验收闸门**（前端热修 / Python 热修 / 覆盖层对服务端可见，3/3 必须通过）。
它还会跑一次服务端，所以**构建前要先停掉 VM 上正在跑的 MRRC**，否则端口冲突会让验收崩掉。

### VM 操作陷阱（都是实测踩过的）

- **SSH 会话结束会回收 `Start-Process` 拉起的子进程** → 要让 GUI/长任务留在用户会话里，
  必须用计划任务：`schtasks /create /tn X /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\tmp\x.ps1" /sc once /st 23:59 /RL HIGHEST /RU cheenle /IT /F` 然后 `/run`；
  `/tr` 里**不要塞引号**（`set "X=Y"` 之类会直接被 schtasks 拒掉）。
- PowerShell 5.1 读脚本按 GBK：**含中文的 `.ps1` 必须存 UTF-8 with BOM，且只能有一个 BOM**
  （双 BOM 会让 `param(...)` 解析失败）。
- `Tee-Object` **没有** `-Encoding` 参数；`if (...) {...} | Out-File` 会报 `EmptyPipeElement`（`if` 不能直接进管道）。
- 中文控制台 GBK 下的 emoji 会让 `print` 抛 `UnicodeEncodeError`（见 RC-002 §5）。

---

## 3. 上架与清单

```bash
# 3.1 取回产物（Mac ← ham ← VM，经宿主中转）
ssh ham.vlsc.net 'scp cheenle@192.168.122.133:C:/mrrc/dist/windows/MRRC-Setup.exe /tmp/new.exe'
scp ham.vlsc.net:/tmp/new.exe /tmp/MRRC-Setup-<ver>.exe

# 3.2 站点文件（全部必须 git 入库！）
cp /tmp/MRRC-Setup-<ver>.exe website/downloads/MRRC-Setup-<ver>.exe   # 带版本名（清单指向它）
cp /tmp/MRRC-Setup-<ver>.exe website/downloads/MRRC-Setup.exe         # 兼容老书签
# 上一版归档（回退目标，同样必须入库）
git rm --cached website/downloads/MRRC-Setup-<更旧>.exe; rm website/downloads/MRRC-Setup-<更旧>.exe

# 3.3 生成 latest.json（installer/previous/hotfix/notes）
python3 dev_tools/make_latest_json.py --version <ver> \
    --installer /tmp/MRRC-Setup-<ver>.exe --previous <上一版> --notes "…"

# 3.4 提交 + 部署 + 复核
git add website/downloads README.md website && git commit -m "release: V<ver> …" && git push
./deploy_website.sh
ssh cheenle@www.vlsc.net 'cd /var/www/vlsc.net/mrrc/downloads && sha256sum MRRC-Setup.exe MRRC-Setup-<ver>.exe'
```

### 关键约束与坑

- **`deploy_website.sh` 是 `rsync --delete`** → **任何没进 git 的服务器文件都会被删掉**。
  回退目标（`previous`）因此**必须入库**，否则【回退到上一版】按钮 404
  （2026-09-16 实际发生过一次）。
- **服务器 `/tmp` 是 454 MB tmpfs**：连传几个 45 MB 安装包就会写失败
  （`scp: write remote "/tmp/x.exe": Failure`）→ 大文件先传 `~`，再 `sudo mv`。
- 清单里的 `installer.sha256` 必须等于 **带版本名**的那个文件（生成器自动取该文件；
  不要把 `MRRC-Setup.exe` 的名字写进清单）。
- 站点上是**扁平的** `downloads/`：`latest.json`、`patch.json`、`MRRC-Setup*.exe`、
  `hotfix-*.zip` 全在同一层。

---

## 4. 热修（不改安装版本的补丁）

```bash
python3 packaging/hotfix/make_hotfix.py --version <ver> --requires 6.0.3 \
        --notes "…" <改动过的仓库文件…>         # 产物：dist/hotfix/hotfix-<ver>.zip + patch.json
cp dist/hotfix/hotfix-<ver>.zip dist/hotfix/patch.json website/downloads/
git add … && git commit -m "hotfix <ver>: …" && git push && ./deploy_website.sh
```

**哪些文件可热修**（决定"要不要重新打包"）：

| 位置 | 能否热修 | 说明 |
|---|---|---|
| `www/**`（前端） | ✅ | 覆盖层优先，tornado 静态路由也走覆盖层 |
| `_APP_MODULES` 里的模块（`patch_overlay`/`rig_models`/`support_bundle`/`upgrade_core`/`config_io`/`audio_interface`/`hamlib_wrapper`/`wdsp_wrapper`/…） | ✅ | 松散文件放 `_internal\app\`，覆盖层目录在 `sys.path` 最前 |
| 其它 Python（如 `MRRC` 主脚本、`windows/launcher.py`） | ❌ | 在 PyInstaller 的 PYZ 里 → 只能重发安装包 |
| 第三方依赖 / 原生库 | ✅（vendor） | 覆盖层 `vendor` 排在搜索路径最前 |

因此**"升级逻辑本身的修复"要看它落在哪个文件**：`upgrade_core.py` 可热修（V6.1.10/11 就是这么
下发的），`windows/launcher.py` 的改动必须重发包。

---

## 5. 发布后复核清单

- [ ] 服务器侧 `sha256sum MRRC-Setup.exe MRRC-Setup-<ver>.exe` 与构建产物一致；
- [ ] `latest.json`：`latest` / `installer.url`（带版本名）/ `installer.sha256` / `previous.version` 都对；
- [ ] `MRRC-Setup-<上一版>.exe` 在站上**确实存在**（回退可用）；
- [ ] 站点首页/安装页显示的版本号 == 新版本；
- [ ] `patch.json` 的 `latest` **小于**安装版本；
- [ ] 有条件的做一次真机升级（见 `dev_tools/vm_upgrade_e2e.ps1`），
      `state.json` 的 `lastResult.status` 应为 `ok`。

---

## 6. 真机升级验收（可选但强烈建议）

`dev_tools/vm_upgrade_e2e.ps1`（UTF-8 with BOM）参数化基线/目标版本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\tmp\vm_upgrade_e2e.ps1 -Base 6.1.8 -Target 6.1.9
```

要点：
- 用 `MRRC_UPDATE_MANIFEST=file:///…/test-latest.json` 指向**本地清单+本地安装包**，
  可完全离线验证（不被站点网络波动干扰）；
- 必须在**管理员 + 用户会话**里跑（计划任务 `/RL HIGHEST /RU <user> /IT`），
  否则静默安装拿不到提权、或被 SSH 会话回收；
- 判定标准：`version.txt` 变成目标版本 **且** `state.json.lastResult.status == "ok"`
  （`ok` 是唯一成功态，由新版启动时自证）。

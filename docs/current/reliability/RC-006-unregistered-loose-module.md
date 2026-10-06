# RC-006 · 松散模块没登记进 spec：安装包一启动就 `ModuleNotFoundError`

> - 发现日期：2026-10-06（V6.2.0 构建后的**洁净室真跑**，即四层验证的第 4 层）
> - 影响版本：`antenna_sweep` 自 `b61553f`（天线 SWR 扫频基础设施）引入起即存在；
>   **6.1.18 及更早的安装包不含该 import，所以从未暴露**。V6.2.0 会是第一个带它的包
> - 影响面：**安装包完全不可用**（服务端进程启动即崩，不是某个功能坏掉）
> - 状态：✅ 已修（V6.2.0）+ ✅ 已加守卫 `tests/test_frozen_module_coverage.py`
> - 关联：[RC-005](RC-005-plaintext-credentials-in-installer.md)、
>   windows-installer 技能的「四层验证」

## 现象

前三层验证**全绿**：

| 层 | 结果 |
| --- | --- |
| 1 三证合一 | exe 66,274,902 B、mtime `2026-10-06 11:56:58`、sha `28da945a…` ≠ 6.1.18 的 `c103998…`、`version.txt = 6.2.0` ✅ |
| 2 结构核对 | 三个 exe 齐、`fleet\frpc.exe` 16,708,608 B 且哈希与 `payload.lock` 一致、`_internal\app\` 下 20 个松散 .py 一个不缺、junk 0、密钥形状 0 ✅ |
| 3 符号走查 | 33 项全 OK：`_internal/app/MRRC` 里有 `import cloud_hub`、四个 `/api/cloud/*` 路由、`cloud_hub.py` 的 `find_frpc`/`TunnelProcess`/POSIX `ps -eo` 分支都在 ✅ |

第 4 层（拿隔离配置真跑打出来的 exe）**一启动就死**：

```
File "C:\mrrc\dist\windows\MRRC\_internal\app\MRRC", line 2675, in <module>
    import antenna_sweep as _antsw
ModuleNotFoundError: No module named 'antenna_sweep'
[PYI-9280:ERROR] Failed to execute script 'frozen_entry' due to unhandled exception!
```

## 根因链

1. **本仓的冻结入口不 import 应用代码。** `packaging/pyinstaller/frozen_entry.py` 把
   `_internal/app` 加进 `sys.path`，然后用 `runpy.run_path(_internal/app/MRRC, run_name="__main__")`
   跑它。这是热修覆盖层能生效的前提：PyInstaller 6 的 `PyiFrozenFinder` 会截走 PYZ 内
   所有同名模块，磁盘上的 `.py` 覆盖无效，所以应用代码必须留在 PYZ 外（见 `patch_overlay`
   头部与 `mrrc_server.spec:20-26` 的实验记录）。
2. **代价是 PyInstaller 的 Analysis 看不到 `MRRC` 的任何 import。** 一个模块要进包，
   必须被显式登记在两处之一：
   - `_APP_MODULES` → 作为数据文件发到 `_internal/app/<name>.py`（松散、可热修）
   - `hiddenimports` → 冻进 PYZ
3. `antenna_sweep` **两处都没有**。而 `MRRC:2673` 的注释明明写着
   「引擎在 antenna_sweep.py（**松散模块**，回调注入）」—— 意图是对的，登记漏了。
   `grep -n antenna_sweep packaging/pyinstaller/mrrc_server.spec` → 0 命中。
4. 于是它既不在 PYZ 里、也没被当数据文件发出。运行时 `sys.path` 上的
   `_internal/app/` 里没有 `antenna_sweep.py`，PYZ 里也没有 ⇒ `ModuleNotFoundError`。
   而 `MRRC:2675` 是**模块级**的无条件 import，所以进程直接起不来。

> 这与 `upgrade_core` 那次是同一族，但方向相反：`upgrade_core` 是"该在 `_APP_MODULES`
> 里却漏了 ⇒ 热修后 `ModuleNotFoundError`"；本次是"被 `MRRC` import 却两处都没登记
> ⇒ 装完就起不来"。两者都源于同一条事实：**Analysis 看不见 runpy 加载的代码。**

## 为什么前三层抓不到

- 第 1 层只看产物元数据（时间/大小/哈希），与内容无关；
- 第 2 层数的是**已知该在的东西**（三个 exe、frpc、20 个松散 .py）—— 少一个"本该有第 21 个"
  的文件，清单本身不知道；
- 第 3 层查的是 `cloud_hub` 这条本次改动的链路，`antenna_sweep` 不在待查符号里。

只有"真的把 exe 跑起来"能发现。这正是 windows-installer 技能里那句话的实例：
**退出码、`Successful compile`、`version.txt`、产物哈希全绿，也不代表包能用。**

## 修复

1. `mrrc_server.spec`：`_APP_MODULES` 加 `"antenna_sweep"`（符合原作者注释的意图，
   同时让它可热修）。修完松散 .py 从 20 个变 21 个。
2. **确认它的依赖不会跟着缺**：`antenna_sweep.py` 只 import `json/os/statistics/threading/time`。
   松散模块是运行时从磁盘加载的，它的 stdlib 依赖必须**已经在 PYZ 里**。
   实测 `PYZ.pyz` 的 486 个模块中 `statistics` = True（`json/threading/ssl/socket/configparser`
   同样在），所以不需要动 `hiddenimports`。
   > 这一步不能省：`statistics` 只有 `antenna_sweep` 在用，如果它不在 PYZ 里，
   > 修好第一个 import 就会撞上第二个。
3. 新增守卫 `tests/test_frozen_module_coverage.py`（7 个用例），把这个不变量钉住：
   - **正方向**：用 ast 解析 `MRRC` 与每个 `_APP_MODULES` 文件的 import，
     凡是仓库根下的本地模块，必须在 `_APP_MODULES ∪ hiddenimports` 里；
   - **反方向**：`_APP_MODULES` 里每个名字都必须有对应的 `.py`（登记了不存在的名字
     会静默少发一个模块）；
   - 钉住 `antenna_sweep` 与 Cloud Hub 三件套（`cloud_hub`/`session_metrics`/`base_path`）；
   - 断言 spec 真的把 `_APP_MODULES` 从 PYZ 里过滤掉（否则热修覆盖层失效）；
   - 断言 `MRRC_users.db` 不再被打包（RC-005 的回归守卫）。
   - 变异验证：把 `antenna_sweep` 从 `_APP_MODULES` 删掉 ⇒ 2 个用例变红且报错点名
     `antenna_sweep <- MRRC`；还原后 `cmp` 一致、7 个用例全绿。

## 顺带查出的一个潜伏陷阱（本次未触发）

`tci_client.py:10` 是**模块级** `import websockets`，`tci_client` 在 `_APP_MODULES` 里
（因此也是 hiddenimport），但：

- `websockets` **不在** `requirements.txt` / `requirements-build.txt`，构建 VM 的 venv 里没有它
  ⇒ Analysis 找不到，静默跳过，实测 `websockets` 不在 PYZ 的 486 个模块里；
- 而全仓**没有任何代码 import `tci_client`**（`grep -rn tci_client` 只命中 spec 那一行），
  所以那个松散文件发出去了却永远不会被加载 ⇒ **当前无害**。

风险在于：哪天有人把 TCI 客户端接上，就会得到与本次一模一样的
`ModuleNotFoundError: No module named 'websockets'`，而构建照样全绿。
处置建议（择一，别放着不管）：把 `websockets` 加进 `requirements-build.txt`，
或者干脆把未接线的 `tci_client` 从 `_APP_MODULES` 移除。

## 验证方法

```bash
# 1) 静态守卫（本地即可，秒级）
python3 tests/test_frozen_module_coverage.py            # 期望 7 个用例全绿

# 2) 产物侧：松散 .py 数量与 _APP_MODULES 一致，且 antenna_sweep.py 在包里
#    （VM 上跑 C:\tools\pyzcheck.py）
#    期望：21 loose .py；antenna_sweep.py True；statistics in PYZ True

# 3) 真跑（唯一能证明"包能用"的一层）
#    隔离配置 + 空闲端口 + 用**包内**的 ssl_bootstrap 签证书 + 用**包内**的模板生成配置，
#    然后 HTTPS 打 /login、/api/cloud/state
#    期望：服务起来、/login 200、未登录 /api/cloud/state 401、登录后 200 且
#          frpc_available == true（证明 {app}\fleet\frpc.exe 被发现）
```

回归判据：第 3 步不再出现 `Failed to execute script 'frozen_entry'`，
且 `frpc_available` 为 `true` —— 后者同时证明本次发版的头号能力（内置 frpc）成立。

## 经验教训

1. **"构建成功"与"包能用"之间隔着一整个第 4 层。** 本次 1/2/3 层 33+ 项检查全绿，
   包仍然一启动就死。任何"只验产物形状"的清单都不能替代真跑。
2. **用 runpy/importlib 动态加载代码的项目，静态打包器是瞎的。** 这类架构必须有一份
   "所有动态加载模块都要显式登记"的守卫，而且是**双向**的（登记的都存在 / 存在的都被登记）。
   本仓已经因同一族原因栽过两次（`upgrade_core`、`antenna_sweep`）。
3. **补一个松散模块时，要连带确认它的依赖在 PYZ 里。** 松散模块运行时才加载，
   它的 import 不参与 Analysis；一个只有它自己在用的 stdlib/第三方模块很可能没被收进去。
4. **验证脚本自身也会撒谎。** 本轮两次命中：
   - 第一版符号走查照搬 mrrc_modern 的配方去 `extract('server')`，而本仓入口叫
     `frozen_entry` ⇒ `KeyError`，而外层脚本仍打印 `FAILURES: 0`（Python 崩溃没有计入
     `$fail`）。**检查器崩了必须算失败。**
   - 洁净室脚本用 `text=True` 读子进程输出，Windows 按控制台 GBK 解码冻结服务端的 UTF-8
     输出 ⇒ 满屏 `\ufffd`；打印时又因 GBK 编不出 `\ufffd` 抛 `UnicodeEncodeError`，
     **把唯一有价值的报错信息吞掉了**。改成按字节读 + 显式 UTF-8 解码 + stdout
     `reconfigure(errors="replace")` 才看到真正的 `ModuleNotFoundError`。
5. **符号走查的配方要按仓库架构改写，不能跨仓照搬。** modern 的入口是冻进 PYZ 的
   `server.py`（所以走 `CArchiveReader`+`marshal` 看 `co_names` 有意义）；本仓入口是
   runpy 加载的松散文件，正确做法是直接读 `_internal/app/` 下的文件内容。

## 出处

- 发现：V6.2.0 构建后的洁净室真跑（`C:\tools\cleanroom620.py`，日志 `C:\tmp\clean620b.log`）
- 取证：`C:\tools\pyzcheck.py` → `C:\tmp\pyz620.log`（PYZ 486 个模块的实测清单）
- 相关代码：`packaging/pyinstaller/frozen_entry.py`、`packaging/pyinstaller/mrrc_server.spec`
  的 `_APP_MODULES`/`hiddenimports`/`PYZ(...)` 过滤、`MRRC:2673-2675`、
  `antenna_sweep.py`、`tci_client.py:10`
- 引入提交：`b61553f feat(antenna): 天线 SWR 扫频基础设施（bypass 画像）`

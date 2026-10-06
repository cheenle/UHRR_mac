# RC-005 · 明文口令文件 `MRRC_users.db` 被打进公开可下载的安装包

> - 发现日期：2026-10-06（V6.2.0 发版前体检，在源码包内容核对这一步发现）
> - 影响版本：**V6.2.0 之前的打包链路一直如此**（`mrrc_server.spec` 建立时就有这条 datas）；
>   V6.2.0 已修（不再打包）
> - 影响面：**凭据泄露 → 认证绕过 → 发射安全**
> - 状态：✅ 打包链路已修（V6.2.0）；⚠️ **口令本身仍需轮换**（见下"未完成的动作"）
> - 关联：[RC-004](RC-004-shared-cookie-secret.md)（同为认证面缺陷，根因不同）

## 现象

`MRRC_users.db` **不是数据库**，是明文口令文件，每行一条 `username password`：

```
#one line per account like:
#username password
BG1SB abcd1234
admin uhrh2024
```

它被 `packaging/pyinstaller/mrrc_server.spec` 的 `datas` 打进 `_internal/`，
而安装包在 `https://www.vlsc.net/mrrc/downloads/MRRC-Setup.exe` **公开可下载**
⇒ 任何人解包即可拿到这两个口令。

## 根因链

1. `mrrc_server.spec` 的 datas 里有 `(str(ROOT / "MRRC_users.db"), ".")` —— 与
   `www/`、`memory_channels.json`、`MRRC.conf.template` 并列，看起来像"随包资源"，
   实际是**构建机当前那份真实口令**。
2. `dev_tools/release_windows.sh` 打源码包时还把它列进 `extra` 显式带上
   （因为它被 `.gitignore` 忽略、`git ls-files` 收不到）—— 于是它既上了构建机，又进了包。
3. 文件名叫 `.db`，容易被当成"空的种子数据库"；`sqlite3` 打开会报
   `file is not a database`（实测），因为它是纯文本。名字掩盖了内容。
4. **本机 live 实例用的正是这一份**：`MRRC.radio1.conf` 写
   `auth = FILE` + `db_users_file = MRRC_users.db`（相对路径），
   而该实例进程的 CWD 实测是仓库根（`lsof -a -p <pid> -d cwd`）⇒ 解析到的就是它。
   该实例公网可达（`https://bg6lh-legacy.mrrc.vlsc.net/`，hub 注册表端口 18802）。

合起来：**公开安装包里的口令 = 一个能按键发射的公网实例的登录口令。**

## 为什么"从包里去掉"是安全的（逐条验证，不是推断）

| 运行路径 | 是否依赖包里 `_internal/MRRC_users.db` | 证据 |
| --- | --- | --- |
| Windows 新装 | ❌ | `launcher.py:ensure_config()` 把 `db_users_file` 写成**用户数据目录的绝对路径**；`ensure_users()` 在文件缺失时自己生成随机口令 |
| 相对路径配置 | ❌ | `config_io.read_text()` 只是 `open(path, "rb")`，按 **CWD** 解析，**不做** `_resource_dir()` 解析 ⇒ 永远落不到 `_internal/` |
| Docker | ❌ | `docker-compose.yml:32` 显式挂载 `./MRRC_users.db:/uhrh/MRRC_users.db` |
| 源码运行 | ❌ | 同上，相对路径按 CWD 落到仓库根 |
| 测试 | ❌ | `tests/test_support_bundle.py:42` 只把文件名当作脱敏用例的字符串 |

结论：包里那份**在运行时根本够不到**，纯属净损失 —— 只贡献了一次凭据泄露。

## 修复（V6.2.0）

1. `mrrc_server.spec`：删掉 `(str(ROOT / "MRRC_users.db"), ".")`，原地留注释说明为什么不打。
2. `dev_tools/release_windows.sh`：从源码包的 `extra` 列表里移除 `MRRC_users.db` ——
   **构建机也不该收到它**（留着就是一份可被顺手带走的凭据；本次 VM 体检时也确实发现
   构建机上残留着 `certs/`，里面有一份真私钥，已删）。
3. 验收（重打源码包后逐项数，不看"成功"字样）：
   `MRRC_users.db` 条数 **0**、`frpc.exe` **1**、`certs/` **0**、`MRRC.conf.template` **1**
   （模板仍需在包里，launcher 首启要用）；文件数 816 → **815**。

## 未完成的动作（需要运维执行）

- ⚠️ **轮换 `BG1SB` / `admin` 的口令**。修打包链路只能保证**以后**不再泄露；
  这两个口令已经随包分发过一段时间，必须当作已泄露处理。
  改法：编辑 live 实例配置里 `db_users_file` 指向的那个文件，换掉口令后重启实例。
- 建议把该文件改名（例如 `MRRC_users.txt`）或在文件头加一行醒目注释：
  `.db` 这个后缀会让人误以为它是二进制库、可以随手打包。
- 建议给 `dev_tools/release_windows.sh` 的源码包加一条**正向**守卫：
  解包后断言"不含任何口令/私钥形状的文件"，而不是只依赖排除清单
  （排除清单是黑名单，黑名单会漏；本次就是 `extra` 白名单里混进来的）。

## 验证方法

```bash
# 1) 源码包/安装包里不该有它
unzip -l dist/mrrc_build_src.zip | grep -c MRRC_users.db        # 期望 0
# 2) 装完的机器上，_internal 里也不该有
dir "%LOCALAPPDATA%\Programs\MRRC\_internal\MRRC_users.db"       # 期望 找不到
# 3) 新装仍能登录（launcher 自己生成口令，不受影响）
type "%LOCALAPPDATA%\MRRC\MRRC Quick Start.txt"                  # 期望 有 Username / Password
# 4) live 实例改口令后仍能用新口令登录、旧口令被拒
```

回归判据：第 1、2 项为 0/找不到，且第 3 项仍能拿到一组可用口令 ——
即"不再泄露"与"没把用户锁在门外"同时成立。

## 经验教训

1. **"随包资源"清单要按内容审，不是按文件名审。** `.db` 看起来像种子数据，
   实际是明文口令；`sqlite3` 打不开它正是线索（`file is not a database`）。
2. **排除清单是黑名单，黑名单会漏。** `release_src_excludes.json` 挡住了 `certs/`，
   却挡不住 `extra` 白名单里被**显式**加进来的那一份。真正可靠的守卫是
   "解包后正向断言不含凭据形状的文件"。
3. **发版体检要核对产物内容，不能只看构建退出码。** 这一条是在
   "解包源码包、逐项数内容"那一步发现的 —— 如果只跑构建，它会一路绿灯地把口令发出去。
4. **构建机上不该留任何凭据。** 本次 VM 体检同时发现残留的 `certs/`（含一份真私钥，
   来自 `certs/` 被加进排除清单之前的构建）。`Expand-Archive` 只覆盖不删除，
   所以历史残留会一直在 —— 每次构建前要主动清。
5. **与 RC-004 同属一个模式：认证面的假设没被重新审视过。**
   RC-004 是"签名密钥人人相同"，本条是"口令随包分发"。两者都要求"知道一个公开值
   就能登录一个能发射的实例"。发布一个把实例挂到公网的功能（内网穿透）时，
   整条认证链都该重走一遍。

## 出处

- 发现：V6.2.0 发版前对 `dist/mrrc_build_src.zip` 做内容核对时
- 相关代码：`packaging/pyinstaller/mrrc_server.spec` 的 `datas`、
  `dev_tools/release_windows.sh` 的 `extra`、`MRRC:5478`（读 users 文件）、
  `config_io.read_text`、`windows/launcher.py` 的 `ensure_config` / `ensure_users` /
  `_seed_candidates`、`docker-compose.yml:32`
- live 实例取证：`MRRC.radio1.conf` 的 `auth`/`db_users_file`，
  `lsof -a -p <pid> -d cwd` 确认相对路径的解析基准

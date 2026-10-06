# RC-004 · 全部装机共用同一个 `cookie_secret`：会话 cookie 可被伪造

> - 发现日期：2026-10-06（V6.2.0 发版前体检）
> - 影响版本：**V6.2.0 及之前全部版本**（既有问题，非本版引入）
> - 影响面：**认证绕过 → 发射安全**（可远程键控电台）
> - 状态：⚠️ **未修复 —— 已知风险，2026-10-06 由维护者决定先发 V6.2.0**
> - 关联：`AGENTS.md`「Cloud Hub 接入」、`SDD/15-ptt-safety-architecture.md`、
>   `docs/current/design/hub-parity-plan.md`

## 现象

不存在"故障现象"——这是一个**静默的、一直成立**的认证缺陷：任何知道 `cookie_secret`
的人，可以为任意用户名签出一个 Tornado 安全 cookie，从而**不经口令**获得已登录会话。
而本应用的已登录会话可以按下发射键（PTT）。

## 根因链

1. **同一个密钥值被写进 7 个文件**，包括随安装包分发的那份模板：

   ```
   windows/MRRC.conf.template      ← 会进安装包
   MRRC.conf  MRRC.radio1.conf  MRRC.radio2.conf  MRRC.radio3.conf
   MRRC.9000.conf  MRRC.jrc
   ```

   七处的值完全相同：`cookie_secret = L8LwECiNRxq2N0N2eGxx9MZlrpmuMEimlydNX/vt1LM=`

2. **它随安装包发到公网**。`packaging/windows/build.ps1:91`
   `Copy-Item (Join-Path $RepoRoot "windows") $AppRoot -Recurse -Force`，
   而 `packaging/windows/MRRC.iss` 打包 `dist\windows\MRRC\*`
   ⇒ 装机后位于 `{app}\windows\MRRC.conf.template`。
   安装包本身在 `https://www.vlsc.net/mrrc/downloads/MRRC-Setup.exe` **任何人可下载**，
   所以这个密钥等同于公开——与仓库是否公开无关。

3. **首启逐字节复制模板，不做任何随机化**。
   `windows/launcher.py` 的 `_copy_seed()`：

   ```python
   def _copy_seed(target: Path, source: Path) -> None:
       if target.exists():
           return
       if source.exists():
           target.write_bytes(source.read_bytes())   # ← 原样复制，密钥照抄
   ```

   `default_config_path()` 返回的正是 `app_dir()/"windows"/"MRRC.conf.template"`，
   `config_path()` 返回 `user_data_dir()/"MRRC.conf"`。

4. **服务端直接使用，无兜底、无生成**。`MRRC:6157` 把配置值原样交给 Tornado：

   ```python
   Application(handlers=[...], debug=..., websocket_ping_interval=30,
               cookie_secret=config['SERVER']['cookie_secret'])
   ```

5. **会话 cookie 就是全部的登录判定**。`MRRC:5464` 登录成功时
   `set_secure_cookie("user", self.get_argument("name"), path=_base_path.cookie_path(BASE_PATH))`；
   而 `get_current_user`（`MRRC:603 / 618 / 676`）只有一句
   `return self.get_secure_cookie("user")`。

   Tornado 的安全 cookie 是用 `cookie_secret` 做 HMAC 签名的、**内容不加密**。
   cookie 里装的就是用户名字符串 ⇒ 知道密钥即可自行构造合法签名。

## 为什么 V6.2.0 让它变严重

V6.2.0 之前，多数装机只在**局域网**可达（或用户自己做了端口映射），攻击者需要先进到同一个
内网。V6.2.0 引入内网穿透（Cloud Hub）后，实例会挂在
`https://<呼号>-legacy.mrrc.vlsc.net/`（**443，公网可达，Let's Encrypt 真证书**），
认证仍走 `auth = FILE` 的会话 cookie（hub 侧不带 URL 令牌）。

于是"一把公开的签名密钥 + 一个公网入口"同时成立：**任何人的电台都可能被陌生人键控**。
这不是本版引入的缺陷，但本版改变了它的可利用性 —— 这也是它必须在 V6.2.0 的记录里留痕的原因。

## 修复方案（尚未实施）

要点是**每台装机一把随机密钥**，且**不能重写整个配置文件**
（`AGENTS.md` 明确警告：configparser 重写会丢注释）。

1. 新增一个纯逻辑函数（放进 `_APP_MODULES` 里的可热修模块，例如 `config_io.py`）：
   `ensure_unique_cookie_secret(path)` ——
   - 以**文本**方式读文件，只在 `cookie_secret` 等于上面那个**已公开的默认值**
     （或缺失/为空）时，用 `secrets.token_bytes(32)` + base64 生成新值；
   - **只正则替换那一行**，其余字节原样保留（保住注释与排版）；
   - 原子写（临时文件 + `os.replace`），失败不破坏原文件。
2. 两处调用：`windows/launcher.py` 启动服务端之前，以及 `MRRC` 启动时对自己的配置路径
   —— 后者覆盖源码运行与 Docker 两条路径。
3. **老装机同样要轮换**：`_copy_seed()` 对已存在的目标直接 `return`，所以只在"播种"环节
   修不够；必须在启动路径上检测"仍是公开默认值"并轮换。代价是用户被登出一次（可接受）。
4. 轮换后把仓库里 6 份配置与模板的默认值换成**占位符**（例如空值或 `CHANGE_ME`），
   并让"检测到占位符"也走生成逻辑 —— 否则模板里那把密钥会继续被复制出去。
5. 守卫测试：默认值/占位符/缺失三种输入都要生成随机值；已是随机值时**不得**改动
   （幂等，否则每次启动都把用户登出）；替换后其余行逐字节不变（守住"不丢注释"）。

> 注意：`MRRC` 与 `windows/launcher.py` 都在 PYZ 里，**热修通道覆盖不到** ⇒
> 这个修复只能随安装包到达用户，不能靠热修下发。这正是它无法"先发版再热修"的原因。

## 验证方法

判断一台机器是否仍在使用公开默认值（不依赖推断，直接读它实际加载的配置）：

```bash
# Windows 装机（实际生效的配置在用户数据目录，不是安装目录）
grep -n "cookie_secret" "%LOCALAPPDATA%\MRRC\MRRC.conf"
# 源码运行 / Docker
grep -n "cookie_secret" MRRC.conf          # 或 MRRC.<实例名>.conf
```

命中 `L8LwECiNRxq2N0N2eGxx9MZlrpmuMEimlydNX/vt1LM=` 即为**仍暴露**。

验证伪造是否真的成立（只在**自己**的实例上做）：用该密钥按 Tornado 的
`create_signed_value` 格式签一个 `user=<你的用户名>` 的 cookie，带上它请求需要登录的页面，
若不再被重定向到 `/login` 即成立。修复后同样操作应当被重定向回 `/login`。

修复上线后的回归判据：

- 两台不同装机的 `cookie_secret` **不相同**；
- 同一台机器重启多次，`cookie_secret` **不变**（幂等，不会每次启动都登出用户）；
- 配置文件除该行外**逐字节不变**（注释仍在）。

## 安全影响

| 维度 | 说明 |
| --- | --- |
| 机密性 | 可读取该实例的 Web 界面全部内容（频率、日志、录音列表、诊断包） |
| 完整性 | 可改配置、改频率、改天调参数 |
| **发射安全** | **可键控发射（PTT）** —— 本应用的最高风险面，参见 RC-001 与 `SDD/15` |
| 前置条件 | 只需能访问该实例的 Web 端口；V6.2.0 起公网入口默认可达 |
| 缓解（未修复期间的临时手段） | 不申请/不启用 Cloud Hub 入口；或在 hub 侧不开放该实例；<br>或手工把本机 `MRRC.conf` 的 `cookie_secret` 换成随机值并重启（轮换会让已登录会话失效一次） |

## 经验教训

1. **"随包模板"里的任何凭据都等于公开发布。** 安装包在公网上可下载，
   模板文件会原样进到每台机器 —— 判断一个值是否秘密，要看它**最终去了哪**，
   不是看它在不在 `.gitignore` 里。
2. **发版体检要扫"会进产物的跟踪文件"，不只是扫 `.env`/`certs/`。**
   本次是用 `git ls-files`（正是源码包的取材口径）配合密钥形状正则扫出来的；
   只盯着常见的密钥文件名会漏掉它。
3. **新功能会改变既有缺陷的可利用性。** 这个密钥问题在 V6.1.18 就成立，但那时只是局域网风险；
   内网穿透把它抬成公网风险。**发布一个"扩大暴露面"的功能时，必须重新审视既有的认证假设**，
   即使相关代码一行没改。
4. **认证判定只有一句 `get_secure_cookie("user")` 时，签名密钥就是唯一的门。**
   而 `AGENTS.md` 已经写过同类判断（"绑所有接口时 Web 口令是唯一一道门，而这个应用能按下发射键"）——
   那句话的前提是口令**不可绕过**；密钥公开时它被绕过了。

## 出处

- 发现过程：V6.2.0 发版前体检（`git ls-files` × 密钥形状正则）
- 相关代码：`MRRC:6157`（Application 的 cookie_secret）、`MRRC:5464`（签发）、
  `MRRC:603/618/676`（`get_current_user`）、`windows/launcher.py` 的
  `_copy_seed` / `config_path` / `default_config_path`、
  `packaging/windows/build.ps1:91`、`packaging/windows/MRRC.iss` 的 `[Files]`
- 决定记录：2026-10-06，维护者在"先修再发 / 先发再修 / 先发并记录"三个选项中选择
  **先发 V6.2.0 并记录风险**（"发后再热修"不成立：相关代码在 PYZ 里，热修覆盖不到）

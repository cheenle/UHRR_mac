# RC-007 · 冻结包把可写状态（频道记忆）写进**安装目录**

> - 发现日期：2026-10-06（V6.2.0 洁净室真跑，四层验证第 4 层）
> - 影响版本：**V6.2.0 及之前全部安装版**（既有缺陷，非本版引入 —— 同一行在
>   6.1.18 时代的 `456ce20:347` 就存在，引入于 `917461c`）
> - 影响面：功能可用性（频道记忆无法持久化）；**不崩溃**（写入有 try/except 兜底）
> - 状态：⚠️ **本版未修**（改动会影响既有用户的频道文件位置，属产品决策，见下"为什么没顺手修"）
> - 关联：[RC-006](RC-006-unregistered-loose-module.md)（同一次洁净室跑出来的）

## 现象

洁净室真跑打出来的 exe，跑完后**安装目录里多了一个文件**：

```
install dir gained no UNEXPECTED files   XX  ['C:\\mrrc\\dist\\windows\\MRRC\\memory_channels.json']
```

## 根因

`MRRC:359`：

```python
MEMORY_CHANNELS_FILE = os.environ.get("MRRC_MEMORY_CHANNELS_FILE") \
    or os.path.join(_runtime_dir(), 'memory_channels.json')
```

而 `_runtime_dir()`（`MRRC:184-188`）在冻结包里是：

```python
if getattr(sys, "frozen", False):
    return os.path.dirname(os.path.abspath(sys.executable))   # = 安装目录 {app}
```

⇒ 频道记忆被写到 `{app}\memory_channels.json`，也就是**自己的代码目录**。
装在 `C:\Program Files\` 下时那里普通用户不可写。

注意 spec 另外把仓库根的 `memory_channels.json` 作为 datas 打进了 `_internal/`，
而代码写的是**应用根目录** —— 两个位置，所以读到的和写回的甚至不是同一个文件。

## 为什么它没变成崩溃

写入路径有兜底（`MRRC:381-386`）：

```python
try:
    config_io.write_text(MEMORY_CHANNELS_FILE, json.dumps(user_memory_channels, indent=2))
except Exception as e:
    logger.warning(f"保存频道记忆文件失败: {e}")
```

所以在受保护的安装目录下表现为：**保存静默失败、只留一条 warning**，
用户看到的是"存的频道重启就没了"。这也是它长期没被发现的原因 —— 没有报错弹窗，
只有日志里一行警告。

## 正确的落点

配置目录，与 Cloud Hub 的状态文件同一个地方：`_cloud_dir()` =
`os.path.dirname(os.path.abspath(config_file))`，Windows 安装版即
`%LOCALAPPDATA%\MRRC\`。本次洁净室已实测该目录是可写的，且
`mrrc_cloud.json`、`certs/`、`MRRC.log`、`MRRC.conf` 都正确落在那里，
**没有一个写进 bundle**。频道记忆是这条纪律唯一的例外。

> 对照：`mrrc_modern` v1.24.6 犯过同一类错（冻结包把 `recordings/` 建在**签名 bundle 内部**，
> macOS 上写一个文件就报 `a sealed resource is missing or invalid`）。
> 判据是一样的：**冻结包的可写状态一律放用户数据目录，绝不放代码目录。**

## 为什么没顺手修

改 `MEMORY_CHANNELS_FILE` 的落点会改变既有用户的数据位置：已经能写成功的安装
（例如装在用户可写目录、或用 `MRRC_MEMORY_CHANNELS_FILE` 指过路径的）会"丢失"
已存频道 —— 文件还在旧位置，程序却去新位置找。要修就得连**迁移**一起做
（启动时若新位置不存在而旧位置存在，则搬过去），这不是发版当口该塞进去的改动。

处置：记录在案，作为独立小改单独做（含迁移与守卫测试）。
临时规避：设 `MRRC_MEMORY_CHANNELS_FILE` 指向用户可写目录。

## 验证方法

洁净室判据（本次实测脚本 `C:\tools\cleanroom620.py`）：跑打包出的 exe 前后各做一次
安装目录快照（文件名 + 大小 + mtime），比对新增/变更：

```
期望：install dir gained no UNEXPECTED files  OK
      no mrrc_cloud.json / MRRC.log / MRRC.conf written into the bundle  OK
      可写状态都出现在配置目录（%LOCALAPPDATA%\MRRC\）
现状：多出 memory_channels.json ⇒ 本条
```

修好后的回归判据：跑一轮"存一个频道 → 重启 → 读回来"，且安装目录快照**零新增**，
同时旧位置的既有文件被迁移到新位置（不是被忽略）。

## 经验教训

1. **"有 try/except 兜底"不等于"没问题"** —— 它把功能缺陷降级成了日志里的一行 warning，
   于是能躲过所有看退出码和看崩溃的验证。只有比对**文件系统副作用**才看得见。
2. **洁净室必须做"跑之前/跑之后"的目录快照比对**，而不是只看服务起没起来。
   本次正是这一项抓到的；前三层（时间戳/大小/哈希、结构核对、符号走查）都看不见它。
3. **`_runtime_dir()` 在冻结包里是安装目录**，这是本仓反复踩的一个点
   （RC-006 的 frpc 发现路径也依赖它）。凡是"要写"的路径都不该用它，
   要用 `_cloud_dir()`（配置目录）。

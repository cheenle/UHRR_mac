# 一键升级（Windows 安装版）

用户侧：移动端菜单 **⬆️ 软件更新** / 桌面工具栏 **⬆️** → 看到"有新版本"→ 点【立即升级】；
或直接在启动器窗口**输入 U 回车**。升级时弹一次 UAC（管理员确认），装完自动重启服务。

## 开关

| 配置 | 作用 |
|---|---|
| `[UPDATE] enabled = False` | 完全不检查（含热修） |
| `[UPDATE] autoDownload = False` | 只提示有新版，不后台预下载 |
| `MRRC_NO_UPDATE_CHECK=1` | 环境变量，覆盖一切（调试/离线可用） |

## 运行机制（排障必读）

1. **启动器启动时**拉 `https://www.vlsc.net/mrrc/downloads/latest.json`
   （读不到则回退 `patch.json`：行为与旧版一致，只做热修）；
2. 有新版本 → 后台线程下载到 `%LOCALAPPDATA%\MRRC\updates\MRRC-Setup-<ver>.exe`
   （先 `.part` → SHA256 → 原子改名；**校验失败只删 .part，绝不动现有安装**）；
3. 用户点【立即升级】/ 输 U → 服务端写哨兵 `updates\upgrade.request`
   （页面路径先做 PTT 门禁，发射中返回 423）→ 启动器接手：
   `ShellExecuteW runas` + `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /LOG=…`；
4. 安装完成后 `version.txt` 变化 → 启动器自动重启并拉起新版。

**状态文件**（都在 `%LOCALAPPDATA%\MRRC\updates\`）：

| 文件 | 内容 |
|---|---|
| `state.json` | `staged{version,sha256,path,size,at}` 与 `lastResult{status,version,detail,at}` |
| `upgrade.request` | 页面/按键写入的升级请求（启动器消费后立即删除） |
| `install-<ver>.log` | Inno Setup 安装日志（失败时看它） |

**`lastResult.status` 取值**：`ok` 成功；`uac_denied` 用户拒绝管理员确认；
`ptt_active` 发射中被拒；`sha_mismatch` 安装包校验失败；`download_failed` 下载失败；
`missing_staged` 还没下载完就触发；`install_failed` 安装器返回失败或版本没变。

## 回退到上一版

`latest.json` 的 `previous` 段指向站点上保留的旧安装包；页面【回退到上一版】按钮
写同样的哨兵，走同一条静默安装路径（同样一次 UAC）。站点上至少保留上一版：
发布流程会把"当前线上包"归档成 `MRRC-Setup-<上一版>.exe`。

## 发布清单（维护者）

```bash
./dev_tools/release_windows.sh          # 一条命令：构建→验收→取回→归档→生成 latest.json→部署→线上复核
```
关键约束：
- `latest.json` 的 `installer.sha256` 必须与 **`MRRC-Setup-<ver>.exe`** 一致（生成器自动取该文件）；
- 安装版本必须**大于**热修通道最新版本（否则启动器会反复重放旧补丁）；
- `minSupported` 决定多老的安装还能走热修；低于它的用户会被要求装完整包。

## 安全边界

只走 HTTPS + 清单内 SHA256 固定校验；**无代码签名**（需证书，列为后续硬化项）→
信任锚 = 站点 TLS；安装时的 UAC 是最后一道人工闸门；静默安装参数固定，不接受网络下发参数。

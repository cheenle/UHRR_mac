# 支持诊断包（「🐞 遇到问题」一键上传）

用户侧：移动端菜单 **🐞 遇到问题** 或桌面工具栏 **🐞** → 填问题描述 → 生成 → 上传/只保存本地。
维护者侧：`https://www.vlsc.net/mrrc/support/api/list`（Basic Auth，口令见下）。

## 维护者用法

| 项 | 值 |
|---|---|
| 列表页 | `https://www.vlsc.net/mrrc/support/api/list`（浏览器会弹出口令框） |
| 用户名 | `mrrc` |
| 口令 | 本机 `~/.mrrc-support-credentials.txt`（部署时生成，权限 600）；服务器上在 `/etc/mrrc-support.env`（0600 root） |
| 存储 | 服务器 `/var/www/support/<id>/`（`bundle.zip` + `meta.json`，**不在站点 docroot 内**） |
| 删除 | 列表页每行的「删除」按钮，或 `DELETE .../api/<id>/bundle`（需口令） |

看包顺序建议：`diagnostics/summary.txt`（自动体检结论 + 命中明细）→ `problem.txt` →
`diagnostics/env.json`（音频设备/主机 API/rigctld/ATR/热修）→ `logs/*`。

## 部署 / 更新接收端

```bash
./deploy_support_receiver.sh            # 幂等：装 server.py + systemd 单元 + 口令（0600）
```
- 服务：`systemd` 单元 `support-receiver`（`/opt/mrrc-support/server.py`，监听 127.0.0.1:8099，
  跑在 `www-data`，`ProtectSystem=full` + `ReadWritePaths=/var/www/support`）
- nginx：站点 `vlsc.net` 里 `location ^~ /mrrc/support/ { proxy_pass http://127.0.0.1:8099/; client_max_body_size 25m; }`
  （改动前已备份为 `vlsc.net.bak-<时间戳>`；改完必须 `nginx -t` 再 reload）
- 客户端默认上报地址：`https://www.vlsc.net/mrrc/support/api`（`[SUPPORT] url` 可覆盖）

## 包内容与脱敏（硬规则）

生成逻辑在 `support_bundle.py`（纯标准库、可热修）：

- **白名单**：配置只导出 `CONFIG_WHITELIST` 列出的键，其余节整节省略；
- **密钥替换**：`cookie_secret`/`password`/`token`/`api_key` 等一律写成 `<redacted>`，命中数写进 manifest；
- **永不打包**：`MRRC_users.db`、证书与私钥（`FORBIDDEN_SUBSTRINGS`）；
- **只读尾部**：日志按行边界截断到 ≤2 MB；
- 传输：只走 HTTPS + 接收端限速（每 IP 每分钟 ≤5 次 create）与单包上限（默认 20 MB）。

## 排障

| 现象 | 处理 |
|---|---|
| 列表页 502 | `ssh www.vlsc.net 'sudo systemctl status support-receiver'`；确认 8099 在听 |
| 上传 413 | 诊断包超过 20 MB：调 `SUPPORT_MAX_MB`（同时改 nginx `client_max_body_size`） |
| 上传 429 | 触发限速；等 1 分钟或调 `SUPPORT_RATE_PER_MINUTE` |
| 用户说"上传失败" | 包仍在本地 `%LOCALAPPDATA%\MRRC\support\`，让用户点「只保存到本地」把路径发你 |

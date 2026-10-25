# 老产品站点补处境页（设计）

日期：2026-10-25
上游：`2026-10-25-trunk-merge-and-site-recovery-design.md`（第 ② 节）
范围：只加站点页面与入口。产品行为不改，诊断包/升级/云接入的实现一律不动。

## 1. 问题

老站 33 个 html 里，"用户会卡住的地方"只有一半有答案：

| 处境 | 产品有这能力吗 | 依据 | 站上有答案吗 |
| --- | --- | --- | --- |
| 安装 | 有 | `docs/installation.html`、`MRRC-Setup.exe` | 有 |
| 升级 / 升不动 | 有 | `upgrade_core.py`、`windows/launcher.py`、`latest.json` + `patch.json` | **无**（只有 `lifecycle.html` 一段表格） |
| 出问题拿诊断包 | 有 | `www/support.html`（🐞）、`support_bundle.py` | **无** |
| 把电台放到公网 | 有 | `www/cloud.html`（☁️）、`cloud_hub.py`、`/api/cloud/*` | **无** |
| 盒子（刷机/DNS/远程协助） | 无 | 那是 mrrc_modern + W103D | 不写 |

## 2. 决定

按 mrrc_modern 的处境分类逐条比对，**有的才写**。三页 + 六个文件（中英各一）：

| 路径 | 标题 | 一句话 |
| --- | --- | --- |
| `docs/upgrade.html` | 升级与热修 | 点一下升到最新；升不动时先看哪个判据 |
| `docs/diagnose.html` | 出问题先拿诊断包 | 三步把证据交给维护者，包里有什么、绝不含什么 |
| `docs/cloud.html` | 把电台接到公网 | 不用公网 IP、不用开端口；呼号即入口 |
| `zh/docs/upgrade.html` | 同上（中文） | |
| `zh/docs/diagnose.html` | 同上 | |
| `zh/docs/cloud.html` | 同上 | |

拆成三页而不是一页合集：三个受众不同（所有人 / 出了事的人 / 想把电台放上网的人），
一页三件事在手机上一屏看不到头。

**不写的**：远程协助（`cloud_hub.py` 还没有 `help_*`，属第 ④ 节）、W103D 盒子六页、
DNS 修复（那是盒子的 systemd-resolved 问题）。写没有的能力等于制造下一次误导。

## 3. 内容的事实来源

每页只写代码里查得到的：

- **升级**：`docs/current/operations/one-click-upgrade.md`（入口、`state.json.lastResult`
  的八种取值、10 个真机坑、PTT 门禁 423、拒绝降级与 `minSupported`、热修先于升级检查）；
- **诊断包**：`www/support.html` 的交互顺序 + `support_bundle.py` 的白名单/脱敏与
  "用户库、证书私钥、令牌永不打包"；
- **云端**：`www/cloud.html` 的对话框序列 + `cloud_hub.py`（`PORTAL_DEFAULT`、
  `product=legacy` → 标签 `<呼号>-legacy`、30 s 自查、frpc pin 0.71.0、证书换了要重启应用）。

页面里出现的版本号一律写"V6.1.0 起"这类**能力引入版本**，不写"当前版本"——
当前版本由 `release_check.py` 管，散落在正文里必然漂移。

## 4. 入口（否则三页是孤岛）

1. `docs/docs.html` / `zh/docs/docs.html` 的「产品支持」表：每行连到对应页面，并补一行「接入云端」；
2. `docs/lifecycle.html` / `zh/docs/lifecycle.html` 的 Entry points 列表加三条；
3. `answers/index.html` 顶部加一行"不知道该看哪页？"，三个链接；
4. 三个新页自身的导航沿用 `docs/lifecycle.html` 的 navbar 与 footer（不改全站 33 个页面的导航）。

## 5. 验收

| 判据 | 命令 |
| --- | --- |
| 链接与样式无漂移 | `python3 dev_tools/site_audit.py` |
| 内联 JS 语法 | `python3 tests/test_web_inline_js.py` |
| 版本锚点未破坏 | `python3 dev_tools/release_check.py` |
| 中英成对 | 六个文件都存在且互相 `lang-btn` 可达 |
| 线上 | 部署后 `curl -o /dev/null -w '%{http_code}'` 六个 URL 全 200 |

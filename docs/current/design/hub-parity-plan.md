# MRRC 接入 Cloud Hub：改造计划（2026-09-30 侦察）

目标：让 `mrrc`（本仓产品，Tornado，默认端口 8877）具备与 `mrrc_modern` 同等的
"可被云端入口接入"能力。**标签规则**采用主产品裸呼号、附加产品加产品后缀
（本仓若上线即 `bg1sb-legacy` 形式）；规则与理由见 `mrrc_hub/SDD/07-subject-area-model.md` §7.x.1。

## 现状结论

- **子域根路径入口**（`https://<标签>.mrrc.vlsc.net:8899/`）：本仓**开箱即用**，无需改造
- **路径反代入口**（`https://www.vlsc.net/<产品段>/<呼号>/`）：需做前缀改造，本文件即该项
- 令牌不进 URL：**天然满足**（`auth = FILE`，会话机制，无 URL 令牌）
- PTT 半开释放、会话遥测：**缺失**，见下"未完成"两节

## 前缀改造：逃逸点实测清单

| # | 位置 | 实测 | 处理 |
|---|------|------|------|
| 1 | 路由注册表 | `MRRC:71` 起的 `handlers=[...]`（含 `/login` `/logout` `/CONFIG` `/mobile` `/test` `/api/mem_channels` `/api/recordings` `/WSaudioRX` `/WSaudioTX` `/WSCTRX` `/WSpanFFT` `/WSATR1000` `/WSATU` `/(panfft.*)` 等） | 引入 `base_path` 配置，注册时统一前缀（空值 = 现状） |
| 2 | HTML 绝对路径 | **5 个文件 / 8 处**（如 `www/index.html` 的 `href="/wdsp_settings.html"`、`/panfft.html`） | 改相对路径 |
| 3 | JS 绝对调用 | `fetch('/api/devices')` ×2、`fetch('/api/devices/apply')` ×1 | 改相对或经 `base_url()` |
| 4 | 登录跳转 | `MRRC:474` `549`（`/login?next=` + quote(request.uri)）、`MRRC:4241` `4430`（`redirect("/login")`）、`MRRC:4450` 内联 `window.location.href='https...'` | 目标前缀化；`next` 回跳要能处理带前缀的 uri（**这是 mrrc_modern 踩过的同一个坑**） |
| 5 | service worker | `www/sw.js` 存在 | 依 mrrc_modern 的断言规则：**文档资源用相对、预缓存清单保持绝对** |
| 6 | X-Forwarded-For | `MRRC.conf` 无概念 | 信任反代来源后按 XFF 取客户端 IP（否则限流退化为全局桶，同 §12.8 已知退化） |

## 守卫测试（照 mrrc_modern 的形状）

新增 `tests/`（或用 `dev_tools/`，本仓无统一 pytest 入口）：
断言"任何 HTML/JS 里不得出现指向站点根的绝对路径"（`sw.js` 预缓存清单除外）、
"路由表在 `base_path` 非空时全部带前缀"、"登录跳转与 `next` 往返保持前缀"。

## 未完成（第二、三块）

1. **PTT 活性闸门（P0-1 类）**：TX 路径在本仓是另一套代码（`hamlib_wrapper.py` / `audio_interface.py` /
   `atu_auto_tuner.py`），mrrc_modern 的实现不能复用。需：客户端心跳 → 服务端超时即释放 PTT，
   与既有 `MAX_TX` 类时长上限构成两条独立防线；默认关闭，Hub 模式建议 3–5 秒
2. **会话遥测**：需新增等价于 mrrc_modern `session_metrics.py` + `/api/session_metrics` 的聚合与周期日志，
   供 Hub 侧容量决策（AD-H12 的扇出触发器）

## 上线步骤（代码就绪后）

1. hub：`instances.tsv` 加一行（如 `bg1sb-legacy 18803`）→ 重跑 `gen_hub_routes.py` → reload nginx
2. 实例侧：`install_instance_tunnel.sh bg1sb-legacy 18803`（frpc localPort 8877）
3. 验证：`https://bg1sb-legacy.mrrc.vlsc.net:8899/` → 期望 401/登录页（真证书，零警告）
4. 路径入口（可选）：hub 与 www 的 nginx 增加对应产品段

**注意**：本仓需要电台/音频/串口设备；在已运行 mrrc_modern 的同一台机器上不要并行启动，
以免争抢设备。上线验证应在有独立硬件或用户明确同意停用主产品的窗口内进行。

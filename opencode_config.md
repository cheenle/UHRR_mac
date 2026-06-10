# OpenCode 配置分析

## 发现过程

### 第1问：opencode 配置在哪？

**结论：没有 `opencode.json` 或 `opencode.jsonc` 配置文件。**

检查了项目根目录、`~/.config/opencode/`、`~/.opencode/`，均无配置文件。opencode 使用内置默认值运行。

仅有：
- `.opencode/package.json` — 声明 `@opencode-ai/plugin` v1.14.51
- `.opencode/summary.md` — 会话进度记录
- `AGENTS.md` — 项目级指令文件

### 第2问：模型从哪来？

查看运行中的进程：

```
ps aux | grep opencode
```

发现：
```
/Users/cheenle/.mulerun/vendor/opencode/node_modules/opencode-darwin-arm64/bin/opencode --model openai/gpt-5.5
```

模型通过 `--model` 启动参数传入。但同时也发现 system prompt 里写的是 `opencode/deepseek-v4-flash-free`，存在不一致。

### 第3问：可用模型列表从哪来？

检查环境变量发现所有配置通过 `OPENCODE_CONFIG_CONTENT` 注入：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "autoupdate": false,
  "share": "disabled",
  "small_model": "openai/gpt-5.4-mini",
  "provider": {
    "openai": {
      "options": {
        "apiKey": "muk-35cb24adac98ccb7f6f7ab2f09f6f21578c7be6ab9aabdb8bc5f018208e14c90",
        "baseURL": "https://api.mulerun.com/v1"
      }
    },
    "google": {
      "options": {
        "apiKey": "muk-35cb24adac98ccb7f6f7ab2f09f6f21578c7be6ab9aabdb8bc5f018208e14c90",
        "baseURL": "https://api.mulerun.com/vendors/google/v1beta"
      }
    },
    "alibaba": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "apiKey": "muk-35cb24adac98ccb7f6f7ab2f09f6f21578c7be6ab9aabdb8bc5f018208e14c90",
        "baseURL": "https://api.mulerun.com/v1"
      }
    },
    "moonshot": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "apiKey": "muk-35cb24adac98ccb7f6f7ab2f09f6f21578c7be6ab9aabdb8bc5f018208e14c90",
        "baseURL": "https://api.mulerun.com/v1"
      }
    },
    "xai": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "apiKey": "muk-35cb24adac98ccb7f6f7ab2f09f6f21578c7be6ab9aabdb8bc5f018208e14c90",
        "baseURL": "https://api.mulerun.com/v1"
      }
    },
    "zhipu": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "apiKey": "muk-35cb24adac98ccb7f6f7ab2f09f6f21578c7be6ab9aabdb8bc5f018208e14c90",
        "baseURL": "https://api.mulerun.com/v1"
      }
    }
  }
}
```

所有 provider 指向 `api.mulerun.com`，共用同一 API key。

当时猜测模型列表来自 API 网关动态查询。

### 第4问：`alibaba/qwen-3.6-plus` 和 `opencode/deepseek-v4-flash-free` 从哪来？

进一步检查 MuleRun 文档（mulerun.com）发现：
- 没有专门的"免费模型"，而是通过 Free Plan 每日 200 credits 可用任何模型
- 官方支持的模型列表：https://mulerun.com/docs/api-reference/endpoint/openai/models
- 价格表：https://mulerun.com/docs/creator-guide/pricing/llm.md

### 第5问：`deepseek-v4-flash-free` 到底从哪来？（核心发现）

检查 opencode 运行日志：

```
cat /Users/cheenle/.mulerun/agent-data/opencode/opencode/log/*.log | grep -E "provider|model|deepseek"
```

关键日志：

```
service=provider providerID=opencode found
service=provider providerID=opencode pkg=@ai-sdk/openai-compatible using bundled provider
```

Session 创建记录：

```
session model={"id":"deepseek-v4-flash-free","providerID":"opencode","variant":"max"}
```

API 调用记录：

```
service=llm providerID=opencode modelID=deepseek-v4-flash-free ... stream
```

错误日志显示实际 HTTP 请求：

```
url: "https://api.mulerun.com/v1/responses"
requestBodyValues: {"model":"deepseek-v4-flash-free",...}
```

## 最终架构图

```
mulerun (启动器)
  │
  ├── 设置环境变量
  │     ├── OPENCODE_CONFIG_CONTENT  ← 6 个自定义 provider
  │     ├── OPENCODE_AUTH_CONTENT    ← 认证信息
  │     └── 其他 (OCTEN_API_KEY, XDG_DATA_HOME 等)
  │
  └── 启动 opencode --model openai/gpt-5.5
        │
        ├── 读取 OPENCODE_CONFIG_CONTENT 合并为配置
        │   ├── openai  → @ai-sdk/openai       → api.mulerun.com/v1
        │   ├── google  → @ai-sdk/google        → api.mulerun.com/vendors/google/v1beta
        │   ├── alibaba → @ai-sdk/openai-compatible → api.mulerun.com/v1
        │   ├── moonshot→ @ai-sdk/openai-compatible → api.mulerun.com/v1
        │   ├── xai     → @ai-sdk/openai-compatible → api.mulerun.com/v1
        │   ├── zhipu   → @ai-sdk/openai-compatible → api.mulerun.com/v1
        │   └── opencode (内置) → @ai-sdk/openai-compatible → api.mulerun.com/v1/responses
        │
        └── Session 使用 opencode/deepseek-v4-flash-free
              └── → POST api.mulerun.com/v1/chat/completions
                    → model: "deepseek-v4-flash-free"
                    → MuleRun 网关路由到实际后端
```

## 核心结论

### `deepseek-v4-flash-free` 的三层来源

| 层级 | 来源 | 说明 |
|------|------|------|
| Provider `opencode/` | opencode 二进制内置 | `pkg=@ai-sdk/openai-compatible using bundled provider`，硬编码指向 `api.mulerun.com` |
| 模型名 `deepseek-v4-flash-free` | mulerun 会话注入 | Session 创建时指定 `model={"id":"deepseek-v4-flash-free","providerID":"opencode","variant":"max"}` |
| 实际 API 请求 | MuleRun 网关路由 | 模型名作为参数传给 `api.mulerun.com`，网关负责路由到具体后端 |

### 配置分层

1. **OPENCODE_CONFIG_CONTENT** — 定义 6 个自定义 provider（openai, google, alibaba, moonshot, xai, zhipu）
2. **opencode 内置 provider** — `opencode` 不在 config 中，是二进制内部的硬编码 provider
3. **mulerun 会话管理** — 决定每个会话用什么模型（当前会话用 `deepseek-v4-flash-free`）

### MuleRun 免费计划

| 项目 | 说明 |
|------|------|
| 注册赠送 | 500 credits |
| 每日刷新 | 200 credits/天 |
| 月额度 | 无 |
| 所有模型可用 | 按用量扣 credits |
| 最便宜模型 | Qwen3 Flash (5¢/1M)、GPT-5 Nano (5.25¢/1M) |

官方支持的 LLM 模型和价格：
- 模型列表：https://mulerun.com/docs/api-reference/endpoint/openai/models
- 价格表：https://mulerun.com/docs/creator-guide/pricing/llm.md
- MuleRun 首页：https://mulerun.com

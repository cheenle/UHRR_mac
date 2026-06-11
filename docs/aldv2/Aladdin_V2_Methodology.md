# 阿拉丁 V2 方法论

> IT 老兵擦亮老灯，释放新灵；用 FDE 找真问题，用 SDD 固化架构，用 harness 约束 agent，用 vibe coding 加速工程落地。

## 1. 定义

阿拉丁 V2 是一套面向复杂软件工程的实践方法论，核心是把 IT 老兵的工程判断力和最新 vibe coding / agentic coding 能力结合起来，让经验不再只存在于个人脑中，而是进入架构、文档、计划、验证和可复用工具链。

它不是“AI 写代码方法”，也不是传统架构文档方法，而是一个闭环：

```text
阿拉丁 V2 = 老灯新灵 + FDE Cycle + SDD Spine + Agentic Harness + Product Leverage
```

其中：

- 老灯：IT 老兵的生产经验、故障直觉、架构嗅觉、取舍能力。
- 新灵：vibe coding / agentic coding 释放出的智能执行力。
- FDE Cycle：Echo → Delta → Product 的现场交付节奏。
- SDD Spine：把经验和决策放进可维护的架构骨架。
- Agentic Harness：让 agent 安全工作的上下文、计划、验证和 guardrail。
- Product Leverage：每个 cycle 都降低下一次交付的边际成本。

## 2. 为什么叫阿拉丁 V2

阿拉丁神灯的故事里，旧灯看似普通，灯灵被封印多年；当灯被擦亮，沉睡的力量被释放。

在 IT 语境中：

- 老灯不是业务用户，而是 IT 老兵本人。
- 被封印的是老兵多年项目、事故、上线、重构、维护中积累的隐性判断力。
- 擦亮老灯的是新一代 vibe coding / agentic engineering 工具链。
- 新灵不是神化 AI，而是被释放的智能工程执行力。
- V2 表示它不是传统“老兵手工经验”的 V1，而是老兵经验被 AI 工具链放大、结构化、可复制后的第二形态。

一句话：

```text
阿拉丁 V2 = 老兵判断被新工具链唤醒、放大并工程化后的方法系统。
```

## 3. 方法论目标

阿拉丁 V2 要解决八个问题：

- 老兵经验如何从“口传心授”变成可执行的工程资产。
- vibe coding 如何避免变成幻觉驱动的代码堆。
- 快速原型如何不牺牲长期架构质量。
- 文档如何从负担变成 agent 和人类共享的状态机。
- 复杂系统如何让新 agent 快速接手而不踩老坑。
- 每轮迭代如何产出可复用产品杠杆。
- 真实现场如何持续校验架构判断。
- 软件工程方法如何在个人/小团队中低成本落地。

## 4. 三层循环（核心模型）

> 早期版本用过"七层模型"。实操中证明层太多、记不住、彼此重叠。现在压缩成**三层一循环**——每层只回答一个问题，只背一条约束，只换一个效果。七个旧概念没有消失，而是降级为三层内部的"角色"或"载体"。

```text
L1 定界 Constrain → L2 提速 Execute → L3 沉淀 Capture →（更省的）L1
```

| 层 | 一句话职责 | 谁来做 | 唯一约束 | 换来的效果 |
|----|-----------|--------|----------|-----------|
| **L1 定界** | 动手前划清边界 | 老兵 + 现场事实 | 先写边界卡，超过 10 行说明没想清 | 把 AI 的"高速猜测"变成"高速执行" |
| **L2 提速** | 在边界内快速验证 | AI / agent | 先验最大不确定性，3–5 轮收敛，每轮能 demo | 边界换来的速度本身 |
| **L3 沉淀** | 把学习变成可复用资产 | 人 + AI | 每个 cycle 至少留一个可复用资产，否则不算完 | 下次更便宜——这就是杠杆 |

### 4.1 L1 定界 Constrain

回答"什么是真问题、边界在哪"。

- **角色"老灯"**：老兵判断——生产经验、故障直觉、架构嗅觉、取舍能力。决定方向、风险、质量底线。
- **角色"现场事实"**：给判断提供证据锚点——日志、hex dump、延迟测量、用户体感、硬件/浏览器真实行为。实测优先于手册（强监管领域反转，见批判分析）。
- **产物**：一张边界卡（目标 / 不做什么 / 必须守住什么 / 最容易猜错的 3 点 / 失败如何被发现）。

MRRC 示例：PTT 时序优先级高于 UI 微调；ATR-1000 连接要独立代理；`/CONFIG` 写死 `MRRC.conf` 必须进 guardrail。证据：TX→RX 2-3 秒延迟、ATR-1000 高频 SYNC 假死、Safari AudioContext 异常。

> 铁律：**没有边界的 vibe coding 只是高速猜测。** L1 不完成，不进 L2。

### 4.2 L2 提速 Execute

回答"在边界内怎样最快验证路能不能通"。

- **角色"新灵"**：vibe coding / agent——快速建上下文、生成原型补丁、按 checklist 执行、把事故经验转成 guardrail。
- **节奏"FDE"**：Echo（定义值得做的 demo）→ Delta（允许粗糙，验证最大不确定性）→ Product（在 L3 固化）。

约束：先验最大不确定性；hardcode 可以但假设要记录；每 2-3 天能 demo；超过 5 轮不收敛就换方案；不在早期写大抽象。

MRRC 示例：ATR-1000 从主进程直连 → 线程 → 300ms 轮询 → 节流 → 独立代理，5 轮收敛。

### 4.3 L3 沉淀 Capture

回答"这次学习如何降低下次成本"。

把 Delta 的消耗品代码，提炼成三类长寿载体：

- **SDD Spine（架构记忆）**：开发后的证据驱动 SDD，不让 SDD 反拖开发。MRRC 用 14 章承载上下文、NFR、决策、服务、组件、运维、版本史。
- **Harness（agent 轨道）**：Context / Spec / Plan / Verification / Runtime / Memory，业务场景再加第七类 **Safety/Cost**（见业务工具包）。
- **Product 杠杆（复用资产）**：`audio_interface.py` 让跨平台音频变配置问题；`atr1000_proxy.py` 让硬件独占变代理；`wdsp_wrapper.py` 让 C 库变 Python 可配置；`AGENTS.md` 让未来 agent 不再猜错入口/端口/PTT 时序。

约束：每个 cycle 至少留一个可复用资产。验收问题——6 个月后的自己或新 agent 能否 15 分钟内理解这次决策并安全改代码。

> 循环闭合：L3 产出的资产成为下一次 L1 的起点，于是下一次定界更快、边界更准、猜错更少。**每次迭代都要问：这次是否让下一次更便宜。**

## 5. 标准工作流

### 5.1 Cycle Kickoff

输入：

- 老兵判断：工程风险、架构取舍、质量底线。
- 现场事实：场景、痛点、证据、体感。
- Demo 目标：用户看到什么说明成功。
- Scope 边界：明确本轮不做什么。

输出：

- 一句话问题陈述。
- 一个 demo 脚本。
- 一组可测指标。
- SDD 影响章节。
- agentic plan 初稿。

### 5.2 Echo

Echo 不等于收集需求，Echo 是定义值得做的 demo。

检查点：

- 问题是否来自真实运行证据。
- 是否能用一句话说清痛点。
- 是否能定义用户体感变化。
- 是否明确不做事项。
- 是否知道最不确定的技术点。

### 5.3 Delta

Delta 不追求漂亮代码，追求验证速度。

规则：

- 第一个原型只验证最大不确定性。
- hardcode 可以，但假设要记录。
- 每 2-3 天必须能 demo。
- 3-5 轮应收敛；超过 5 轮要考虑换方案。
- 不在 Delta 早期写大框架。

### 5.4 Product

Product 负责把学习变成资产。

检查点：

- 是否抽象出可复用模块。
- 是否更新 ADR 或说明无需 ADR。
- 是否更新 SDD。
- 是否增加或更新 harness。
- 是否记录已知风险和故障经验。
- 是否让下次类似问题更容易解决。

### 5.5 Release

发布不是打 tag，而是完成知识闭环。

最低要求：

- CHANGELOG 或版本历史更新。
- SDD 受影响章节更新。
- AGENTS 或 skill guardrail 更新。
- 验证命令记录。
- 未解决风险记录。

## 6. 阿拉丁 V2 Skill Pack

阿拉丁 V2 在 OpenCode 中应表现为一套可触发的工程技能，而不是纯文档。

Skill 的职责：

- 在用户提到 `阿拉丁 V2`、`老灯新灵`、`FDE`、`SDD`、`harness`、`agentic engineering`、`vibe coding`、`方法论`、`架构实践` 时加载。
- 帮助 agent 先判断当前处于 Echo、Delta、Product、Review、Documentation 哪个阶段。
- 根据阶段产出对应模板、计划、文档和验证清单。
- 强制将老兵判断、现场事实、验证指标和 Product 杠杆写入结果。
- 防止 agent 直接跳到写代码而忽略边界、NFR、harness 和复盘。

本仓库的 repo-local skill 位于：

```text
.opencode/skills/aladdin-v2/SKILL.md
```

## 7. 度量体系

| 指标 | 健康值 | 警戒信号 |
|------|--------|----------|
| 老兵判断显性化 | 关键取舍进入 ADR/AGENTS/plan | 重要经验只存在聊天记录或脑中 |
| Field Truth 密度 | 每个 cycle 有真实证据 | 凭想象定义需求 |
| Demo 验证率 | Delta 结束能演示 | 一直写代码但不能展示 |
| 迭代收敛速度 | 3-5 轮稳定 | 8 轮以上还在调参 |
| NFR 可测性 | 关键 NFR 有验证方法 | 性能/可靠性只有口号 |
| Product 杠杆 | 后续边际成本下降 | 每次都从零开始 |
| Harness 完整度 | agent 能按文档安全执行 | agent 每次都要重新探索入口 |
| 记忆保真度 | 事故经验能被复用 | 同类事故重复发生 |

## 8. 反模式

### 8.1 新灵失控

表现：AI 很快写出大量代码，但绕过老兵边界、NFR 和运行约束。

修正：先写 guardrail、scope、验证标准，再写代码。

### 8.2 老灯沉默

表现：老兵只在脑中判断，不写 ADR、AGENTS、plan、postmortem。

修正：每次关键判断必须留下至少一种可传承资产。

### 8.3 文档偶像化

表现：文档越来越多，但没人知道该按哪个行动。

修正：每份文档绑定读者、触发场景和下一步动作。

### 8.4 Delta 永久化

表现：原型代码直接长期运行，没有 Product 阶段。

修正：每个 cycle 保留 20-25% 时间做抽象、文档和 harness。

### 8.5 Harness 空壳化

表现：有脚本但不知道何时运行、预期结果是什么、失败代表什么。

修正：每个 harness 写明前置条件、命令、预期输出、失败解释。

## 9. 模板

### 9.1 阿拉丁 V2 Cycle

```markdown
# 阿拉丁 V2 Cycle: [名称]

## 老灯：老兵判断
- 工程风险：
- 架构取舍：
- 最容易被 AI 猜错的点：
- 质量底线：

## 现场事实
- 场景：
- 痛点：
- 证据：
- 当前 workaround：

## Echo
- 一句话问题：
- Demo 脚本：
- 成功指标：
- 不做事项：

## Delta
- 最大不确定性：
- 原型策略：
- 迭代计划：
- 验证命令：

## Product
- 抽象产物：
- ADR/SDD 更新：
- Harness 更新：
- 复盘文档：

## 杠杆
- 下次少做什么：
- 剩余风险：
```

### 9.2 Agentic Task

```markdown
# Agentic Task: [名称]

Goal:
Scope:
Out of Scope:
Files:
Guardrails:

Steps:
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3

Verification:
- Command:
- Expected:
- Failure means:
```

## 10. MRRC 作为实践样本

MRRC 适合作为阿拉丁 V2 样本，因为它同时具备：

- 真实硬件：电台、USB 声卡、ATR-1000、串口、RTL-SDR。
- 实时链路：PTT、TX/RX 音频、WebSocket、AudioWorklet。
- 跨平台复杂度：macOS/Linux/Windows、iOS Safari/Android Chrome。
- 业务体感：远程通联必须像坐在电台前一样自然。
- 长期运营：14 个月 Gap Period 暴露真实痛点。
- 文档体系：FDE、SDD、DESIGN、docs、AGENTS。
- Agentic harness：superpowers specs/plans、dev_tools、运行脚本。

因此，MRRC 不只是业余无线电软件，而是“老兵经验如何被新 AI 工具链释放、约束、放大并工程化”的实证项目。

## 11. 最终原则

1. 老兵判断定方向。
2. 现场事实给证据。
3. 新灵提供速度。
4. FDE 管理节奏。
5. SDD 固化架构。
6. Harness 约束 agent。
7. Product 杠杆降低未来成本。
8. Demo 验证价值。
9. Postmortem 积累未来速度。
10. 每次交付都必须问：这次是否让下一次更容易。

---

文档版本: V1.0  
核心模型: `docs/aldv2/Laodeng_Xinling_Methodology.md`  
OpenCode skill: `.opencode/skills/aladdin-v2/SKILL.md`

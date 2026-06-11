# 老灯新灵核心模型

> 阿拉丁 V2 的核心模型：以 MRRC 为样本，用“阿拉丁神灯”的隐喻解释 IT 老兵经验被最新 vibe coding / agentic engineering 唤醒后的软件工程实践方法。

## 0. 题解

“老灯”指 IT 领域老兵：经历过真实系统上线、故障、重构、性能瓶颈、跨团队协作和长期维护的人。他们的价值不在于掌握某个新框架，而在于知道什么问题会在生产中爆炸，什么抽象会过早，什么文档会没人看，什么测试才真的能防事故。

“新灵”取自阿拉丁神灯的“灯中之灵”，但去掉神化色彩。它指最新 vibe coding / agentic coding 技术释放出的智能工程能力：AI agent、代码生成、自动化计划、快速原型、文档生成、可执行检查、架构抽象和多轮迭代。它不是魔法，也不是替代老兵的神谕，而是被老灯唤醒、受老兵约束、为工程目标服务的新智能。

“老灯新灵方法”的核心不是用 AI 替代老兵，也不是让老兵拒绝 AI，而是让老兵定义方向、边界、风险和质量标准，让 vibe coding/agentic coding 提升探索、实现、验证和文档化速度，再用架构和 harness 把经验固化为可复用资产。

一句话定义：

```text
老灯新灵 = Veteran Judgment + Vibe Coding + FDE Cycle + SDD Spine + Agentic Harness + Product Leverage
```

在 MRRC 中，它表现为：由 IT 老兵识别真实工程风险和产品价值，围绕低延迟 PTT、移动端控制、ATR-1000 天调、WDSP 降噪、FT8/ULTRON 等复杂问题，用 vibe coding/agentic coding 快速推进实现，再把每次“能跑”的方案沉淀为架构决策、SDD、运维模型、验证脚本和未来 agent 可以继续执行的计划。

阿拉丁神灯的故事里，旧灯看似普通，灯灵被封印多年；一旦被擦亮和召唤，沉睡的力量被释放。对应到软件工程：老灯是 IT 老兵长期积累但常被封存在个人经验里的判断力；新灵是被 vibe coding / agentic coding 释放出来的智能执行力。没有老灯，新灵容易变成幻觉驱动；没有新灵，老灯经验容易停留在手工时代。

## 0.1 新老分工

| 维度 | 老灯：IT 老兵 | 新灵：vibe coding / agentic coding | 结合后的方法能力 |
|------|---------------|-------------------------------------|------------------|
| 问题选择 | 判断哪个问题真正值得做 | 快速整理材料和候选方案 | 少做伪需求，快进真问题 |
| 架构边界 | 识别系统边界、状态边界、故障边界 | 快速生成接口、草图、文档和代码 | 高速但不越界 |
| 实现速度 | 判断哪些地方可 hardcode，哪些不能 | 快速产出原型、补齐重复代码 | Delta 阶段提速 |
| 质量控制 | 识别隐性风险、历史坑和运行约束 | 执行 checklist、测试、静态检查 | 质量从经验变成流程 |
| 知识沉淀 | 决定什么经验值得固化 | 生成 ADR、SDD、AGENTS、plan | 经验可复制、可交接 |
| 长期演进 | 判断何时抽象、何时停止迭代 | 辅助重构、迁移、文档同步 | Product 杠杆递增 |

## 1. 方法论目标

老灯新灵方法要解决五个软件工程难题：

- 如何让老兵经验不止停留在脑子里，而是进入架构、计划和 harness。
- 如何让 AI/agent 加速实现，而不是制造不可维护的代码堆。
- 如何在快速试错和长期架构质量之间取得平衡。
- 如何让文档不是负担，而是 agent 和人类的共享状态机。
- 如何把一次性解决方案变成下次可复用的产品杠杆。

MRRC 的实践证明：一个硬件、实时音频、浏览器、Python 服务、DSP、移动 UI、运维部署混合的复杂项目，仍然可以通过明确的 cycle、文档骨架和执行 harness 维持演进速度。

## 2. 三层结构(原七层的归并)

> 早期版本用过"七层模型"。实操中证明层太多、彼此重叠、记不住。现在压缩成**三层一循环**:每层只回答一个问题、只背一条约束、只换一个效果。下面七个概念没有消失,而是归位到三层内部——前者是"为什么这样设计",后者是"动手时怎么记"。

```text
L1 定界 Constrain  ← 老灯(2.1) + 现场事实(2.2)
   一句话:动手前把边界写下来。约束:边界卡 ≤10 行。效果:把"高速猜测"变成"高速执行"。

L2 提速 Execute    ← 新灵/Vibe Coding(2.3) + FDE Cycle(2.4)
   一句话:在边界内让 AI 跑。约束:先验最大不确定性,3-5 轮收敛,每轮能 demo。效果:边界换来的速度。

L3 沉淀 Capture    ← SDD Spine(2.5) + Harness(2.6) + Product Leverage(2.7)
   一句话:每轮至少留一个可复用资产。约束:没有资产=没完成。效果:下次更便宜(杠杆)。

循环:边界 → 速度 → 资产 →(更省的)边界
```

判据:**L1 定方向,L2 出速度,L3 降未来成本。** 任一层缺位,循环就退化——缺 L1 是高速猜测,缺 L2 是纸上方法论,缺 L3 是每次从零开始。

以下 2.1–2.7 是这三层内部七个角色/载体的详细论述,保留作为设计依据。

### 2.1 Veteran Judgment：老灯层(归入 L1 定界)

老灯层回答“什么才是真工程问题”。

MRRC 的老灯不是业务使用方，而是 IT 老兵的系统性判断：知道实时链路中 PTT 时序比 UI 小优化更关键，知道硬件协议不能只信手册，知道浏览器音频状态会在移动端出幺蛾子，知道一个配置路径错误会让多实例部署全部失效，知道“能跑”之后必须尽快 Product 化。

老灯层的输入包括：

- 生产经验：长期运行会暴露需求文档里没有的问题，V3.x 后 14 个月稳定使用成为最长 Echo 阶段。
- 故障直觉：ATR-1000 高频 SYNC 压挂设备、PTT 切换 stale audio、Safari AudioContext 异常都不是普通 CRUD 问题。
- 架构嗅觉：硬件连接要隔离，实时队列要清理，配置路径和默认端口要被明确写入 guardrail。
- 取舍能力：什么时候 hardcode 验证，什么时候抽象，什么时候写 ADR，什么时候停止迭代换方案。

原则：老兵不靠“资历”压人，而是把经验转化为可检查的约束、可执行的计划、可复用的架构和可传承的文档。

### 2.2 Field Truth：现场事实层(归入 L1 定界)

现场事实层回答“老兵判断要锚定在哪些证据上”。

老灯新灵不是纯经验主义。老兵判断必须接受真实系统校验：实测优先于手册，运行日志优先于猜测，用户体感优先于漂亮功能列表。

MRRC 的现场事实包括：

- PTT 2-3 秒延迟破坏通联节奏，因此 V4.0 先做 TX/RX 切换 <100ms。
- ATR-1000 手册字段与实测不一致，因此必须 hex dump 和协议逆向。
- SSB 背景噪声导致长时间收听疲劳，因此 WDSP NR2 比普通滤波器更有价值。
- 移动端 Safari 音频状态特殊，因此移动端不能简单复用桌面假设。

### 2.3 Vibe Coding：新灵层(归入 L2 提速)

新灵层回答“怎样用最新 AI/vibe coding 技术把老兵判断转成速度”。

这里的 vibe coding 不是无约束地让模型自由发挥，而是在老兵定义的边界内，让 AI 快速完成探索、草拟、重构、补文档、生成计划、执行局部修改和反复验证。

MRRC 中的新灵能力包括：

- 用 agent 快速阅读 SDD、FDE、AGENTS、源码和脚本，建立上下文。
- 用 spec/plan 把复杂任务拆成 agent 可执行的步骤。
- 用 AI 快速生成或更新 SDD、ADR、postmortem、实践指南。
- 用局部验证命令约束 AI 输出，而不是只看代码“像不像”。
- 用 AGENTS guardrail 防止 AI 猜错入口、端口、配置、PTT/audio 时序。

核心原则：vibe coding 提供速度和发散能力，老灯提供边界、优先级、风险判断和最终验收。

### 2.4 FDE Cycle：推进层(归入 L2 提速)

FDE 层回答“这一轮怎样从痛点走到成果”。

MRRC 已经形成清晰节奏：

```text
Echo：发现真实痛点，定义能让用户惊讶的 demo
Delta：快速实现，允许 hardcode，目标是验证 demo
Product：抽象泛化，形成可复用模块、ADR、SDD 和运维资产
```

典型例子：ATR-1000 Cycle。

- Echo：无功率/SWR 显示，用户盲发，不知道天线匹配状态。
- Delta：主进程直连、线程、300ms 轮询、节流保护、独立代理，5 轮找到正确约束。
- Product：`atr1000_proxy.py`、Unix Socket 隔离、三态动态轮询、REST API、频率参数学习。

核心判断：Delta 代码是消耗品，Product 产物才是资产。不能在第一天写通用框架，也不能在 demo 成功后跳过抽象。

### 2.5 SDD Spine：架构骨架层(归入 L3 沉淀)

SDD 层回答“系统为什么这样长”。

MRRC 的 SDD 不是传统瀑布式文档，而是 FDE 后的结构化记忆。它把 field truth 和 Delta 经验放入 IBM TeamSD 14 章骨架：

- Ch4 系统上下文：谁在和系统交互，包括浏览器、rigctld、电台、ATR-1000、外部软件。
- Ch5 非功能需求：把体感转成指标，如 TX/RX <100ms、PTT <50ms、功率显示 <200ms。
- Ch6 用例模型：把 demo 固化成可追踪用例。
- Ch8 架构决策：记录为什么选 Tornado、Opus/Int16、WDSP、独立代理、多实例。
- Ch9-Ch12 架构、服务、组件、运维：让后续 agent 能快速定位系统边界。
- Ch14 版本历史：把每次 Product 化纳入演化轨迹。

关键原则：不要让 SDD 驱动开发，让开发后的证据驱动 SDD。SDD 是架构脊柱，不是需求许愿池。

### 2.6 Agentic Harness：执行夹具层(归入 L3 沉淀)

harness 层回答“怎样让人和 agent 都能安全、可重复地推进”。

MRRC 中的 harness 由多种可执行和半可执行资产组成：

- `AGENTS.md`：未来 OpenCode session 的高信号上下文，防止猜错端口、入口、配置、PTT 约束。
- `docs/superpowers/specs/*`：设计规格，先定义目标、范围、约束和不做什么。
- `docs/superpowers/plans/*`：agentic worker 可逐步执行的 checkbox 计划。
- `dev_tools/test_installation.py`、`test_audio.py`、`test_audio_capture.py`：聚焦诊断脚本。
- `mrrc_control.sh`、`mrrc_multi.sh`、Docker Compose：运行和部署 harness。
- SDD NFR 的 Verification 列：把非功能需求连接到可执行验证方法。
- PTT/Audio postmortem、ATR troubleshooting journey：把事故经验变成 guardrail。

harness 的本质是把“我知道但容易忘”的上下文变成“下一次可以执行”的约束。它不是完整自动化测试套件才算 harness；只要能降低 agent 误判、限定执行路径、提供验证命令，就是 harness。

### 2.7 Product Leverage：杠杆层(归入 L3 沉淀)

杠杆层回答“这次成果如何降低下次成本”。

MRRC 的产品杠杆不是商业指标，而是工程复用能力：

- ALSA 直连变成 `audio_interface.py`，跨平台成本下降。
- ScriptProcessor 变成 AudioWorklet，后续音频延迟优化有共同基础。
- 直接 PTT 控制变成预热帧、计数超时、三队列 flush 的可靠性框架。
- ATR-1000 直连变成独立代理、Unix Socket、动态轮询、REST API。
- C 库调用变成 `wdsp_wrapper.py`，DSP 能力可配置、可文档化。
- 单实例配置变成多实例端口、配置、Socket 隔离。
- 现场调参变成 RagChew TX 预设和 WebAudio 技能文档。

评估标准：下次支持相似场景时，是否少写代码、少踩坑、少解释上下文。

## 3. MRRC 的核心抽象

### 3.1 从业务目标到实时约束

业余无线电的业务目标不是“有一个网页控制面板”，而是“远程通联仍然像坐在电台前一样自然”。这会立刻推导出一组强约束：

- PTT 是最高优先级交互，必须低延迟、高可靠。
- RX 音频不能因为切换、缓冲、网络抖动产生可感知断裂。
- 移动端不是附属界面，而是主战场。
- 天调功率/SWR 是发射决策的一部分，不能是慢速装饰数据。
- DSP 目标不是“降噪强”，而是“长时间听不累且语音自然”。

这就是“老兵判断 + 现场事实”到 SDD NFR 的转译：把真实体感和生产风险变成架构可设计、代码可检查、agent 可执行的目标。

### 3.2 从硬件脾气到代理架构

ATR-1000 案例显示，硬件集成不能假设设备像云 API 一样稳定。高频请求会压垮设备，字段可能与手册不一致，连接可能独占。

抽象出的最佳实践：

- 硬件连接尽量由独立代理拥有，主业务进程通过窄接口访问。
- 高频显示需求用动态轮询，而不是固定高频拉取。
- 设备实测协议要沉淀为项目文档，不要只写在代码注释里。
- 外部系统集成优先通过 REST/API 或 socket bridge，不要让多个消费者直连设备。

这套模式可迁移到其他硬件工程：示波器、传感器、工业 PLC、SDR、音频设备都适用。

### 3.3 从实时音频到守护规则

MRRC 的音频链路跨浏览器、WebSocket、Python、PyAudio、WDSP、电台，任何一个队列没清都会造成 stale audio 或 gap。

抽象出的守护规则：

- 实时系统的“正确性”不仅是函数返回正确，还包括时间顺序正确。
- PTT release 是状态边界，必须同时清理 JS、后端已编码帧、原始 PCM accumulator。
- 缓冲不是越小越好，`min:1` 可以用于短暂恢复，但不能成为稳定态。
- 音频帧大小要对齐编解码器时基，避免 fractional frame。

这些规则已经进入 `AGENTS.md` 和 PTT postmortem，成为 agentic harness 的一部分。

### 3.4 从 AI 到本地可控能力

MRRC 的 AI 不是中心化云智能，而是嵌入本地工程系统的可控模块：Whisper/Qwen3-TTS、CW ONNX、FT8/ULTRON、DXCC 决策。

抽象出的原则：

- AI 能力要有边界：本地进程、可选依赖、失败可降级。
- AI 只负责增强某个明确工作流，不替代核心控制闭环。
- 对实时链路，AI 不应阻塞 PTT、音频、控制通道。
- 对 agentic coding，AI 也必须被 harness 约束：入口、测试、计划、guardrail、文档索引。

## 4. 老灯新灵的标准流程

### 4.1 Cycle 入口

每个 cycle 必须以一个现场问题开始，而不是以“我要加一个功能”开始。

入口模板：

```text
场景：谁在什么环境下操作
动作：用户正在做什么
痛点：哪里卡住、慢、难受、不可信
情绪：为什么这个痛点重要
指标：怎样证明改善了
Demo：用户看到什么会说“这就对了”
边界：这轮明确不做什么
```

MRRC 示例：

```text
场景：移动端远程 SSB 通联
动作：用户松开 PTT 等待对方回话
痛点：TX→RX 切换 2-3 秒，错过对方开头
指标：切换 <100ms，PTT 可靠性 99%+
Demo：按下立即发射，松开立即接收
边界：这一轮不做 UI 重写，不做天调学习
```

### 4.2 Echo 输出

Echo 结束时只需要四件东西：

- 一句话问题陈述。
- 一个 demo 脚本。
- 一组可测指标。
- SDD 影响范围：Ch4/Ch5/Ch6 是否需要更新。

不需要 50 页需求文档。超过一页仍说不清 demo，说明 Echo 还没完成。

### 4.3 Delta 执行

Delta 阶段允许粗糙，但必须有纪律：

- 先验证最大不确定性。
- hardcode 可以，隐含假设必须记录。
- 每 2-3 天必须能 demo。
- 迭代超过 5 轮仍不收敛，要重新审视方案。
- 不要在 Delta 早期写大抽象。

Delta 的目标不是代码优雅，而是尽快回答：“这条路能不能通”。

### 4.4 Product 固化

Product 阶段至少完成五件事：

- 抽象一个可复用模块或稳定模式。
- 写下一个 ADR 或更新已有架构决策。
- 更新 SDD 中受影响的章节。
- 增加或更新 harness：命令、测试、脚本、计划、AGENTS guardrail。
- 记录已踩坑，形成故障复盘或实践指南。

Product 的验收问题：6 个月后的自己或一个新 agent，能否在 15 分钟内理解这次决策并安全修改相关代码。

## 5. Agentic Engineering 规则

### 5.1 Agent 不是程序员替身，而是工程加速器

MRRC 的经验说明，agent 最擅长：

- 阅读已有文档并建立上下文。
- 按 plan checklist 执行明确任务。
- 做局部代码修改和验证。
- 生成 SDD/ADR/指南草稿。
- 把事故经验转成 guardrail。

agent 最容易出错：

- 猜测入口、端口、配置路径。
- 把隐藏兼容 HTML 当死代码删掉。
- 不理解 PTT/audio timing 的脆弱性。
- 根据旧 README 执行错误端口或部署路径。
- 对硬件和实时系统做“看起来合理”的抽象。

因此必须用 harness 约束 agent，而不是只给它一个模糊目标。

### 5.2 Agentic Harness 的最小集合

每个复杂项目至少要有这六类 harness：

- Context harness：`AGENTS.md`、架构索引、入口说明、已知坑。
- Plan harness：`docs/superpowers/plans/*` 这类可逐步执行计划。
- Spec harness：目标、范围、数据模型、依赖和 out of scope。
- Verification harness：聚焦测试脚本、语法检查命令、NFR 验证方法。
- Runtime harness：start/stop/status/logs 脚本、Docker Compose、multi-instance 脚本。
- Memory harness：postmortem、troubleshooting journey、ADR、SDD version history。

如果没有这些，agent 会把工程问题退化成“生成代码问题”。

### 5.3 给 agent 的任务颗粒度

好的 agentic 任务应满足：

- 输入文件范围明确。
- 成功标准可验证。
- 不做事项明确。
- 每一步可独立检查。
- 涉及实时/硬件/安全时有 guardrail。

`docs/superpowers/plans/2026-05-31-wdsp-nr2-optimization.md` 是典型样例：它规定文件、函数、参数表、配置变更、语法检查和兼容性验证。这样的计划让 agent 能执行，而不是自行发明工程路径。

## 6. 文档体系原则

老灯新灵方法要求文档分层，不同文档承担不同责任。

### 6.1 DESIGN 层

回答产品和系统边界问题：系统与谁交互、有哪些 API、为什么做某些架构选择。

### 6.2 SDD 层

回答系统设计问题：业务方向、项目定义、上下文、NFR、用例、领域、ADR、服务、组件、运维、可行性。

### 6.3 docs 层

回答工程实践问题：怎样部署、怎样调试、为什么 PTT 出问题、WDSP 怎样配置、ATR-1000 为什么假死。

### 6.4 AGENTS 层

回答未来 agent 最可能猜错的问题：入口、端口、默认配置、运行命令、隐藏依赖、易碎时序。

### 6.5 计划层

回答下一次 agent 应如何执行：spec 定义方向，plan 细化步骤。

文档不是越多越好，而是每层都要有明确读者和动作。如果一行不能帮助未来的人或 agent 少踩坑，就应该删掉。

## 7. 度量体系

老灯新灵方法用八类指标衡量健康度。

| 指标 | 健康表现 | MRRC 示例 |
|------|----------|-----------|
| 老兵判断显性化 | 关键取舍进入 ADR/AGENTS/plan | PTT guardrail、Docker/端口/配置路径说明 |
| Field Truth 密度 | 每个 cycle 来自真实运行证据 | PTT 延迟、天调假死、SSB 听感疲劳 |
| Demo 验证率 | Delta 结束能演示 | PTT <100ms、NR2 听感、功率/SWR 实时显示 |
| 迭代收敛速度 | 3-5 轮稳定 | ATR-1000 第 5 轮独立代理收敛 |
| NFR 可测性 | 每个关键 NFR 有验证方法 | SDD Ch5 Verification 列 |
| Product 杠杆 | 后续相似功能边际成本下降 | `audio_interface.py`、`wdsp_wrapper.py`、ATR proxy |
| Harness 完整度 | agent 能按文档安全执行 | AGENTS、superpowers plans、dev_tools |
| 记忆保真度 | 事故经验能被后续复用 | PTT postmortem、ATR troubleshooting、ADR |

警戒信号：连续两个 cycle 没有抽象产出，连续一个版本没有更新 SDD/ADR，agent 修改前必须重新探索大量基础事实，或者同一类事故重复发生。

## 8. 反模式

### 8.1 新灵压倒老灯

表现：AI/vibe coding 很快生成大量代码，但绕过了老兵对真实硬件、音频时序、移动端限制和长期维护成本的判断。

修正：让老兵先定义边界、风险、NFR 和验收方式，再让 agent 在约束内快速实现。

### 8.2 老灯拒绝新灵

表现：老兵全靠经验手调，不写文档、不建 harness、不让 agent 接手，导致经验无法规模化。

修正：把经验写成 AGENTS guardrail、ADR、可执行计划和验证命令，让 vibe coding 能继承而不是猜测。

### 8.3 SDD 变成神像

表现：为了文档完整而文档，开发被流程拖慢。

修正：开发驱动 SDD，只记录已验证事实和关键决策。

### 8.4 Delta 直接上线

表现：hack 代码能跑就长期运行，没有抽象、没有文档、没有 guardrail。

修正：每个 cycle 强制留下 Product 时间，至少产出一个可复用资产。

### 8.5 Harness 只剩脚本

表现：有很多脚本，但没有说明何时用、验证什么、前置条件是什么。

修正：每个 harness 必须绑定场景、命令、预期结果和失败解释。

## 9. 可迁移模板

任何复杂软件项目都可按以下模板套用。

### 9.1 老灯新灵 Cycle 模板

```markdown
# 老灯新灵 Cycle: [名称]

## 老灯：老兵判断
- 工程风险：
- 架构取舍：
- 最容易被 AI 猜错的点：
- 必须守住的质量底线：

## 现场事实：证据锚点
- 场景：
- 痛点：
- 情绪强度：
- 现有 workaround：
- 实测证据：

## Echo：Demo 定义
- 一句话问题：
- Demo 脚本：
- 成功指标：
- 本轮不做：
- SDD 影响章节：

## Delta：快速验证
- 最大不确定性：
- 原型策略：
- 迭代计划：
- 每轮学到什么：

## Product：抽象固化
- 可复用模式：
- 抽象产物：
- ADR：
- SDD 更新：
- Harness 更新：
- 文档/复盘：

## 杠杆评估
- 下次相似场景少做什么：
- 新增一个场景的边际成本：
- 仍未解决的风险：
```

### 9.2 Agentic Plan 模板

```markdown
# [任务] 实施计划

> For agentic workers: execute step-by-step. Do not skip verification.

Goal: [一句话结果]
Architecture: [设计约束]
Scope: [文件/模块]
Out of Scope: [不做事项]

## Task 1: [最小变更]
- Files:
- Steps:
- Verification:
- Expected result:

## Task 2: [后续变更]
- Files:
- Steps:
- Verification:
- Expected result:

## Guardrails
- 不得破坏：
- 必须保持：
- 如遇到：则停止并询问：
```

### 9.3 Product 化检查清单

- 是否有至少一个真实 demo 成功。
- 是否识别出可复用模式。
- 是否有明确抽象边界。
- 是否更新 ADR 或说明无需 ADR。
- 是否更新 SDD 对应章节。
- 是否更新 AGENTS 或其他 agent context。
- 是否提供至少一个验证命令。
- 是否记录已知风险和不做事项。

## 10. MRRC 的课题价值

MRRC 的价值不只在于业余无线电业务功能，而在于它是一个高密度工程样本：

- 它有真实硬件，因此能检验 AI 生成方案是否尊重物理约束。
- 它有实时音频，因此能检验架构是否处理时间、缓冲和状态边界。
- 它有移动浏览器，因此能检验跨平台兼容和用户体验。
- 它有长期运营，因此能检验 Echo 是否来自真实痛点。
- 它有 SDD 和 FDE 文档，因此能检验文档是否服务工程演进。
- 它有 agentic plans 和 AGENTS guardrail，因此能检验 AI 工程协作是否可控。

因此，“老灯新灵”可以作为一个专门课题：研究传统复杂工程场景如何唤醒 IT 老兵被封存在经验里的判断力，并借助 AI agent、FDE、SDD 和 harness 形成可复用的软件工程方法。

## 11. 最终原则

1. 老兵判断负责定义方向、边界、风险和质量底线。
2. 真实现场是最高优先级证据源。
3. Demo 是 Echo 的终点，也是 Delta 的北极星。
4. Delta 代码可以粗糙，但学习必须清晰。
5. Product 阶段必须把学习变成杠杆。
6. SDD 是架构脊柱，不是瀑布枷锁。
7. Harness 是 agent 安全工作的轨道。
8. Postmortem 是未来速度的一部分。
9. AI 负责放大工程能力，不负责替代工程判断。
10. 每次迭代都要问：这次成果是否让下一次更容易。
11. 老灯不灭，新灵不飘；老兵定边界，现场给证据，智能提速度，架构保长期。

---

文档版本: V1.0  
基于材料: `FDE.md`, `docs/FDE_Practice_Guide.md`, `SDD/`, `DESIGN/MRRC_SDD.md`, `docs/superpowers/`, `AGENTS.md`, MRRC 运行和诊断脚本。

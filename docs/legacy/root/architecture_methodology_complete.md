# IBM Team Solution Design 完整方法论指南

> 端到端深度总结提炼
> 来源: IBM TSS01G v2.3.2 + DWS IoT架构文档
> 日期: 2026-03-13

---

## 一、方法论全景图

### 1.1 核心定位

**TeamSD** = IBM统一的售前解决方案设计方法论

| 维度 | 说明 |
|------|------|
| **目的** | 提高方案设计、提案和构建能力 |
| **价值** | 降低风险、提高质量、促进销售与交付协作 |
| **范围** | 售前阶段 (从机会识别到合同签订) |
| **归属** | UMF (Unified Method Framework) 的一部分 |

### 1.2 与CVM对齐

```
┌─────────────────────────────────────────────────────────────────┐
│                     Client Value Method (CVM)                   │
├─────────────┬─────────────┬─────────────┬─────────────┬────────┤
│  Understand │   Explore   │   Develop   │  Implement  │ Confirm│
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴────┬───┘
       │             │             │             │           │
       ▼             ▼             ▼             ▼           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TeamSD 阶段                                │
├─────────────┬─────────────────────────────┬────────────────────┤
│    PLAN     │   PRE-SALE SOLUTION DESIGN │  SUPPORT IMPLEMENT │
│             │                             │  & CONFIRM VALUE   │
├─────────────┼─────────────┬───────────────┼────────────────────┤
│  UNDERSTAND │   EXPLORE   │    DEVELOP    │   IMPLEMENT        │
│             │             │               │   CONFIRM          │
└─────────────┴─────────────┴───────────────┴────────────────────┘
```

---

## 二、PLAN阶段 - 理解客户业务与需求

### 2.1 阶段目标

> 评估客户业务环境，理解客户需求，识别机会

### 2.2 核心活动

#### Activity: UNDERSTAND Client's Business and Needs

**两大子活动**:

1. **Discovery (发现)**
   - 理解业务环境、目标、挑战
   - 了解组织结构(正式+非正式)
   - 评估技术环境
   - 识别客户战略方向

2. **Opportunity Assessment (机会评估)**
   - 战术性: 具体可落地机会
   - 战略性: 长期规划路线图

### 2.3 任务与产出

| 任务 | 产出工作产品 | 编码 |
|------|-------------|------|
| Understand Business Environment | Business Direction | BUS 411 |
| Describe Current Organization | Current Organization Description | ORG 001 |
| Describe Current IT Environment | Technical Environment | ART 0506 |
| | Standards | ARC 310 |
| Plan for Client Value | Technical Account Plan | ART 0742 |
| | Strategic Roadmap | BUS 326 |
| Identify Opportunity | Opportunity Plan | ART 612 |
| | Project Definition | ENG 343 |

### 2.4 关键输入

- 客户访谈
- 账户团队访谈
- 在线研究 (IBV Points of View, Solution Navigator)
- CVM Account Plan

### 2.5 工作产品详解

#### Business Direction (BUS 411)
基于OMG业务动机模型:
- **Vision (愿景)**: 长期目标
- **Mission (使命)**: 操作性指导
- **Goals (目标)**: 期望结果(定性)
- **Objectives (目标)**: 可衡量指标
- **Strategies (策略)**: 长期方向
- **Tactics (战术)**: 短期行动
- **Directives (指令)**: 政策与规则

#### Current Organization Description (ORG 001)
- 正式组织结构
- 非正式权力关系
- 关键利益相关者

#### Technical Environment (ART 0506)
- 现有应用清单
- 数据库环境
- 网络基础设施
- 安全架构
- 开发测试能力

#### Standards (ARC 310)
分类:
- 当前标准 (As-is)
- 未来标准 (To-be)
-  sunset标准
- 退役标准

### 2.6 阶段检查点

**Milestone: Opportunity Validated**
- 客户验证我们的理解
- 清晰定义的机会
- 业务价值驱动因素明确

---

## 三、PRE-SALE阶段 - 解决方案设计

### 3.1 EXPLORE 活动 - 探索选项与方法

#### 3.1.1 活动目标

- 识别关键需求
- 探索解决方案选项
- 开发初始方案愿景
- 评估成功可能性

#### 3.1.2 核心任务序列

```
Define Project → System Context → NFRs → Requirements
     ↓                              ↓
Data Sources ← Architectural Decisions ← Use Cases
     ↓                              ↓
Architecture Overview ← Viability Assessment
     ↓
Candidate Assets
```

#### 3.1.3 任务详解

| 任务 | 目的 | 产出 |
|------|------|------|
| **Define Project** | 将机会转化为定义的项目 | Project Definition |
| **Describe System Context** | 定义系统边界和交互 | System Context |
| **Identify NFRs** | 识别性能/容量/可用性等 | Non-Functional Requirements |
| **Identify/Outline Requirements** | 定义用例和功能需求 | Use Case Model, Requirements Matrix |
| **Identify High Level Data Sources** | 识别数据源 | Subject Area Model |
| **Document Architectural Decisions** | 记录架构决策 | Architectural Decisions |
| **Sketch Initial Architecture Overview** | 绘制初始架构图 | Architecture Overview |
| **Survey Candidate Assets** | 搜索可复用资产 | Candidate Asset List |
| **Conduct Viability Assessment** | 评估可行性 | Viability Assessment |
| **Ideation** | 构思创新方案 | UI Prototype, Empathy Map |

#### 3.1.4 关键产出详解

**System Context (APP 011)**
- 用户与系统交互
- 外部系统接口
- 批处理输入输出
- 外部事件

**Non-Functional Requirements (ART 0507)**
- 可用性、备份恢复
- 容量规划、配置管理
- 灾难恢复、环境因素
- 可扩展性、可靠性
- 安全性、SLA
- 性能、质量

**Use Case Model (ART 0508)**
- 参与者(Actors)
- 用例(Use Cases)
- 关系图

**Requirements Matrix (BUS 011)**
- 功能需求ID
- 需求名称
- 详细描述
- 对应组件

**Subject Area Model (APP 408)**
- 概念数据模型
- 主要实体分组
- 数据元素关系

**Architectural Decisions (ART 0513)**

决策结构:
```
ID: AD-XXX
Type: Management/Architectural/Operational
Topic: [主题]
Decision Summary: [决策摘要]
Issue/Problem: [问题描述]
Assumptions: [假设]
Motivation: [动机]
Alternatives: [替代方案]
Justification: [理由]
Implications: [影响]
Derived Requirements: [派生需求]
Related Decisions: [相关决策]
```

**Viability Assessment (ART 0530)**

RAID Log:
- **Risks** (风险): 概率×影响
- **Assumptions** (假设): 置信度
- **Issues** (问题): 优先级
- **Dependencies** (依赖): 所有者

#### 3.1.5 里程碑

**Milestone: Opportunity Qualified**

---

### 3.2 DEVELOP 活动 - 开发并同意解决方案

#### 3.2.1 活动目标

- 共同开发解决方案
- 达成客户和IBM都同意的提案
- 完成提案文档

#### 3.2.2 核心任务

| 任务 | 产出 |
|------|------|
| Develop Architecture Overview | Architecture Overview (详细版) |
| Define Key Services | Service Model |
| Develop High Level Component Model | Component Model |
| Develop High Level Operational Model | Operational Model |
| Develop Solution Estimates | Estimation Report |
| Refine Viability Assessment | Viability Assessment (更新) |
| Evaluate Integrated Solution | 技术评审 |
| Propose Solution | 客户提案 |

#### 3.2.3 产出详解

**Architecture Overview (ART 0512)**

视图类型:
- Enterprise View (企业视图)
- Services View (服务视图)
- IT System/Infrastructure View (IT系统视图)

内容:
- 子系统
- 组件
- 节点
- 连接
- 数据存储
- 用户
- 外部系统

**Service Model (ART 0582)**

内容:
- Service Portfolio (服务组合)
- Service Hierarchy (服务层次)
- Service Dependencies (服务依赖)
- Service Composition (服务组合)

**Component Model (ART 0515)**

内容:
- 组件职责
- 接口定义
- 静态关系
- 协作方式

**Operational Model (ART 0522)**

三层视图:
- **ALOM** (Application Logical): 功能/服务/边界,无产品
- **LOM** (Logical): 功能+技术,无产品
- **POM** (Physical): 明确产品

内容:
- 系统拓扑图
- 节点描述
- 组件清单
- 连接矩阵

**Estimation Report (ART 0533)**

内容:
- 项目范围
- 估算方法
- 规模/工时/进度/资源
- 成本明细

#### 3.2.4 质量检查点

- **TDA** (Technical Delivery Assessment)
- **ITR** (Integrated Technical Review) - 跨LOB复杂交易
- **PBA** (Proposal Baseline Assessment)

#### 3.2.5 里程碑

**Milestone: Solution Agreed To**

---

## 四、SUPPORT阶段 - 实施与确认价值

### 4.1 IMPLEMENT 活动 - 实施解决方案

#### 任务

1. **Transition to Implementation**
   - 项目kickoff
   - 向实施团队交接
   - 沟通解决方案设计

2. **Monitor Pilot and Early Implementation**
   - 跟踪试点
   - 验证成功标准

3. **Harvest Assets**
   - 经验教训
   - 资产收割

### 4.2 CONFIRM 活动 - 确认价值

#### 任务

1. **Evaluate Success**
   - 验证交付价值
   - 客户确认
   - 参考案例

2. **Explore New Client Issues**
   - 探索扩展机会
   - 识别新问题

3. **Confirm Client Value**
   - 确认客户满意
   - 规划未来机会

---

## 五、工作产品依赖关系

### 5.1 完整依赖图

```
Phase 1: PLAN
─────────────────────────────────────────────────────────────
                         Project Definition (ENG 343)
                    ┌─────────────────┬─────────────────┐
                    │                 │                 │
          Business Direction    Current Org     Technical Env
              (BUS 411)         (ORG 001)        (ART 0506)
                    │                 │                 │
                    └─────────────────┼─────────────────┘
                                         │
                              Opportunity Plan (ART 612)
                                         │
                                         ▼
Phase 2: EXPLORE (Pre-Sales)
─────────────────────────────────────────────────────────────
                    ┌───────────────────────┐
                    │   Project Definition   │
                    └───────────┬───────────┘
                                │
     ┌──────────────┬───────────┼───────────┬──────────────┐
     │              │           │           │              │
     ▼              ▼           ▼           ▼              ▼
System Context  Use Case    Non-Func    Subject      Architect
   (APP 011)    Model      Reqs       Area Model    Decisions
               (ART 0508) (ART 0507)  (APP 408)     (ART 0513)
     │              │           │           │              │
     └──────────────┴───────────┼───────────┴──────────────┘
                                │
                     Architecture Overview
                          (ART 0512)
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
     Candidate Asset    Viability          Estimation
          List         Assessment            Report
        (ENG 100)       (ART 0530)         (ART 0533)
              │                 │
              └─────────────────┼─────────────────┐
                                │
Phase 3: DEVELOP (Pre-Sales)   │
─────────────────────────────────────────────────────────────┤
                     Architecture Overview
                          (更新)
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
         Service         Component          Operational
          Model          Model               Model
       (ART 0582)      (ART 0515)          (ART 0522)
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                          Estimation
                            Report
                          (更新)
                                │
                                ▼
                        Viability
                        Assessment
                        (更新)
                                │
                                ▼
                         Solution
                          Agreed
                           (里程碑)
```

### 5.2 强制工作产品 (5个)

| # | 工作产品 | 编码 | 阶段 |
|---|----------|------|------|
| 1 | Project Definition | ENG 343 | PLAN |
| 2 | Use Case Model OR Requirements Matrix OR NFRs | 三选一 | EXPLORE |
| 3 | Architectural Decisions | ART 0513 | EXPLORE |
| 4 | Estimation Report | ART 0533 | DEVELOP |
| 5 | Viability Assessment | ART 0530 | EXPLORE/DEVELOP |

---

## 六、设计原则

### 6.1 Outside-In (外部→内部)

```
业务目标 → 用户需求 → 用例 → 架构 → 组件 → 运营
```

### 6.2 Iterative (迭代式)

- 从一般到具体
- 逐步细化
- 任务可并行
- 决策可追溯

### 6.3 Varied Elaboration (差异化精细度)

- 不同模块不同深度
- 早期版本也有价值
- 提供足够细节
- 不过度设计

### 6.4 预集成灵活性

- 预定义流程模板
- 适应不同场景
- 支持部分执行
- 无需方法采择Workshop

---

## 七、IBM设计思维整合

### 7.1 核心概念

**Hills (里程碑)**
```
Who (谁) + What (什么) + Wow (有多好)
```

**Playbacks (回放)**
- 利益相关者参与的定期会议
- 展示进展
- 收集反馈
- 测量对齐

**Sponsor Users (赞助用户)**
- 真实用户参与
- 提供领域专业知识
- 持续反馈

### 7.2 与TeamSD活动对齐

| TeamSD阶段 | 设计思维应用 |
|------------|-------------|
| PLAN - Discovery | 用户同理心、痛点识别 |
| PLAN - Opportunity | 机会识别、Hills |
| EXPLORE | 需求细化、原型验证 |
| DEVELOP | 架构工作坊、技术决策 |

### 7.3 整合价值

- 理解用户真实需求
- 创新的解决方案构思
- 可视化沟通
- 快速验证假设

---

## 八、敏捷整合

### 8.1 敏捷vs传统

| 维度 | 传统瀑布 | 敏捷 |
|------|----------|------|
| 范围 | 固定 | 可变 |
| 时间 | 可变 | 固定 |
| 成本 | 估算 | 固定 |
| 交付 | 阶段式 | 增量式 |

### 8.2 何时用敏捷

- 中低关键度项目
- MVP概念可行
- 客户容忍不确定性
- 有探索预算

### 8.3 敏捷中的架构

**Intentional Architecture (意向架构)**
- 初始架构快速设计
- 约束涌现式设计

**Architecture Runway (架构跑道)**
- 支持开发的 技术举措
- 通过迭代Sprint实现

**协作模型**
- 架构师 ↔ 敏捷团队
- 双向反馈循环

---

## 九、架构决策框架

### 9.1 决策类型

1. **Management (管理类)**
   - 平台选择
   - 供应商选择
   - 战略方向

2. **Architectural (架构类)**
   - 技术选型
   - 集成模式
   - 数据架构

3. **Operational (运营类)**
   - 部署策略
   - 运维模式
   - 监控策略

### 9.2 决策过程

```
问题定义 → 替代方案评估 → 决策 → 理由记录 → 影响分析 → 派生需求
```

### 9.3 最佳实践

- 记录每个重要决策
- 说明替代方案和理由
- 明确影响和派生需求
- 关联回需求

---

## 十、CAMSS技术考量

| 技术 | 关键考量 |
|------|----------|
| **Cloud** | 云架构模式、SaaS、多租户、计费模型 |
| **Analytics** | 数据湖、实时分析、BI、ML |
| **Mobile** | 响应式设计、跨平台、原生vs混合 |
| **Social** | 社交集成、协作平台 |
| **Security** | 身份认证、合规、数据保护、零信任 |

---

## 十一、角色与职责

### 11.1 端到端角色

| 角色 | 职责 |
|------|------|
| **Solution Architect** | 解决方案设计领导 |
| **Delivery Owner** | 交付负责人(早期介入) |
| **Risk Manager** | 风险管理(复杂交易) |

### 11.2 协作模式

```
Sales Role ←→ Solution Architect ←→ Delivery Architect
      ↑                                    ↓
      └────────── Client Team ←────────────┘
```

---

## 十二、实施检查清单

### 12.1 PLAN阶段

- [ ] 业务环境分析完成
- [ ] 组织结构理解
- [ ] 技术环境评估
- [ ] 标准识别
- [ ] 机会识别
- [ ] Project Definition创建

### 12.2 EXPLORE阶段

- [ ] System Context定义
- [ ] 非功能需求捕获
- [ ] 用例/需求矩阵
- [ ] 主题域模型
- [ ] 初始架构草图
- [ ] 架构决策记录
- [ ] 候选资产搜索
- [ ] 可行性评估
- [ ] **Milestone: Opportunity Qualified**

### 12.3 DEVELOP阶段

- [ ] 详细Architecture Overview
- [ ] Service Model
- [ ] Component Model
- [ ] Operational Model
- [ ] 估算报告
- [ ] 技术评审通过
- [ ] 客户提案
- [ ] **Milestone: Solution Agreed**

### 12.4 SUPPORT阶段

- [ ] 实施过渡
- [ ] 实施监控
- [ ] 资产收割
- [ ] 成功评估
- [ ] 价值确认

---

## 十三、关键成功因素

1. **客户价值导向**
   - 始终以业务价值为核心
   - 量化价值主张

2. **迭代式方法**
   - 逐步细化
   - 持续反馈

3. **利益相关者对齐**
   - 定期Playbacks
   - 透明沟通

4. **资产复用**
   - Solution Navigator
   - 参考架构
   - 加速器

5. **风险管理**
   - 早期识别
   - 主动缓解

6. **质量保证**
   - 强制检查点
   - 同行评审

---

## 十四、工具与资源

### 14.1 核心工具

| 工具 | 用途 |
|------|------|
| **Solution Navigator** | 解决方案资产搜索 |
| **Solution Gateway** | 资产元搜索引擎 |
| **Cognitive Architect** | 架构设计辅助 |
| **iRAM** | IBM资产库 |
| **UMF Browser** | 方法论导航 |

### 14.2 工作产品模板

通过UMF获取标准模板:
- method.ibm.com/rmchtml_teamsd

---

## 十五、案例研究关键要点 (Maple Bank)

### 15.1 业务背景
- 移动银行App评分低 (2.0)
- 目标: 成为领先移动银行

### 15.2 技术方案
- **平台**: IBM Worklight
- **前端**: Dojo Mobile (HTML5)
- **架构**: 通道服务层
- **部署**: 分阶段 (iPhone→Android→BB)

### 15.3 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 移动平台 | Worklight | 灵活性、可靠性、生产力 |
| 服务格式 | JSON | 简单、低开销 |
| 代码复用 | 重用Online Banking | 成本、上市时间 |
| 应用类型 | 混合HTML5 | 跨平台、一致性 |

### 15.4 成果
- 评分: 2.0 → 4.5
- App Store最佳新App
- 2000+分行预约
- R2合同获得

---

## 附录: 工作产品编码速查

| 编码 | 工作产品 | 阶段 |
|------|----------|------|
| ART 0506 | Technical Environment | PLAN |
| ART 0507 | Non-Functional Requirements | EXPLORE |
| ART 0508 | Use Case Model | EXPLORE |
| ART 0512 | Architecture Overview | EXPLORE/DEVELOP |
| ART 0513 | Architectural Decisions | EXPLORE |
| ART 0515 | Component Model | DEVELOP |
| ART 0522 | Operational Model | DEVELOP |
| ART 0530 | Viability Assessment | EXPLORE/DEVELOP |
| ART 0533 | Estimation Report | DEVELOP |
| ART 0582 | Service Model | DEVELOP |
| APP 011 | System Context | EXPLORE |
| APP 408 | Subject Area Model | EXPLORE |
| BUS 011 | Requirements Matrix | EXPLORE |
| BUS 411 | Business Direction | PLAN |
| BUS 326 | Strategic Roadmap | PLAN |
| ENG 100 | Candidate Asset List | EXPLORE |
| ENG 343 | Project Definition | PLAN |
| ORG 001 | Current Organization Description | PLAN |
| ARC 310 | Standards | PLAN |
| ART 612 | Opportunity Plan | PLAN |
| ART 614 | Client Value Account Plan | PLAN |
| ART 617 | Account Profile | PLAN |
| ART 696 | Client Imperative | PLAN |
| ART 742 | Technical Account Plan | PLAN |

---

*本文档为IBM Team Solution Design方法论的完整端到端总结，供未来参考使用*
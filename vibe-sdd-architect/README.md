# Vibe-SDD Architect 快速入门

> 将企业级架构思维注入AI辅助编程

## 快速开始

### 1. 创建新项目

```bash
# 初始化项目结构
mkdir my-vibe-sdd-project
cd my-vibe-sdd-project

# 创建核心文档
# (见下方模板)
```

### 2. 核心文档结构

```
my-vibe-sdd-project/
├── SPEC.md                 # 项目规格 (必须)
├── CONTEXT.md              # 系统上下文
├── REQUIREMENTS.md         # 需求矩阵
├── NFR.md                  # 非功能需求
├── ARCH-DECISIONS.md       # 架构决策
├── ARCH-OVERVIEW.md        # 架构概览
├── estimation.md            # 估算报告
├── src/                    # 源代码
│   ├── components/
│   ├── services/
│   └── ...
├── tests/                  # 测试
└── docs/                   # 额外文档
    ├── api/
    └── deployment/
```

### 3. 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                      Vibe-SDD 工作流                         │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│    PLAN     │   EXPLORE   │   DEVELOP   │    ITERATE        │
├─────────────┼─────────────┼─────────────┼───────────────────┤
│ 需求发现     │ 架构探索     │ 代码生成     │ 迭代优化          │
│ 规格定义     │ 技术选型     │ 组件开发     │ 测试验证          │
│ 机会识别     │ 可行性评估   │ API实现      │ 部署交付          │
├─────────────┼─────────────┼─────────────┼───────────────────┤
│ 产出:       │ 产出:       │ 产出:       │ 产出:             │
│ - SPEC.md   │ - REQ.md   │ - 代码       │ - 可用系统        │
│ - CONTEXT   │ - NFR.md   │ - ARCH-OVER │ - VALIDATION      │
│ - PERSONAS  │ - ARCH-DEC │ - ESTIMATION│ - LESSONS         │
└─────────────┴─────────────┴─────────────┴───────────────────┘
```

## 核心命令

### 使用AI生成文档

```bash
# 1. 生成项目规格
AI提示: "基于以下业务需求生成SPEC.md..."

# 2. 生成需求矩阵
AI提示: "分析SPEC.md，生成完整的需求矩阵..."

# 3. 生成架构设计
AI提示: "基于需求分析，设计系统架构..."

# 4. 生成代码
AI提示: "根据ARCH-OVERVIEW.md实现功能..."
```

### 迭代演进

```bash
# 每次迭代后更新文档
1. 更新需求状态 (REQUIREMENTS.md)
2. 记录新决策 (ARCH-DECISIONS.md)
3. 更新架构 (如有必要)
4. 记录经验教训 (LESSONS.md)
```

## AI工具集成

### Cursor
```bash
# 将 .cursorrules 复制到项目根目录
cp vibe-sdd-architect/config/.cursorrules ./
```

### Windsurf
```bash
# 类似配置 (使用 .windsurfrules)
```

### Devin
```bash
# 使用SPEC.md作为任务输入
/devin "实现SPEC.md中定义的MVP功能"
```

## 示例

### 示例1: 电商后端服务

```bash
# 1. 创建规格
# 参考: examples/ecommerce/SPEC.md

# 2. AI生成需求
AI: "分析电商系统需求，生成完整需求矩阵"

# 3. AI设计架构
AI: "设计电商后端微服务架构，包含：
      - 用户服务
      - 商品服务
      - 订单服务
      - 支付服务"

# 4. AI生成代码
AI: "基于架构设计，实现用户服务的REST API"
```

### 示例2: React管理后台

```bash
# 1. 定义规格
AI: "生成分页管理系统规格，包含用户CRUD、权限管理"

# 2. 技术选型
AI: "对比React管理后台方案：Ant Design vs Material UI vs Chakra UI"

# 3. 生成代码
AI: "使用Ant Design实现用户管理页面，包含表格、弹窗、分页"
```

## 最佳实践

### Do's ✅
- 始终从规格开始
- 记录所有重要决策
- 保持文档与代码同步
- 使用版本控制

### Don'ts ❌
- 不要跳过规格直接写代码
- 不要忽略非功能需求
- 不要忽视架构决策
- 不要让文档过时

## 检查清单

### 开始新功能前
- [ ] 需求已明确 (SPEC/REQUIREMENTS)
- [ ] 技术选型已确定 (ARCH-DECISIONS)
- [ ] 架构设计已完成 (ARCH-OVERVIEW)

### 功能完成后
- [ ] 代码符合规范
- [ ] 单元测试通过
- [ ] 需求状态已更新
- [ ] 如有新决策已记录

### 迭代完成后
- [ ] 功能测试通过
- [ ] 性能符合NFR
- [ ] 文档已更新
- [ ] 经验教训已记录

## 常见问题

### Q: 如何处理需求变更？
A:
1. 评估变更影响
2. 更新SPEC.md
3. 评估是否需要更新架构
4. 记录新决策
5. 同步团队

### Q: AI生成的代码如何保证质量？
A:
1. 清晰的规格和约束
2. 明确的验收标准
3. 代码审查
4. 自动化测试
5. 性能和安全检查

### Q: 如何在团队中推广？
A:
1. 培训团队成员
2. 从小项目开始试点
3. 逐步完善模板和工具
4. 收集反馈持续改进

## 相关资源

- TeamSD方法论: `architecture_methodology_complete.md`
- 架构思维: `architecture_thinking_summary.md`
- IBM UMF: method.ibm.com

---

*Vibe-SDD = 企业级架构思维 + AI辅助编程 = 高质量快速交付*
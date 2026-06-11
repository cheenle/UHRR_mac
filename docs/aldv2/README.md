# 阿拉丁 V2 文档集

本目录集中存放阿拉丁 V2 / 老灯新灵方法论相关文档。

## 文档结构:主张 → 反思 → 实操 的闭环

| 文档 | 层次 | 职责 | 读者 |
|------|------|------|------|
| `Aladdin_V2_Methodology.md` | 主张 | 阿拉丁 V2 总纲:三层一循环、工作流、度量、模板 | 想了解方法论全貌的人 |
| `Laodeng_Xinling_Methodology.md` | 主张(核心模型) | 老兵经验与 vibe coding / agentic engineering 的结合方式 | 想理解底层模型的人 |
| `Aladdin_V2_Critical_Review.md` | 反思 | 客观辩证审视:正面证据、盲点、正反合综合、适用边界 | 准备引用/推广/裁剪方法论前必读 |
| `Aladdin_V2_Business_Toolkit.md` | 实操 | 面向通用业务团队的五个可复制工具(边界卡、七类 Harness、硬指标、纠错回路、失效标注) | 要把方法用到真实业务的团队 |
| `SKILL.md` | 操作层副本 | `aladdin-v2` OpenCode skill 的文档副本 | 维护 skill 的人 |

## 阅读路径建议

- **第一次了解**:`Laodeng_Xinling_Methodology.md` → `Aladdin_V2_Methodology.md`
- **要用到团队/业务**:先读 `Aladdin_V2_Critical_Review.md` 确认适用边界,再用 `Aladdin_V2_Business_Toolkit.md` 取工具
- **核心判断**:方法论是"成熟度高度不均衡"的——在单人硬件项目锤炼过的维度(harness、SDD、memory、可执行 plan)精良且已被实物验证;在从未遭遇压力的维度(团队仲裁、纠错回路、成本/安全、高频反馈)接近空白。出了射程要自己装备,业务工具包就是那套装备。

## Skill 同步

OpenCode 实际加载的 skill 位于 `.opencode/skills/aladdin-v2/SKILL.md`,并引用本目录作为方法论来源。修改 skill 时应同步更新这两个副本。

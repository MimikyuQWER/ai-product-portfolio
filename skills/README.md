# Skills — AI 开发基础设施

> 本目录包含在作品集项目开发过程中沉淀的 6 个自建 Claude Code Skill。每个 Skill 定义了 AI 在特定场景下的行为约束——该做什么、不该做什么、如何验证——确保输出可复现、可溯源。

## 为什么需要 Skill？

通用的 AI 模型不知道你的项目规范、计算口径、工作流程。Skill 就是把"我们是怎么做事的"结构化地告诉 AI。同一个模型，有 Skill 和没有 Skill 的表现差异远大于不同模型之间的差距。

## Skill 清单

### 量化投资

| Skill | 说明 |
|-------|------|
| [factor-backtest](factor-backtest/SKILL.md) | 因子研究→回测→版本管理完整链路。统一计算口径（几何年化、ddof=1 时序标准差），所有结果从版本档案读取不重算，严禁编造数据。 |
| [cn-investment-research](cn-investment-research/SKILL.md) | A股/债券/衍生品投研分析。个股五层分析、DCF 估值（中债利率）、可转债双低策略。AKShare（免费优先）+ iFinD MCP（付费兜底）双数据源。 |

### AI 产品开发

| Skill | 说明 |
|-------|------|
| [harness-engineering](harness-engineering/SKILL.md) | Agent 集群设计 + Context 工程 + 评测体系 + 记忆系统设计。源自米哈游多 Agent 集群实战 + Anthropic/OpenAI 官方 Harness 实践。 |

### 知识库管理

| Skill | 说明 |
|-------|------|
| [wiki-material-ingest](wiki-material-ingest/SKILL.md) | 金融研报 PDF/PPTX → Markdown 入库。MarkItDown + pdfplumber 双工具对比择优，含质量控制检查。 |
| [wiki-page-writer](wiki-page-writer/SKILL.md) | 结构化 Wiki 页面编写规范。强制 frontmatter、内容溯源、反编造检查。支持 Entity/Judgment/Pattern/Observation 四种页面类型。 |
| [feishu-qa-detector](feishu-qa-detector/SKILL.md) | 飞书学习笔记自动检测疑问句（？/?），用本地知识库 + iFinD 实时数据给出可溯源答案，含反馈闭环。 |

## 使用方式

这些 Skill 是为 Claude Code 设计的，拷贝到 `~/.claude/skills/` 目录即可被 Claude Code 自动加载。每个 SKILL.md 中的 description 字段定义了触发条件——当你的对话匹配触发词时，Skill 会自动激活。

```bash
# 安装示例
cp -r factor-backtest ~/.claude/skills/
```

## 设计思路

Skill 的本质是**用结构化文档约束 AI 行为**，核心设计原则：

1. **不是文档，是约束**：Skill 不只是"告诉 AI 怎么做"，更是"定义 AI 不能怎么做"。每个 Skill 都包含禁止项——禁止编造数据、禁止重写回测引擎、禁止修改 raw/ 文件等。

2. **渐进式披露**：Skill 前面是触发条件和核心规则（AI 快速判断是否适用），详细的参考材料和脚本章节在后面（需要时深入）。不把全部内容塞进上下文。

3. **流程标准化**：每个 Skill 定义了明确的工作流（如 factor-backtest 的 Phase 1→6），每一步有输入、输出、验证标准。AI 不需要"思考该怎么做"，只需要"按流程执行"。

4. **可验证性**：约束不是建议——factor-backtest 要求指标从 `result.json` 读取而非重算，wiki-page-writer 要求每条陈述可溯源 raw/ 原文。这些是可以通过程序验证的硬约束。

5. **持续迭代**：每个 Skill 都是活的——从实际使用中发现 AI 的常见错误模式，反向编码进 Skill 作为新的约束规则。

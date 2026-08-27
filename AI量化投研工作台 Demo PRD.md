# AI量化投研工作台 Demo PRD

**产品代号：Quant Research Copilot**  
**版本：PRD v1.0**  
**产品形态：Web Demo / Desktop-first**  
**目标用户：量化研究员、基金经理、投研负责人、金融机构AI产品负责人**

---

# 1. 产品概述

## 1.1 产品定位

Quant Research Copilot 是一个面向专业量化投研场景的 **AI-native Quant Research Workspace**。

产品不是让 AI 黑盒式生成因子或策略，而是将真实量化研究流程结构化，使：

- 人提出研究假设、做专业判断和最终审批；
- AI 将自然语言研究想法形式化、执行分析、解释结果、发现异常并提出改进建议；
- 确定性的量化计算引擎负责因子计算、回测、金融指标及完整性校验；
- 系统记录所有因子、策略、实验、参数、版本及研究决策；
- 每一个结果都做到 **可见、准确、可复现、可追踪、可审计**。

产品核心价值不是“AI帮用户生成更多策略”，而是：

> **让人和AI共同完成一个严谨、透明且可持续积累知识的量化研究流程。**

---

# 2. 背景与用户痛点

当前 AI + Quant 产品通常存在以下问题：

| 痛点 | 典型表现 | 风险 |
|---|---|---|
| 黑盒 | 用户不知道AI实际计算逻辑 | 无法判断研究结论可信度 |
| 计算口径漂移 | AI迭代时偷偷修改参数或公式 | 不同版本不可比较 |
| 结果导向 | 只展示Sharpe和净值 | 容易数据挖掘和过拟合 |
| 缺少研究过程 | 不记录假设、实验及失败结果 | 研究知识无法积累 |
| 前视偏差 | 财务数据、指数成分使用错误日期 | 回测结果虚高 |
| 无版本管理 | 修改策略后覆盖旧版本 | 无法复现 |
| AI既执行又决策 | AI自行判断是否采纳策略 | 缺少Human-in-the-loop |
| 指标可信度不足 | 金融公式由LLM临时生成 | 结果不可用于专业投研 |
| 缺少系统性测试 | 仅验证单一参数 | 无法判断Alpha稳定性 |
| 研究记录分散 | Notebook、Excel、代码、聊天混在一起 | 协作及审计困难 |

本产品需要将上述问题通过产品机制直接约束，而不是只依靠 Prompt。

---

# 3. 产品目标

## 3.1 核心目标

### G1：建立可复现的量化研究工作流

任何一次实验必须明确记录：

- 数据范围；
- 股票池；
- Benchmark；
- 因子定义；
- 计算口径；
- 参数；
- 数据时间规则；
- 回测规则；
- 引擎版本；
- 实验结果；
- 人工决策。

用户应可以在未来任意时间重新打开某个历史版本并理解其完整逻辑。

---

### G2：建立Human-AI Co-Research体验

AI主要承担：

- 研究假设形式化；
- 参数解释；
- 研究建议；
- 自动执行实验；
- 结果分析；
- 异常发现；
- 改进建议；
- 版本Diff解释。

人主要承担：

- 提出投资逻辑；
- 确认研究定义；
- 判断经济意义；
- 决定是否执行实验；
- 决定是否接受AI建议；
- Approve / Revise / Reject。

---

### G3：降低AI量化研究的黑盒感

用户在任何时刻都应回答以下问题：

1. 当前研究对象是什么？
2. 当前版本是什么？
3. 当前因子到底怎么算？
4. 使用了哪些数据？
5. 数据在什么时间可获得？
6. 当前策略用了哪些因子？
7. 与上一版本相比改了什么？
8. 当前结果基于哪些参数？
9. AI提出了什么建议？
10. 哪些是AI判断，哪些是确定性计算？
11. 当前版本为什么被采纳或废弃？

---

### G4：保证基本量化研究正确性

核心金融计算不得交由 LLM 自由生成。

系统必须提供稳定的：

- 因子处理函数；
- IC / Rank IC；
- ICIR；
- 分组收益；
- Long-short收益；
- Sharpe；
- Sortino；
- Maximum Drawdown；
- Calmar；
- Alpha / Beta；
- Tracking Error；
- Information Ratio；
- Turnover；
- Transaction Cost；
- Annualized Return；
- Annualized Volatility。

同时建立：

- point-in-time数据规则；
- look-ahead prevention；
- survivorship bias prevention；
- 财报发布时间处理；
- 公司行为处理；
- execution lag；
- Golden Test。

---

# 4. 非目标

Demo v1阶段不追求：

1. 实盘交易；
2. 券商OMS连接；
3. 超高频策略；
4. 完整投资组合优化器；
5. 超复杂风险模型；
6. Tick级数据；
7. 自动生成1000个因子；
8. 自动寻找最高Sharpe策略；
9. AI自行批准策略；
10. 完整企业级权限系统。

Demo核心任务只有一个：

> **完整展示一次真实、可信、人机共创的量化研究闭环。**

---

# 5. 产品设计原则

## P1. Human Controlled

AI可以建议、执行、解释，但不得替用户执行最终研究决策。

所有关键决策需要用户显式操作。

---

## P2. No Silent Mutation

AI不得在用户不可见的情况下修改：

- 因子公式；
- 股票池；
- 回测区间；
- Benchmark；
- 交易成本；
- 中性化；
- 调仓频率；
- 因子权重；
- 风控规则；
- 执行价格。

任何修改必须形成明确的 Proposed Change。

---

## P3. Every Run is Immutable

一旦实验执行完成：

> 该版本禁止原地修改。

任何变化：

`v1.0 → v1.1`

必须新建版本。

---

## P4. Hypothesis Before Backtest

测试前必须记录：

- 投资假设；
- 预期方向；
- 预期持有周期；
- 经济意义。

减少“先找到结果，再编解释”的数据挖掘行为。

---

## P5. Deterministic Finance Core

金融计算应来自确定性引擎。

LLM负责解释结果，不负责决定Sharpe怎么算。

---

## P6. Evidence Before Recommendation

AI提出研究判断时必须引用对应证据：

例如：

> OOS Rank IC由0.042下降至0.029，下降31%。

而不是：

> 这个因子可能不稳定。

---

## P7. Failure is Research Asset

被拒绝的：

- 因子；
- 策略；
- 参数组合；

均必须保存。

系统需要积累：

> What worked + What didn't work.

---

# 6. 目标用户

## Persona A：Quant Researcher

### 核心诉求

- 快速验证研究思路；
- 少写重复数据处理代码；
- 明确因子定义；
- 做稳定性验证；
- 保留完整实验历史。

### 高频任务

- 新建因子；
- 修改计算周期；
- IC分析；
- 参数敏感性分析；
- 因子相关性分析；
- 策略回测；
- 版本比较。

---

## Persona B：Portfolio Manager

更关心：

- 经济意义；
- 策略收益来源；
- 风险；
- 回撤；
- 稳健性；
- OOS表现；
- 是否值得采纳。

不一定查看底层代码。

---

## Persona C：Head of Quant / Research Manager

更关心：

- 研究流程是否规范；
- 是否存在前视偏差；
- 版本管理；
- 因子池；
- 团队已经试过哪些研究；
- 什么失败过；
- 研究资产是否可以复用。

---

# 7. 核心产品对象

整个产品不以Chat为中心，而以Research Objects为中心。

核心对象：

```text
Research Project
    │
    ├── Research Configuration
    │
    ├── Factor
    │     ├── Factor Version
    │     ├── Factor Experiment
    │     └── Factor Decision
    │
    ├── Strategy
    │     ├── Strategy Version
    │     ├── Backtest Run
    │     └── Strategy Decision
    │
    └── Research History
```

---

# 8. 核心对象定义

## 8.1 Research Project

代表一次完整投研项目。

字段：

| 字段 | 示例 |
|---|---|
| Project Name | CSI500 Multi-factor Research |
| Description | 基于基本面+动量的月频Alpha研究 |
| Owner | User |
| Created At | Timestamp |
| Status | Active / Archived |

---

# 9. Research Configuration

这是项目创建后的第一步。

## 9.1 页面目标

强制用户先确定实验环境，再开始研究。

---

## 9.2 参数

### Universe

支持Demo：

- CSI300
- CSI500
- CSI1000
- All A Shares

---

### Benchmark

例如：

- CSI300
- CSI500
- CSI1000

---

### Research Period

通过时间轴拖拽选择。

例如：

`2015-01-01 → 2025-12-31`

---

### Dataset Split

必须支持：

- Train；
- Validation；
- OOS。

示例：

```text
2015 ─────── 2021 │ 2022 ── 2023 │ 2024 ── 2025
      Train       │ Validation   │ OOS
```

建议UI：

用户拖动两个分隔点。

---

## 9.3 默认建议

AI可以建议：

> 当前样本共10年，建议采用60% Train / 20% Validation / 20% OOS。

但必须由用户确认。

---

## 9.4 其他配置

| 配置 | 示例 |
|---|---|
| Rebalance Frequency | Monthly |
| Execution Lag | T+1 |
| Execution Price | VWAP |
| Transaction Cost | 10bps |
| Grouping | Quintile |
| IC Horizon | 20 trading days |
| Industry Classification | CITIC L1 |
| Industry Neutralization | Enabled |
| Size Neutralization | Enabled |
| Winsorization | MAD × 3 |
| Standardization | Z-score |
| Missing Value Policy | Industry Median |

---

# 10. 全局Research Context Bar

在所有研究页面顶部固定展示：

```text
CSI500 · 2015–2025 · Monthly · T+1 · 10bps · Industry+Size Neutral
```

点击可以展开完整Configuration。

目的：

> 用户永远知道自己当前在哪个实验环境中。

---

# 11. Factor Lab

这是Demo第一核心页面。

---

# 12. 创建因子

用户可以自然语言输入：

> 我觉得过去一个季度分析师一致预期EPS持续上修的股票未来一个月可能表现更好。

---

# 13. AI形式化研究假设

AI解析后生成：

## Hypothesis

**Investment Hypothesis**

分析师盈利预测持续上调可能代表公司基本面改善，而市场对盈利预期变化存在逐步定价过程，因此可能形成中短期收益持续性。

**Expected Direction**

Positive

**Expected Horizon**

20 trading days

**Factor Category**

Fundamental / Analyst

---

# 14. Factor Specification

AI同时生成结构化Factor Spec。

例如：

### Factor

**Analyst EPS Revision Momentum**

---

### Formula

```text
EPS_REV_3M(t)

=
FY1_EPS_CONSENSUS(t)
-
FY1_EPS_CONSENSUS(t-60)

────────────────────────

ABS(FY1_EPS_CONSENSUS(t-60))
```

---

### Calculation Definition

| 字段 | 内容 |
|---|---|
| Raw field | FY1 Consensus EPS |
| Lookback | 60 trading days |
| Calculation frequency | Daily |
| Rebalance | Monthly |
| Expected direction | Positive |
| Execution lag | T+1 |
| Winsorization | MAD × 3 |
| Standardization | Cross-sectional Z-score |
| Neutralization | CITIC L1 + log Market Cap |
| Missing values | Exclude |
| Universe | CSI500 PIT constituents |

---

# 15. Data Lineage

用户可点击：

**View Data Lineage**

显示：

```text
Analyst Consensus Database
        ↓
FY1 EPS Consensus Snapshot
        ↓
Point-in-time Filter
        ↓
60D Change
        ↓
Winsorization
        ↓
Industry Neutralization
        ↓
Size Neutralization
        ↓
Z-score
        ↓
Factor Value
```

---

# 16. Factor Spec状态

状态：

- Draft；
- Ready to Test；
- Testing；
- Tested；
- Approved；
- Rejected；
- Superseded。

---

# 17. AI Research Reviewer

右侧固定AI Copilot。

此时AI可以指出：

### AI Review

> 当前定义存在一个潜在问题：FY1预测在财年切换期间可能出现基准变化。建议测试FY1标准化处理，或使用NTM EPS Revision。

操作：

- `Apply Suggestion`
- `Ignore`
- `Ask Why`

如果用户Apply：

系统明确展示：

```text
Proposed Change

Current:
FY1 EPS

Proposed:
NTM EPS

Reason:
Reduce fiscal-year rollover distortion
```

用户Confirm之后再生效。

---

# 18. Run Factor Test

点击：

**Run Factor Test**

之前显示：

## Pre-run Summary

- Factor: Analyst EPS Revision
- Version: v1.0
- Universe: CSI500
- Period: 2015–2025
- Train: 2015–2021
- Validation: 2022–2023
- OOS: 2024–2025
- Horizon: 20D
- Neutralization: Industry + Size
- Transaction lag: T+1

按钮：

**Confirm & Run**

---

# 19. Factor Diagnostics

实验完成后进入结果页。

---

# 20. Factor Summary

顶部Summary Card：

| Metric | Value |
|---|---:|
| Rank IC | 0.038 |
| ICIR | 0.62 |
| IC Positive Ratio | 65% |
| G5-G1 Ann. Excess | 8.7% |
| Turnover | 42% |

旁边状态：

**Research Integrity: PASS**

---

# 21. IC Analysis

表：

| Metric | Train | Validation | OOS |
|---|---:|---:|---:|
| Mean Rank IC | 0.041 | 0.036 | 0.031 |
| IC Std | 0.058 | 0.061 | 0.059 |
| ICIR | 0.71 | 0.59 | 0.53 |
| Positive Ratio | 68% | 64% | 61% |

图：

**Monthly Rank IC**

必须能看到：

- Train；
- Validation；
- OOS分区。

---

# 22. Quantile Return Analysis

输出：

| Portfolio | Annualized Excess Return |
|---|---:|
| G1 | -3.1% |
| G2 | -0.7% |
| G3 | +0.6% |
| G4 | +2.1% |
| G5 | +5.6% |
| G5-G1 | +8.7% |

可视化：

### Chart A

G1-G5 Bar Chart

### Chart B

G5-G1 cumulative NAV

---

# 23. Monotonicity

系统自动计算：

**Monotonicity Score**

例如：

`0.87 / 1.00`

说明：

> 分组收益整体随因子暴露提升而改善。

---

# 24. Stability Analysis

按年份：

| Year | Rank IC |
|---|---:|
| 2018 | 0.045 |
| 2019 | 0.038 |
| 2020 | 0.050 |
| 2021 | 0.033 |
| 2022 | 0.030 |
| 2023 | 0.041 |
| 2024 | 0.028 |
| 2025 | 0.034 |

支持：

- 年度；
- 市场状态；
- 行业；
- 市值分组。

Demo至少实现年度。

---

# 25. Sensitivity Analysis

一级Tab：

**Robustness**

---

## 25.1 Lookback × Holding Period

例如：

| Lookback | 5D | 10D | 20D | 60D |
|---|---:|---:|---:|---:|
| 20D | .031 | .038 | .032 | .014 |
| 40D | .036 | .044 | .039 | .020 |
| 60D | .034 | .047 | .041 | .021 |
| 120D | .015 | .028 | .026 | .010 |

显示Heatmap。

---

## 25.2 可选敏感性测试

Demo支持：

- Lookback；
- Holding Period；
- Neutralization；
- Winsorization；
- Universe；
- Rebalance Frequency。

---

# 26. AI Research Review

实验结束后AI生成结构化Review。

格式：

## Observation

> Train Rank IC = 0.041，OOS = 0.031，存在约24%的样本外衰减，但方向未反转。

## Strength

> G1-G5收益具有较明显单调性，说明信号并非仅依赖极端股票。

## Concern

> 金融行业Rank IC明显高于其他行业，可能存在行业暴露残留。

## Suggested Test

> 建议测试：
>
> 1. 增强行业中性化；
> 2. 对20D / 40D / 60D持有期进一步比较；
> 3. 增加交易成本敏感性分析。

每个建议旁：

**Run Suggested Test**

---

# 27. Factor Decision Gate

测试之后必须进行人工决策。

按钮：

- **Approve**
- **Revise**
- **Reject**

---

# 28. Approve Factor

点击后填写：

### Decision Note

可选：

> OOS仍保持正IC，分组收益单调性较好，接受进入因子池。

保存：

- Factor；
- Version；
- Approver；
- Date；
- Experiment ID；
- Decision Note。

状态：

`Approved`

自动进入：

**Factor Library**

---

# 29. Reject Factor

必须记录原因。

预设：

- Weak IC；
- Poor robustness；
- High turnover；
- Economic rationale unclear；
- Data quality issue；
- OOS decay；
- High correlation with existing factor；
- Unstable across universes；
- Other。

支持补充文字。

---

# 30. Revise Factor

点击后：

进入Change Proposal页面。

例如：

```text
Factor v1.0

Proposed Changes

Lookback
60D → 40D

Neutralization
Industry → Industry + Size

Unchanged
Raw data
Factor direction
Rebalance frequency
Universe
```

点击：

**Create v1.1**

新版本创建。

v1.0永久保留。

---

# 31. Factor Library

展示所有研究因子。

---

## 31.1 表格

| Factor | Version | Category | ICIR | OOS IC | Turnover | Status |
|---|---|---|---:|---:|---:|---|
| Analyst Revision | v1.1 | Fundamental | 0.64 | .033 | 39% | Approved |
| 12M Momentum | v2.0 | Momentum | 0.72 | .041 | 46% | Approved |
| ROE Quality | v1.3 | Quality | 0.55 | .029 | 18% | Approved |
| Short Reversal | v1.0 | Technical | .21 | -.004 | 78% | Rejected |

---

## 31.2 Filter

支持：

- Approved；
- Rejected；
- Draft；
- Category；
- Creator；
- Date。

---

# 32. Factor Detail

点击因子进入：

### Overview

### Formula

### Economic Rationale

### Versions

### Experiments

### Sensitivity

### Decisions

### Data Lineage

### Related Strategies

---

# 33. Factor Version Timeline

例如：

```text
v1.0
60D Analyst Revision
Rejected
│
└── v1.1
    Added Size Neutralization
    Approved
```

---

# 34. Strategy Lab

第二核心研究页面。

用户创建策略：

> 我想把盈利预测上修、Momentum和ROE结合起来做一个月频多因子策略。

---

# 35. AI生成Strategy Specification

### Strategy Name

**CSI500 Multi-factor Alpha**

---

### Universe

CSI500

---

### Factor Selection

| Factor | Version | Weight |
|---|---|---:|
| Analyst Revision | v1.1 | 30% |
| Momentum | v2.0 | 40% |
| ROE Quality | v1.3 | 30% |

注意：

策略必须绑定：

> Factor Version

而不是Factor Name。

---

# 36. Factor Combination

Demo支持：

- Weighted Z-score；
- Equal Weight；
- Rank Average。

默认：

Weighted Z-score。

---

# 37. Portfolio Construction

| 参数 | 值 |
|---|---|
| Selection | Top 50 |
| Weighting | Equal Weight |
| Rebalance | Monthly |
| Max Single Name | 3% |
| Industry Active Weight | ±5% |
| Turnover Constraint | None |
| Execution | Next-day VWAP |
| Transaction Cost | 10bps |

---

# 38. Strategy Logic Map

页面必须提供高度可视化的策略逻辑。

例如：

```text
                    Analyst Revision v1.1 — 30%
                   /
CSI500 Universe ── Momentum v2.0 ─────── 40%
                   \
                    ROE Quality v1.3 ─── 30%
                              │
                              ▼
                     Weighted Z-score
                              │
                              ▼
                           Ranking
                              │
                              ▼
                           Top 50
                              │
                              ▼
                      Risk Constraints
                              │
                              ▼
                     Monthly Rebalance
                              │
                              ▼
                           Portfolio
```

用户点击任意Factor节点：

打开Factor Definition。

---

# 39. Strategy Pre-run Review

点击：

**Run Backtest**

系统先执行：

## Specification Check

- All factors approved；
- Factor version locked；
- Universe specified；
- Benchmark specified；
- Execution lag specified；
- Cost model specified；
- OOS period defined。

---

# 40. Research Integrity Pre-check

显示：

```text
✓ Point-in-time universe
✓ Financial reporting lag
✓ No future price input
✓ Corporate action adjustment
✓ Execution lag applied
✓ Transaction cost configured
```

如果有错误：

禁止运行。

---

# 41. Backtest Result

顶部：

### Strategy Summary

| Metric | Value |
|---|---:|
| Annualized Return | 14.8% |
| Benchmark Return | 8.2% |
| Excess Return | 6.6% |
| Sharpe | 1.21 |
| Sortino | 1.73 |
| Max Drawdown | -13.8% |
| Calmar | 1.07 |
| Tracking Error | 5.6% |
| Information Ratio | 1.18 |
| Turnover | 73% |

---

# 42. Performance Chart

主图：

**Strategy NAV vs Benchmark**

三条：

- Strategy；
- Benchmark；
- Excess NAV。

必须标注：

- Train；
- Validation；
- OOS。

---

# 43. Drawdown

图：

**Strategy Drawdown**

并突出：

**Maximum Drawdown: -13.8%**

---

# 44. Yearly Return

| Year | Strategy | Benchmark | Excess |
|---|---:|---:|---:|
| 2020 | 21.0% | 16.4% | 4.6% |
| 2021 | 15.8% | 9.1% | 6.7% |
| 2022 | -7.3% | -12.8% | 5.5% |
| 2023 | 9.6% | 3.2% | 6.4% |
| 2024 | 12.1% | 6.0% | 6.1% |

---

# 45. Attribution

Demo提供简化版Factor Contribution：

| Factor | Contribution |
|---|---:|
| Analyst Revision | 32% |
| Momentum | 43% |
| Quality | 25% |

---

# 46. Risk & Trading

展示：

- Turnover；
- transaction cost；
- average holdings；
- max stock weight；
- industry concentration。

---

# 47. Post-run Integrity Check

回测完成后自动运行。

---

# 48. Golden Test

### Tests

| Test | Status |
|---|---|
| Formula Regression | PASS |
| Factor Hash Consistency | PASS |
| Metric Calculation | PASS |
| Point-in-time Test | PASS |
| Look-ahead Test | PASS |
| Universe PIT | PASS |
| Corporate Action Test | PASS |
| Execution Lag | PASS |

---

# 49. Formula Hash

每个Factor Version拥有：

`formula_hash`

Strategy拥有：

`strategy_spec_hash`

Data Snapshot拥有：

`dataset_snapshot_id`

Run拥有：

`engine_version`

完整实验唯一标识：

```text
Factor Spec
+
Strategy Spec
+
Dataset Snapshot
+
Engine Version
+
Research Configuration
=
Backtest Run ID
```

---

# 50. Drift Detection

如果相同输入重新运行结果发生异常变化：

显示：

**Calculation Drift Detected**

例如：

```text
Expected Rank IC:
0.0412

Current Rank IC:
0.0387

Difference:
-6.1%
```

禁止自动覆盖旧结果。

---

# 51. AI Strategy Review

回测完成后AI分析。

结构：

## Performance

> 策略OOS年化超额收益5.8%，Sharpe 1.08，低于完整样本Sharpe 1.21，但仍保持正超额。

## Risk

> 最大回撤-13.8%，主要发生于Momentum因子回撤阶段。

## Concern

> 当前组合年化换手率73%，交易成本对收益影响较明显。

## Suggestion

> 建议增加Turnover Penalty，目标将换手率控制在50%以内，并比较净收益变化。

操作：

**Apply as New Version**

---

# 52. Strategy Change Proposal

如果用户采纳：

```text
Strategy v1.0 → Proposed v1.1

Changed

Turnover Constraint
None → 50%

Unchanged

Universe
CSI500

Factors
Analyst Revision v1.1
Momentum v2.0
ROE Quality v1.3

Factor Weights
30% / 40% / 30%

Rebalance
Monthly
```

用户Confirm后：

`Create Strategy v1.1`

---

# 53. Strategy Decision Gate

与Factor完全一致：

- Approve；
- Revise；
- Reject。

---

# 54. Strategy Registry

表：

| Strategy | Version | OOS Sharpe | Max DD | Turnover | Status |
|---|---|---:|---:|---:|---|
| Multi-factor Alpha | v1.0 | 1.02 | -15.6% | 73% | Revised |
| Multi-factor Alpha | v1.1 | 1.11 | -13.8% | 49% | Approved |
| Quality Momentum | v2.0 | .86 | -17.3% | 54% | Rejected |

---

# 55. Strategy Detail

Tab：

- Overview；
- Logic；
- Factors；
- Versions；
- Backtests；
- Metrics；
- Integrity；
- AI Reviews；
- Decisions。

---

# 56. Version Compare

支持：

**Compare v1.0 vs v1.1**

---

## 56.1 Spec Diff

| Parameter | v1.0 | v1.1 |
|---|---|---|
| Turnover Limit | None | 50% |
| Factors | Same | Same |
| Factor Weights | Same | Same |
| Top N | 50 | 50 |

---

## 56.2 Result Diff

| Metric | v1.0 | v1.1 | Change |
|---|---:|---:|---:|
| OOS Sharpe | 1.02 | 1.11 | +0.09 |
| Max DD | -15.6% | -13.8% | +1.8pp |
| Turnover | 73% | 49% | -24pp |
| Excess Return | 6.3% | 5.9% | -0.4pp |

这部分非常重要。

因为研究迭代不是：

> 新版更好。

而应该理解：

> 新版到底牺牲了什么，又改善了什么。

---

# 57. Research History

产品必须记录所有实验。

---

## 57.1 总览

```text
Factors Tested      27
Approved              8
Rejected             14
Under Revision        5

Strategies Tested    12
Approved              3
Rejected              6
Under Revision        3
```

---

# 58. Timeline

例如：

```text
10:32
Created Analyst Revision v1.0

10:41
Ran Factor Test EXP-0238

10:44
AI flagged industry exposure

10:48
Created v1.1

10:53
Ran EXP-0239

11:02
Approved Analyst Revision v1.1

11:16
Created Multi-factor Alpha v1.0

11:23
Backtest BT-0132

11:27
AI flagged high turnover

11:34
Created Strategy v1.1
```

---

# 59. AI Research Memory

AI应该能利用历史研究记录。

例如用户创建一个新因子：

> 用短期反转试一下。

AI提示：

> 当前项目曾在 EXP-0182 测试过5日反转因子，该版本因换手率过高被Reject。当前是否希望：
>
> - 基于原实验继续改进；
> - 创建新的独立研究。

这会成为产品重要差异化能力。

---

# 60. AI角色设计

AI在产品中明确承担四类角色。

---

## 60.1 Translator

自然语言：

> 我觉得ROE持续提升的公司会表现更好。

转换成：

- Hypothesis；
- Formula；
- Parameter；
- Dataset；
- Horizon；
- Expected Direction。

---

## 60.2 Research Assistant

执行：

- Factor test；
- Sensitivity；
- correlation；
- subgroup analysis；
- strategy backtest。

---

## 60.3 Reviewer

主动检查：

- OOS decay；
- industry exposure；
- size exposure；
- instability；
- turnover；
- concentration；
- overfitting risk。

---

## 60.4 Ideation Partner

提供：

> 下一步可以尝试什么？

但不自动执行。

---

# 61. AI不可执行事项

AI不得：

1. 自动Approve；
2. 偷改Research Configuration；
3. 偷改Strategy；
4. 偷换Factor Version；
5. 改交易成本改善结果；
6. 通过修改OOS区间优化Sharpe；
7. 自动覆盖失败实验；
8. 删除失败记录；
9. 将LLM生成数字作为回测结果；
10. 绕过Integrity Check。

---

# 62. AI输出证据原则

所有研究结论必须：

**Evidence-linked**

例如：

错误：

> 因子表现稳定。

正确：

> Rank IC在Train / Validation / OOS分别为0.041 / 0.036 / 0.031，虽然样本外衰减24%，但三个阶段均保持正值。

UI支持点击数字跳到对应图表。

---

# 63. 页面信息架构

一级导航：

```text
Workspace
│
├── Overview
├── Research Setup
├── Factor Lab
├── Factor Library
├── Strategy Lab
├── Strategy Registry
└── Research History
```

---

# 64. 全局页面布局

推荐 Desktop：

```text
┌─────────────────────────────────────────────────────────┐
│ Project / Research Context                              │
├──────────────┬───────────────────────────────┬───────────┤
│ Navigation   │ Main Research Workspace       │ AI Copilot│
│              │                               │           │
│              │                               │           │
│              │                               │           │
└──────────────┴───────────────────────────────┴───────────┘
```

比例：

- Left nav：15%
- Main：60%
- AI：25%

AI面板可收起。

---

# 65. AI Copilot设计

AI面板顶部需要明确：

### Context

```text
Currently reviewing:
Analyst Revision v1.1
Experiment EXP-0239
```

避免用户不知道AI回答基于哪个版本。

---

# 66. AI操作类型

AI回复中可以产生Action Card：

### Suggested Experiment

**Test transaction-cost sensitivity**

Parameters:

- 5bps
- 10bps
- 20bps

按钮：

`Review Test`

而不是：

`Run`

需要用户确认。

---

# 67. Demo完整故事线

Demo只讲一条主故事。

---

## Step 1：Create Project

项目：

**CSI500 Multi-factor Alpha Research**

---

## Step 2：Configure Research

设置：

- Universe：CSI500
- Benchmark：CSI500
- 2015–2025
- Train：2015–2021
- Validation：2022–2023
- OOS：2024–2025
- Monthly
- T+1
- 10bps

---

## Step 3：提出因子

用户：

> 分析师盈利预测持续上修的公司是不是未来一个月会更强？

---

## Step 4：AI定义因子

AI生成：

Analyst EPS Revision v1.0

并解释：

- Formula；
- rationale；
- data；
- horizon。

---

## Step 5：Run Factor Test

得到：

- IC；
- ICIR；
- G1-G5；
- Long-short；
- Sensitivity。

---

## Step 6：AI发现问题

AI：

> 金融行业暴露明显，建议增加Industry + Size Neutralization。

---

## Step 7：创建v1.1

用户批准修改。

重新运行。

---

## Step 8：Approve Factor

进入Factor Library。

---

## Step 9：创建Strategy

选择：

- Analyst Revision；
- Momentum；
- Quality。

---

## Step 10：Strategy Logic

展示完整策略流程。

---

## Step 11：Run Backtest

输出：

- NAV；
- Sharpe；
- Sortino；
- Drawdown；
- turnover。

---

## Step 12：Integrity Check

全部PASS。

---

## Step 13：AI建议

> Turnover偏高。

建议加入：

50% Turnover Constraint。

---

## Step 14：创建Strategy v1.1

重新回测。

---

## Step 15：Compare

展示：

v1.0 vs v1.1。

---

## Step 16：Approve Strategy

进入Strategy Registry。

---

## Step 17：Research History

展示整个研究链条。

Demo闭环结束。

---

# 68. Demo中必须体现的核心Moment

整个Demo最重要的不是“曲线涨得很好”。

而是以下七个Moment：

### Moment 1

AI把自然语言投资想法转成严谨Factor Spec。

### Moment 2

用户看得见公式和经济意义。

### Moment 3

AI指出研究风险，但不替用户做决定。

### Moment 4

用户批准修改后生成新版本，而不是覆盖旧版本。

### Moment 5

Factor被正式Approve后进入Factor Library。

### Moment 6

Backtest结束后系统用确定性规则做Integrity Check。

### Moment 7

Research History完整保留所有成功及失败尝试。

如果七点全部体现，Demo就能明显区别于普通“聊天式量化工具”。

---

# 69. 数据模型

## Factor

```text
factor_id
factor_name
category
description
created_by
created_at
```

---

## FactorVersion

```text
factor_version_id
factor_id
version
hypothesis
formula
formula_hash
raw_fields
direction
lookback
horizon
winsorization
standardization
neutralization
missing_policy
status
created_at
parent_version
```

---

## FactorExperiment

```text
experiment_id
factor_version_id
research_config_id
dataset_snapshot_id
engine_version
start_time
end_time
status
metrics
integrity_result
```

---

## ResearchDecision

```text
decision_id
object_type
object_version_id
decision
reason_code
note
user_id
timestamp
```

---

## StrategyVersion

```text
strategy_version_id
strategy_id
version
universe
benchmark
factor_versions
factor_weights
combination_method
selection_rule
weighting_method
rebalance
execution
cost
risk_constraints
strategy_hash
parent_version
```

---

## BacktestRun

```text
backtest_id
strategy_version_id
research_config_id
dataset_snapshot_id
engine_version
metrics
nav
benchmark_nav
drawdown
turnover
attribution
integrity_result
```

---

# 70. 量化引擎要求

Demo即使使用Mock数据，也必须体现正确的工程边界。

系统架构逻辑：

```text
              User
                │
                ▼
             AI Layer
          ┌────────────┐
          │ Hypothesis │
          │ Explanation│
          │ Suggestions│
          └────────────┘
                │
                ▼
       Structured Research Spec
                │
                ▼
       Deterministic Quant Engine
     ┌────────────────────────────┐
     │ Factor Engine              │
     │ Backtest Engine            │
     │ Metric Engine              │
     │ Validation Engine          │
     └────────────────────────────┘
                │
                ▼
            Results
                │
          ┌─────┴─────┐
          ▼           ▼
        UI        AI Interpretation
```

AI不得直接输出伪造回测数据作为正式Result。

---

# 71. Integrity Rules

必须包含：

## Data

- Point-in-time data；
- PIT index constituents；
- announcement date；
- delisted securities；
- corporate action adjustment。

---

## Signal

保证：

```text
Signal Timestamp <= Decision Timestamp
```

---

## Execution

保证：

```text
Decision t
→
Trade >= t+1
```

---

## Metrics

所有关键指标来源于Metric Library。

---

# 72. Metric Library

Demo封装：

### Return

- Total Return
- Annualized Return
- Excess Return

### Risk

- Volatility
- Maximum Drawdown

### Risk Adjusted

- Sharpe
- Sortino
- Calmar

### Benchmark

- Alpha
- Beta
- Tracking Error
- Information Ratio

### Trading

- Turnover
- Transaction Cost

### Factor

- IC
- Rank IC
- ICIR
- Positive IC Ratio
- Quantile Return
- Long-short Return

---

# 73. 前视偏差控制

系统需要显式体现：

### PIT Data

使用：

> 当时真实可获得的信息。

而不是当前数据库最终值。

---

### Financial Statement

数据可使用日期：

```text
Available Date
=
Announcement Date
+
Configured Lag
```

不是：

Period End Date。

---

### Index Constituents

必须使用历史成分股。

而不是：

今天CSI500成员倒推十年。

---

# 74. OOS保护机制

建议产品设计：

OOS默认：

**Locked**

进入OOS之前提醒：

> Once unlocked, OOS results should not be used for further parameter tuning.

第一次打开：

`Unlock OOS`

记录事件。

后续如果继续调参：

AI提示：

> 当前版本已观察过OOS结果。继续参数优化可能导致test-set leakage。

这是非常有专业感的功能。

---

# 75. 审计日志

任何重要动作记录：

```text
User
Timestamp
Action
Before
After
Reason
```

包括：

- 修改参数；
- Run；
- Approve；
- Reject；
- Apply AI Suggestion；
- Unlock OOS。

---

# 76. 权限

Demo只需：

### User

可：

- Create；
- Edit Draft；
- Run；
- Approve；
- Reject。

未来企业版可以扩展：

- Researcher；
- Reviewer；
- PM；
- Admin。

---

# 77. 核心交互原则

## Change Preview

任何AI引起的修改必须先Preview。

---

## Diff-first

版本升级必须优先展示：

**What changed**

---

## Decision Required

关键节点明确等待人工决策。

---

## Persistent Context

Research Context始终可见。

---

## Drill-down

所有指标支持从：

Summary → Data Table → Methodology

逐层查看。

---

# 78. Demo视觉方向

产品气质：

- Institutional；
- Professional；
- Scientific；
- Calm；
- Dense but structured。

避免：

- 夸张AI光效；
- 过度聊天机器人UI；
- “AI Magic”风格；
- 游戏化Sharpe；
- 花哨渐变。

更接近：

> Bloomberg / Linear / Datadog / institutional research terminal

与AI Copilot结合。

---

# 79. 页面优先级

## P0

必须完成：

1. Research Setup
2. Factor Lab
3. Factor Diagnostics
4. Factor Decision
5. Factor Library
6. Strategy Lab
7. Backtest
8. Strategy Decision
9. Strategy Registry
10. Research History
11. AI Copilot
12. Version Diff
13. Integrity Check

---

## P1

增强：

- Sensitivity Heatmap；
- Factor correlation；
- Attribution；
- OOS Lock；
- Data Lineage；
- Version Timeline。

---

## P2

未来：

- Portfolio optimizer；
- Risk model；
- Live trading；
- Collaboration；
- Comments；
- Approval workflow；
- Internal factor marketplace。

---

# 80. Demo成功标准

用户看完Demo后，应明确感受到：

### 1.

“AI不是在随便写代码，而是在按照研究规范工作。”

### 2.

“我始终知道当前因子怎么算。”

### 3.

“我知道AI改了什么。”

### 4.

“回测结果不是AI编出来的。”

### 5.

“失败的实验也会留下。”

### 6.

“策略任何版本都可以复现。”

### 7.

“AI在帮助我研究，但最终决策权仍然在人。”

---

# 81. Demo验收标准

## Research Setup

- [ ] 可配置Universe
- [ ] 可配置Benchmark
- [ ] 可配置Research Period
- [ ] 可划分Train / Validation / OOS
- [ ] 可配置Transaction Cost
- [ ] Research Context持续显示

---

## Factor

- [ ] 用户可自然语言提出因子
- [ ] AI生成Hypothesis
- [ ] AI生成Factor Formula
- [ ] 用户可查看完整Calculation Definition
- [ ] 可运行Factor Test
- [ ] 输出IC / ICIR
- [ ] 输出G1-G5
- [ ] 输出G5-G1
- [ ] 输出Sensitivity
- [ ] AI输出Research Review
- [ ] 用户可以Approve / Revise / Reject
- [ ] Revise产生新版本
- [ ] Approved Factor进入Library

---

## Strategy

- [ ] 可选择Approved Factors
- [ ] 因子必须绑定Version
- [ ] 可设置Factor Weight
- [ ] 可设置Portfolio Rule
- [ ] 显示Strategy Logic Map
- [ ] Run之前显示Pre-run Check
- [ ] 输出NAV
- [ ] 输出Benchmark
- [ ] 输出Sharpe
- [ ] 输出Sortino
- [ ] 输出Max Drawdown
- [ ] 输出Turnover
- [ ] 输出Integrity Check
- [ ] AI提供Review
- [ ] 用户Approve / Revise / Reject
- [ ] Strategy支持Version Diff

---

## Research History

- [ ] 所有Factor Experiment有记录
- [ ] 所有Backtest有记录
- [ ] Reject原因被保存
- [ ] AI建议有记录
- [ ] 参数修改有记录
- [ ] 可以查看历史版本

---

# 82. 产品核心指标

Demo阶段可以暂不做真实埋点，但正式产品建议观察：

## Activation

**Research Project → First Factor Test Completion Rate**

---

## Research Efficiency

用户提出假设到第一次有效Factor Test的时间。

---

## AI Adoption

AI建议中：

`Apply Suggestion Rate`

---

## Reproducibility

历史Experiment：

`Successful Re-run Rate`

目标：

100%。

---

## Research Memory Value

重复研究减少比例。

---

## AI Trust

用户查看：

- Formula；
- Data Lineage；
- Integrity Check；
- Version Diff

的使用率。

这些行为越高，不一定说明产品复杂，反而可能说明系统在建立专业用户信任。

---

# 83. 核心风险

## Risk 1：产品变成ChatGPT + Backtest

解决：

Research Object必须占据UI主体。

---

## Risk 2：AI建议过多

解决：

AI输出分层：

- Critical；
- Observation；
- Suggestion。

避免每一步都说十条。

---

## Risk 3：指标太专业导致Demo难理解

解决：

默认Summary。

Advanced用户点击：

`View Details`

---

## Risk 4：Mock结果看起来不可信

解决：

所有Demo数据内部保持数学一致。

例如：

- IC；
- ICIR；
- Quantile Return；
- NAV；
- Sharpe；
- Max DD；

不能互相矛盾。

---

## Risk 5：Demo追求高Sharpe

不要设计成：

“AI优化到Sharpe 2.8”。

更可信的是：

```text
v1.0 Sharpe 1.02
↓
降低Turnover
↓
v1.1 Sharpe 1.11
```

改善合理、有限且有解释。

---

# 84. 推荐Demo Seed Data

建议预置三个Approved Factors。

### Analyst Revision

Category：

Fundamental

---

### 12M Momentum

Category：

Momentum

---

### ROE Quality

Category：

Quality

---

用户现场创建：

**Analyst Revision v1.0**

经过一次改进变：

**v1.1**

然后与另外两个预置Factor组成策略。

这样既有现场AI体验，又不会让Demo流程过长。

---

# 85. 首页Overview

推荐首页：

### Active Project

CSI500 Multi-factor Alpha

### Research Progress

```text
8 Approved Factors
14 Rejected Factors
3 Approved Strategies
27 Experiments
```

### Recent Research

显示最近5个Experiment。

### AI Research Brief

AI：

> 当前项目最近三个实验均集中在降低Momentum策略换手率。Strategy v1.1已将Turnover从73%下降到49%，且OOS Sharpe由1.02提升到1.11。

按钮：

`Continue Research`

---

# 86. 产品一句话定义

> **Quant Research Copilot 是一个让人类研究员与AI共同完成量化研究的透明、可复现、可审计工作台。**

---

# 87. 产品核心差异化

传统量化工具强调：

> Run Backtest.

普通AI Quant产品强调：

> Generate Strategy.

本产品强调：

> **Build Research Evidence.**

不是：

**“AI替你投资。”**

而是：

**“AI和你一起做严谨的投资研究。”**

---

# 88. 最终产品飞轮

长期来看，产品真正积累的不是聊天记录，而是：

```text
Research Hypotheses
        ↓
Factor Definitions
        ↓
Experiments
        ↓
Evidence
        ↓
Decisions
        ↓
Factor Library
        ↓
Strategies
        ↓
Backtests
        ↓
Research History
        ↓
Institutional Research Memory
        ↓
Better AI Research Suggestions
```

最终形成：

> **Institution-specific Quant Research Memory**

即属于这家机构自己的：

- 因子知识库；
- 实验库；
- 失败研究库；
- 策略库；
- 决策记录；
- 研究偏好；
- AI Research Context。

这会成为产品长期最有价值的数据资产和护城河。

---

# 89. Demo最终体验目标

用户完成一次完整流程之后，应产生明确感知：

> “我不是让AI替我随机寻找高Sharpe策略，而是在一个严谨的研究系统中与AI协作。AI理解我的投资假设，能把它转换成准确的研究定义，帮助我做实验、看证据、发现问题和迭代；与此同时，我始终清楚每一个数字从哪里来、每一个版本改了什么、哪些结果被采用、哪些研究失败过。我仍然拥有最终研究判断权。”

这就是本产品Demo最核心的产品体验。
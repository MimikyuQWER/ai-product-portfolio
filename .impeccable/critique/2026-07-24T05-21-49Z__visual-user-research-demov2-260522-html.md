---
target: "D:/就业学习资料包251116/秋招AI产品项目/visual_user_research/虚拟人demoV2 260522.html"
total_score: 23
p0_count: 2
p1_count: 2
timestamp: 2026-07-24T05-21-49Z
slug: visual-user-research-demov2-260522-html
---
# 设计审查报告：虚拟用户访谈平台 v2

**Method**: dual-agent (A: a021272d8ecbf33ca · B: a9f1dcc1f7247ccae)
**Target**: D:\就业学习资料包251116\秋招AI产品项目\visual_user_research\虚拟人demoV2 260522.html
**Date**: 2026-07-24

## 设计健康评分

| # | Heuristic | 评分 | 关键问题 |
|---|-----------|------|----------|
| 1 | Visibility of System Status | 3/4 | AI 响应无 loading 状态，180ms 假延迟破坏真实感 |
| 2 | Match System / Real World | 3/4 | 聊天 UI 符合直觉，「原文概括」「推演回答」概念新颖但需引导 |
| 3 | User Control and Freedom | 2/4 | 无撤销发送、离开聊天无确认、聊天历史不持久 |
| 4 | Consistency and Standards | 3/4 | 面板/按钮/标签体系一致，但 filter 和 apply 命名歧义 |
| 5 | Error Prevention | 1/4 | 问题路由仅匹配 3 组关键词，其余静默 fallback 到通用回答 |
| 6 | Recognition Rather Than Recall | 3/4 | 快捷问题按钮、侧边栏辅助信息好；但 profile placeholder 为空 |
| 7 | Flexibility and Efficiency of Use | 2/4 | 有 Enter 发送+快捷按钮，但无键盘快捷键、无批量操作 |
| 8 | Aesthetic and Minimalist Design | 3/4 | 配色克制专业，间距一致；profile placeholder 破坏整体质感 |
| 9 | Error Recovery | 1/4 | 整个界面零错误处理，无任何错误消息或恢复路径 |
| 10 | Help and Documentation | 2/4 | 侧边栏有推荐路径说明，但无 tooltip、无帮助入口 |
| **Total** | | **23/40** | **Acceptable — 需显著改进** |

## Anti-Patterns 判定

**LLM 评估: CLEAN** — 避开了绝大多数 AI 生成模板的标志性特征（无 gradient text、side-stripe borders、编号 section markers、过度圆角）

**Detector Scan**: 1 个 false positive（`dark-glow` on `.user-card.active` — 实际是浅色主题的选中高亮阴影）

**技术审计额外发现**: 3 个假输入框（div-as-input）、全站零 focus 指示器、Modal 无 focus trap/ARIA

## 整体印象

有野心的产品原型。核心创新点（区分「原文概括」与「推演回答」、可展开的推理链路）在同类工具中很少见。视觉基础扎实——配色克制、间距统一、三视图结构清晰。目前停留在「可演示」而非「可用」阶段。

## 做得好的地方

1. **推理过程透明化设计**：可展开的「本轮用户思考过程」面板是产品最有区分度的功能，结构化展示 prompt grid/evidence/reasoning chain
2. **配色系统的克制**：7 个 CSS 变量定义完整语义色彩体系，四色标签方案清晰区分维度
3. **三视图信息架构**：Home→Profile→Chat 渐进式导航符合研究访谈工作流

## 优先级问题

### [P0] 假输入框是最危险的 affordance
.search-box、.assistant-input 样式与真正输入框完全相同，但实际是不可交互的 <div>

### [P0] 聊天问题路由静默失败
getReply() 仅匹配 3 组关键词，其余静默返回通用回答，用户完全不知道

### [P1] Profile 页面 placeholder 严重损害信任
四个空 block 全是「字段接口预留」——demo 中最不该出现的文本

### [P1] 对比度系统性不足
10/16 检测色对未通过 AA，最差的仅 3.19:1；chip.active 状态对比度反比非活跃态更差

### [P2] 组件状态不完整
按钮缺 :active/:focus-visible/:disabled，Modal 缺 focus trap/Escape/role="dialog"

## Persona 红标

- **Alex (效率型研究者)**: 无键盘快捷键、无批量操作、离开聊天丢失对话——高流失风险
- **Jordan (首次使用 PM)**: 点搜索框不能输入、点筛选无反应、看到 placeholder 怀疑产品——第 3 步放弃
- **Sam (键盘/屏幕阅读器)**: 全站无 focus-visible、Modal 无 focus trap、消息区无 aria-live——无法完成核心任务

## 小观察

- 搜索框/筛选器不与实际数据联动，但 UI 暗示它们能工作
- .btn:hover transform 被 .app-shell overflow:hidden 裁剪
- min-height:820px 在笔记本屏幕强制滚动
- contenteditable div 做聊天输入不如 <textarea> 可靠
- 「应用筛选」按钮实际只调用了 highlightCard()，没有过滤逻辑

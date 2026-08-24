# 张逸帆 · AI 产品作品集

复旦大学 2026 届硕士，求职方向为 AI 产品经理。作品集包含两项在实习团队实际使用的 AI 产品，以及两项个人工程项目；重点呈现我如何识别业务瓶颈、把人的判断标准转译为 AI 工作流，并通过评测、审计、溯源和安全降级提高结果可靠性。

**[打开在线作品集总览](https://mimikyuqwer.github.io/ai-product-portfolio/portfolio/index.html)**

## 推荐浏览路线

| 项目 | 先看什么 | 如何体验 |
|---|---|---|
| 01 · 虚拟用户访谈平台 | [项目介绍页](https://mimikyuqwer.github.io/ai-product-portfolio/visual_user_research/landing.html) | [打开交互 Demo](https://mimikyuqwer.github.io/ai-product-portfolio/visual_user_research/虚拟人demoV7.html)，无需安装 |
| 02 · 地址信息审核 Agent | [项目演示页](https://mimikyuqwer.github.io/ai-product-portfolio/address-audit-agent/landing.html) | 在线看完整流程；本地应用按 [README](address-audit-agent/README.md) 启动 |
| 03 · 每日 AI 资讯日报 | [在线体验 Demo](https://mimikyuqwer.github.io/ai-product-portfolio/daily-news-demo/) | 浏览、编辑、撤销、恢复和导出均可直接体验 |
| 04 · 本地结构化知识库 | [架构与工程说明](knowledge-wiki-system/README.md) | 阅读 [设计思路](knowledge-wiki-system/设计思路详解.md)、[Schema](knowledge-wiki-system/SCHEMA.md) 与 [脱敏样例](knowledge-wiki-system/samples/README.md) |

## 01 · 虚拟用户访谈平台

在米哈游原神国际化用户研究场景中，用回收的访谈结果与 BI 数据为真实受访者建立 AI 数字分身。专业用研团队调教分析 Skill、产出中间层研报，业务方和管理层可以直接向数字分身发起对话，获取一手用户洞察。

核心设计包括三级回答体系（原文可答、证据可推演、证据不足直说不编造）、端到端与过程评测体系，以及独立审计 Agent。项目基于真实玩家数据建模，已作为访谈前的情景预演工具在用研团队实际使用。公开 Demo 已脱敏。

## 02 · 地址信息审核 Agent

面向微信支付等金融法律 KYC 场景，把审核员原本逐条使用地图和搜索引擎核验地址的流程，重构为 LLM + 高德地图 + 联网搜索三重交叉验证的 ReAct Agent。项目从提示词实验迭代为完整审核系统，准确率由约 80% 提升到约 95%，单条审核效率提升约 3 倍。

设计重点不是让模型直接给结论，而是先输出预审报告：展示数据摘要、完整度、明显无效项与待补信息，用户确认后才调用外部工具。最终依据 5 条量化标准输出可追溯审核报告。项目已在腾讯金融业务团队作为客户 KYC 审核辅助工具实际使用；公开版本仅含脱敏样例。

## 03 · 每日 AI 资讯日报

将 RSS 与网站信息源的抓取、字段标准化、去重、正文清洗、图片本地化和 AI 中文摘要连接成完整链路，最终形成每天 5–10 分钟可以读完的结构化日报。作品集公开 18 个固定内容快照与 401 张本地新闻图片，以稳定复现优先。

在线版可以直接切换日期、阅读目录、编辑 Markdown、保存浏览器草稿、撤销 / 重做、恢复原始快照，并导出 Markdown 或独立 HTML。AI 润色属于可选的本地能力：基础体验不需要 API Key，也不会覆盖固定快照。

本地运行：

```powershell
cd daily-news-main/demo
npm install
npm run demo
```

启动后访问 `http://127.0.0.1:4173`。直接双击源码目录中的 `index.html` 会显示启动提示，而不是空白页。

## 04 · 本地结构化知识库系统

159 页 Markdown，覆盖量化金融与 AI 产品两个领域。系统不是笔记堆砌，而是由数据流入层、结构化层和检索层组成的工程体系：素材经过去重和质量检查进入只读原始层，再按 Entity / Judgment / Pattern / Observation 四类 Schema 沉淀，并通过索引、wikilink、时效标记和渐进式披露供 AI 检索。

核心约束是每条事实性陈述必须可溯源到原文；不确定内容标记“待补充”，不允许用常识填空。仓库公开架构文档、同步与入库脚本以及四类脱敏样例，不包含个人知识正文、账号凭证或金融数据配置。

## 仓库边界

- 两个实习项目均已脱敏，保留产品逻辑、交互与可靠性设计。
- AI 日报在线版使用固定快照；抓取器、数据库、调度器和发布账号不在公开 Demo 中。
- 知识库仅公开工程规范、工具与脱敏样例。
- 需要模型、地图或搜索服务的完整能力，均由使用者在本地自行配置密钥。

---

© 2026 张逸帆 · 复旦大学 · AI 产品作品集

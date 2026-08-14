# 张逸帆 · AI 产品作品集

> **🌐 在线体验 → [mimikyuqwer.github.io/ai-product-portfolio](https://mimikyuqwer.github.io/ai-product-portfolio/)**
>
> 点击上方链接即可查看作品展示页，无需克隆仓库。

[![Portfolio](https://img.shields.io/badge/🎯_作品展示页-在线体验-2563eb)](https://mimikyuqwer.github.io/ai-product-portfolio/)
[![VUR Demo](https://img.shields.io/badge/🎭_虚拟用户访谈-秒开体验-15803d)](https://mimikyuqwer.github.io/ai-product-portfolio/visual_user_research/%E8%99%9A%E6%8B%9F%E4%BA%BAdemoV7.html)

复旦大学 · 腾讯微信支付风控 + 米哈游原神国际化 实习期间完成的 AI 产品项目。

---

## 🎭 虚拟用户访谈平台

**米哈游 · 原神国际化用户研究** | 纯前端单文件 · 离线可用 · 无需部署

用 28 位基于真实玩家数据建模的 AI 数字分身，替代传统跨国用户访谈的排期瓶颈。

| 入口 | 说明 |
|------|------|
| [🌐 在线体验 Demo](https://mimikyuqwer.github.io/ai-product-portfolio/visual_user_research/%E8%99%9A%E6%8B%9F%E4%BA%BAdemoV7.html) | GitHub Pages 直接打开，秒开即用 |
| [📄 产品介绍页](https://mimikyuqwer.github.io/ai-product-portfolio/visual_user_research/landing.html) | 三级回答体系 + 品质保障设计 |

---

## 📍 地址信息审核 Agent

**腾讯 · 微信支付 KYC 风控** | Python + Streamlit · ReAct Agent

LLM + 高德地图 + 联网搜索三重交叉验证，单条地址审核效率提升约 3 倍，准确率约 95%。

```bash
cd address-audit-agent
pip install -r requirements.txt
python -m streamlit run app.py
# 🔑 高德地图 Key 已预配，你只需填入自己的 DeepSeek/OpenAI API Key
```

| 入口 | 说明 |
|------|------|
| [📄 产品介绍页](https://mimikyuqwer.github.io/ai-product-portfolio/address-audit-agent/landing.html) | 架构图 + 审核五标准 + 效果对比 |
| [📖 完整文档](address-audit-agent/README.md) | 快速开始 + Agent 架构 + 部署指南 |
| [📋 迭代记录](address-audit-agent/SPEC.md) | 每次重大变更的可追溯记录 |

---

## 📰 每日 AI 资讯聚合系统

**PrismFlowAgent（流光）** | Node.js + React + Fastify · Docker 部署

基于 RSS 订阅 + AI 摘要的每日资讯自动生成与推送系统。

```bash
cd daily-news-main
npm install && npm --prefix frontend install
JWT_SECRET=local-dev-secret PORT=3456 npm run dev
```

---

## 🚀 面试官快速体验

| 项目 | 体验方式 | 时间 |
|------|----------|------|
| 虚拟用户访谈 | [在线秒开](https://mimikyuqwer.github.io/ai-product-portfolio/visual_user_research/%E8%99%9A%E6%8B%9F%E4%BA%BAdemoV7.html) | 0 秒 |
| 地址审核 Agent | `pip install` + `streamlit run`（需 Python） | 2 分钟 |
| 每日 AI 资讯 | `npm install` + Docker | 10 分钟 |

---

张逸帆 · 复旦大学 · 2026

---

## 🤖 AI 开发基础设施

### Claude Code Skills — 日常 AI 协作的工程底座

在以上项目开发过程中沉淀了 **6 个自建 Claude Code Skill**，覆盖量化投资、AI 产品开发、知识库管理三个领域。每个 Skill 本质是一套结构化的行为约束——定义 AI 在特定场景下该做什么、不该做什么、如何验证——确保 AI 输出可复现、可溯源。

| Skill | 领域 | 一句话 |
|-------|------|--------|
| [factor-backtest](skills/factor-backtest/SKILL.md) | 量化投资 | 因子研究→回测→版本管理完整链路，统一计算口径，不可变结果存档 |
| [cn-investment-research](skills/cn-investment-research/SKILL.md) | 量化投资 | A股/债券/衍生品投研分析，AKShare+iFinD 双数据源，中金研报格式 |
| [harness-engineering](skills/harness-engineering/SKILL.md) | AI 产品 | Agent 集群设计 + Context 工程 + 评测体系，来自米哈游实战 + 官方实践 |
| [wiki-material-ingest](skills/wiki-material-ingest/SKILL.md) | 知识库 | 研报 PDF/PPTX 双工具对比择优 → Markdown 入库 |
| [wiki-page-writer](skills/wiki-page-writer/SKILL.md) | 知识库 | 结构化 Wiki 页面编写规范，强制内容溯源反编造 |
| [feishu-qa-detector](skills/feishu-qa-detector/SKILL.md) | 知识库 | 飞书笔记自动检测疑问句，知识库 + 实时数据回答 |

详见 [skills/README.md](skills/README.md)。

### 📚 结构化个人知识库

159 页 Markdown，量化金融 + AI 产品双领域，AI 可检索可维护。飞书知识库每日增量同步 + 研报自动转换入库。渐进式披露设计（大纲索引 → 详情 → 原始材料）让 AI 在 50 行内掌握任意页面骨架。

详见 [knowledge-wiki-system/README.md](knowledge-wiki-system/README.md)。

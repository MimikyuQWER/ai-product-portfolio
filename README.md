# 张逸帆 · AI 产品作品集

> **🌐 在线体验 → [mimikyuqwer.github.io/ai-product-portfolio](https://mimikyuqwer.github.io/ai-product-portfolio/)**
>
> 点击上方链接即可查看作品展示页，无需克隆仓库。

[![Portfolio](https://img.shields.io/badge/🎯_作品展示页-在线体验-2563eb)](https://mimikyuqwer.github.io/ai-product-portfolio/)
[![VUR Demo](https://img.shields.io/badge/🎭_虚拟用户访谈-秒开体验-15803d)](https://mimikyuqwer.github.io/ai-product-portfolio/visual_user_research/%E8%99%9A%E6%8B%9F%E4%BA%BAdemoV7.html)

复旦大学 · 腾讯微信支付风控 + 米哈游原神国际化 实习期间独立完成的 AI 产品项目。

---

## 🎭 虚拟用户访谈平台

**米哈游 · 原神国际化用户研究** | 纯前端单文件 · 离线可用 · 无需部署

用 28 位基于真实玩家数据建模的 AI 数字分身，替代传统跨国用户访谈的排期瓶颈。

| 入口 | 说明 |
|------|------|
| [🌐 在线体验 Demo](https://mimikyuqwer.github.io/ai-product-portfolio/visual_user_research/%E8%99%9A%E6%8B%9F%E4%BA%BAdemoV7.html) | GitHub Pages 直接打开，秒开即用 |
| [📄 产品介绍页](https://mimikyuqwer.github.io/ai-product-portfolio/visual_user_research/landing.html) | 三级回答体系 + 品质保障设计 |
| [📝 迭代文档](visual_user_research/%E8%99%9A%E6%8B%9F%E4%BA%BA%E8%BF%AD%E4%BB%A3%E6%96%87%E6%A1%A3.md) | v2→v7 迭代记录 + 评测体系 |

---

## 📍 地址信息审核 Agent

**腾讯 · 微信支付 KYC 风控** | Python + Streamlit · ReAct Agent

LLM + 高德地图 + 联网搜索三重交叉验证，单条地址审核效率提升约 3 倍，准确率约 95%。

```bash
cd address-audit-agent
pip install -r requirements.txt
streamlit run app.py
# 🔑 DeepSeek + 高德地图 API Key 已预配，克隆后直接运行
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

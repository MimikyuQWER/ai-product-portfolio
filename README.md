# 张逸帆 · AI 产品作品集

[![Portfolio](https://img.shields.io/badge/作品集-HTML-2563eb)](portfolio/index.html)
[![VUR Demo](https://img.shields.io/badge/VUR_Demo-双击即开-15803d)](visual_user_research/%E8%99%9A%E6%8B%9F%E4%BA%BAdemoV7.html)

复旦大学 · 腾讯微信支付风控 + 米哈游原神国际化 实习期间独立完成的两个 AI 产品项目。

> 📄 浏览器打开 [`portfolio/index.html`](portfolio/index.html) 查看完整作品展示页。

---

## 🎭 虚拟用户访谈平台

**米哈游 · 原神国际化用户研究** | 纯前端单文件 · 双击即开

用 28 位基于真实玩家数据建模的 AI 数字分身，替代传统跨国用户访谈的排期瓶颈。覆盖 19 个国家/地区、6 种玩家行为类型，支持一对一访谈、群聊推演、代表用户合成。

```bash
# 无需安装，浏览器直接打开
start visual_user_research/虚拟人demoV7.html
```

| 入口 | 说明 |
|------|------|
| [`landing.html`](visual_user_research/landing.html) | 产品介绍页（三级回答体系 + 品质保障） |
| [`虚拟人demoV7.html`](visual_user_research/%E8%99%9A%E6%8B%9F%E4%BA%BAdemoV7.html) | 完整 Demo（628KB，头像 base64 内嵌，离线可用） |
| [`虚拟人迭代文档.md`](visual_user_research/%E8%99%9A%E6%8B%9F%E4%BA%BA%E8%BF%AD%E4%BB%A3%E6%96%87%E6%A1%A3.md) | v2→v7 迭代记录 + 50+40+10 评测体系 |

---

## 📍 地址信息审核 Agent

**腾讯 · 微信支付 KYC 风控** | Python + Streamlit · ReAct Agent

LLM + 高德地图 + 联网搜索三重交叉验证，将地址审核从人工逐条搜索升级为 AI 并行处理。预审报告机制让用户在 API 调用前确认数据质量，避免无效消耗。效率提升约 3 倍，准确率约 95%。

```bash
cd address-audit-agent
pip install -r requirements.txt
streamlit run app.py
# 浏览器打开 http://localhost:8501
```

| 入口 | 说明 |
|------|------|
| [`landing.html`](address-audit-agent/landing.html) | 项目介绍页（架构图 + 审核五标准 + 效果对比） |
| [`README.md`](address-audit-agent/README.md) | 完整文档（快速开始 + Coze 部署 + Agent 架构） |
| [`SPEC.md`](address-audit-agent/SPEC.md) | 迭代变更记录 |

> 🔑 API Key 已预配 DeepSeek + 高德地图，安装依赖后可直接运行。

---

## 📰 每日 AI 资讯聚合系统

**PrismFlowAgent（流光）** | Node.js + React + Fastify · Docker 部署

基于 RSS 订阅 + AI 摘要的每日资讯自动生成与推送系统。后端 Fastify + TypeScript + SQLite，前端 Vite + React 19 + Tailwind CSS 4。支持飞书/Wave 推送、定时生成、AI 多模型适配。

```bash
cd daily-news-main
npm install && npm --prefix frontend install
JWT_SECRET=local-dev-secret PORT=3456 npm run dev
```

| 入口 | 说明 |
|------|------|
| [`README.md`](daily-news-main/README.md) | 中英文文档 + 本地开发指南 |
| [`每日AI动态聚合系统PRD.md`](daily-news-main/%E6%AF%8F%E6%97%A5AI%E5%8A%A8%E6%80%81%E8%81%9A%E5%90%88%E7%B3%BB%E7%BB%9FPRD.md) | 产品需求文档 |
| [`docker-compose.yml`](daily-news-main/docker-compose.yml) | Docker 一键部署 |

---

## 📁 仓库结构

```
ai-product-portfolio/
├── README.md                          ← 你在这里
├── portfolio/
│   └── index.html                     ← ★ 作品展示主页（面试官入口）
├── visual_user_research/              ← 虚拟用户访谈平台
│   ├── landing.html                   → 产品介绍页
│   ├── 虚拟人demoV7.html              → 完整 Demo
│   └── 虚拟人迭代文档.md              → 迭代记录
├── address-audit-agent/               ← 地址审核 Agent
│   ├── landing.html                   → 项目介绍页
│   ├── app.py                         → Streamlit 主程序
│   ├── agent/                         → ReAct Agent 引擎
│   └── README.md                      → 完整文档
└── daily-news-main/                   ← 每日 AI 资讯
    ├── src/                           → Fastify 后端
    ├── frontend/                      → React 前端
    └── README.md                      → 中英文文档
```

---

## 🚀 面试官快速体验

| 项目 | 门槛 | 时间 |
|------|------|------|
| 虚拟用户访谈 | 双击 HTML 即开 | 0 秒 |
| 地址审核 Agent | `pip install` + `streamlit run` | 2 分钟 |
| 每日 AI 资讯 | `npm install` + Docker | 10 分钟 |

---

张逸帆 · 复旦大学 · 2026

# 地址审核 Agent — 变更记录 (Spec Delta)

> 每次重大功能/架构变更在此记录：日期、变更内容、原因。形成项目的可追溯开发历史。

---

## 2026-07-27: 预审报告机制 + 审核结果展示重构

**变更**：
- `prompt.txt` 对话流程新增步骤 4-5（数据预审报告 + 等待用户确认），禁止在确认前调用外部工具
- `app.py` 对话区渲染统一为摘要 + 面板模式，所有 assistant 消息自动检测审核表格 → 展示统计行 + 📄📥 链接
- 修复 `is_audit` 检测误判（`|:---:|` 格式不匹配 `|---` 子串）、非审核消息误触发面板
- 修复 CSV 上传路径未触发审核面板的问题（消息渲染循环统一处理）

**原因**：节省 API 费用，用户确认后再审核；聊天框内不再裸渲 Markdown 表格

---

## 2026-07-24: 审核明细文件化 + 并行工具调用 + 速度优化

**变更**：
- 审核结果不再内联渲染，改为写 `audit_output/` 目录（MD + CSV），聊天框只放摘要 + 链接
- `agent.py` ReAct 循环工具调用从串行改为 `ThreadPoolExecutor` 并行执行
- `tools.py` geocode 增加内存缓存、CSV 解析去掉 `csv.Sniffer`
- `tools.py` geocode 新增 `map_url` 字段（`ditu.amap.com/search?query=...`）

**原因**：表格溢出无法在 Streamlit 解决；并行调用 geocode+search 节省 ~1.5s/条

---

## 2026-07-23: 反幻觉工程化（ResultGuard）上线

**变更**：
- 新增 `agent/guard.py`：EvidenceCollector + ResultGuard（4 条规则 + 重试机制）
- `agent.py` ReAct 循环返回前调用 Guard，不通过则注入修正指令重试
- 前端 URL 自动渲染为可点击链接 + 审核完成统计面板
- Thread 实时进度方案尝试并回退（不稳定）

**原因**：单靠 Prompt 约束 LLM 行为不可靠，需要程序化验证输出

---

## 2026-07-22: 产品主页 + 新手引导

**变更**：
- 新增 `landing.html`（Geist 字体 + Slate+Gold 配色）
- 新手引导弹窗（三步流程）
- 机器人头像集成
- `app.py` CSS 与 landing 同步

**原因**：需要美观的产品主页用于秋招展示

---

## 2026-07-17: Agent 核心功能完成

**变更**：
- `agent/` 模块搭建（agent/llm/tools）
- 高德地图 geocode + Bing 搜索 web_search + Excel 解析
- ReAct 循环实现
- Streamlit 对话界面
- 五大审核标准 Prompt

**原因**：项目启动，MVP 核心链路

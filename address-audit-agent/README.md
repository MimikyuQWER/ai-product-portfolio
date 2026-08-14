# 📍 地址信息审核助手 (Address Audit Agent)

> AI 驱动的地址真实性验证工具 — 金融风控 KYC、法律文书审核场景

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 项目简介

一个基于大语言模型的 **AI Agent**，能够自动判断中国境内或海外地址的有效性。输入地址文本或上传 Excel 文件，Agent 会通过 **LLM 文本理解 + 高德地图定位 + 联网搜索交叉验证** 三重机制，输出结构化的审核报告。

**适用场景**：金融机构客户身份识别（KYC）、反洗钱（AML）、法律文书审核、企业注册地址核验等。

## ✨ 核心能力

| 能力 | 说明 |
|------|------|
| 🔍 格式检查 | LLM 理解中文地址层级结构，识别虚假/乱填的文本 |
| 🗺️ 地图核验 | 高德地图地理编码 API，精确到门牌号级别 |
| 🌐 联网搜索 | Bing 搜索交叉验证，查找地址在公开信息中的记录 |
| 💬 智能追问 | 信息不完整时主动提问，引导用户补充 |
| 📁 批量处理 | 上传 Excel 表格，逐条审核并汇总报告 |
| 📊 结构化输出 | 批量六列 / 单条五列表格：序号、地址、审核结果、审核依据、审核信息源（含链接）；批量额外含「姓名」列 |
| 🛡️ 反幻觉护栏 | ResultGuard 六条硬规则校验，引用须有真实工具证据，杜绝编造 |
| 📑 审计追踪 | 每轮交互落盘 JSON，记录工具 / 错误码 / 耗时，可一键下载回溯 |

## 🏗️ Agent 架构

```
用户输入（文本 / Excel）
        │
        ▼
┌───────────────────────────────┐
│     Address Audit Agent       │
│                               │
│  System Prompt（审核规则）      │
│       ↓                       │
│  ReAct 循环                   │
│  ┌─ Think（分析地址）          │
│  ├─ Act（调用工具）            │
│  ├─ Observe（观察结果）        │
│  └─ Answer（输出报告）         │
│                               │
│  Tools:                       │
│  ├─ geocode() 高德地图         │
│  ├─ web_search() 联网搜索      │
│  └─ parse_excel() 表格解析     │
│  ResultGuard（校验层）:            │
│  A 证据 B 溯源 C 一致 D 格式      │
│  E 搜索相关性 F 行政区划一致       │
└───────────────────────────────┘
        │
        ▼
审核报告（六列/五列表格 + 信息源链接）
  通过 → 输出 ｜ 不通过 → 补充证据重试
```

### 审核五标准

1. **完整详细** — 地址需包含省→市→区→街道→门牌号 6 级信息
2. **可搜索核实** — 地图/搜索能查到且唯一匹配
3. **定位准确** — 不包含模糊方位词（旁边、对面等）
4. **门牌号准确** — 具体门牌号可在地图查到
5. **特殊建筑豁免** — 知名建筑物即使缺门牌号也认可

### 五类输出结果

- ✅ **有效地址** — 满足全部五项标准
- ❌ **无效地址** — 格式像地址但查不到任何信息
- ⚠️ **不确定** — 部分信息有效但关键信息缺失
- 🚫 **不符合地址格式** — 明显编造的文本
- 🔧 **审核失败** — 地图与搜索工具经重试仍不可用（如限流）时，诚实声明核验中断并给出下一步建议，而非编造结论

## 🛡️ 反幻觉护栏（ResultGuard）

提示词负责"意图"，规则脚本负责"兜底"。Agent 每轮产出都会经过 `agent/guard.py` 的六条硬规则校验，任一违规即要求补充证据或重答，从工程层杜绝编造：

| 规则 | 校验点 |
|------|--------|
| A 证据 | 每条结论须有工具返回佐证，禁止凭空断言 |
| B 溯源 | 引用的链接须来自真实工具返回（高德 / Bing），禁止捏造 URL |
| C 一致 | 结论类别须属五类之一，且与依据吻合 |
| D 格式 | 报告须含"审核依据 / 审核信息源"结构化分段 |
| E 相关 | 联网搜索引用的网页须与地址有关键词重合，否则判违规 |
| F 区划 | 结论省份须与地图核验省份一致，冲突即告警（防张冠李戴） |

## 📑 两段式报告与审计追踪

- **两段式渲染**：数据预审报告留在主对话框（标「📋 第 1 步」，可追问补信息）；终审报告在右侧抽屉弹出（六列明细 + 下载入口），两环节互不干扰。
- **JSON 审计追踪**：每轮交互落盘 `outputs/audit_trace_{session}_{ts}.json`，记录每一步调用的工具、原始返回、错误码（如高德限流 `infocode=10021`）、是否降级、耗时毫秒。可在报告页一键下载，作为 KYC/AML 场景的"证据链"。

## ⚙️ 生产级可靠性

- 重试 ≤3 次（指数退避）+ 降级链：高德 → 联网搜索 → 审核失败。
- 联网搜索 4 级回退：Bing API → Bing 国内版 → 百度 → DuckDuckGo 兜底。
- 批量分块（5 条/批）逐批渲染，界面永不冻结。
- 设计细节与界面示意见 [`landing.html`](landing.html)。

## 🚀 快速开始（Windows）

> 以下所有命令都在 **PowerShell** 中执行：按下 `Win` 键，输入 `powershell`，回车即可打开。

### 准备工作（只需做一次）
1. **安装 Python 3.10 或更高版本**：访问 https://www.python.org/downloads/ 下载安装包，**安装时务必勾选 “Add Python to PATH”**，其余一路下一步。
2. **获取一个 AI API Key（二选一即可）**：
   - DeepSeek：https://platform.deepseek.com/ 注册后「新建 API Key」
   - OpenAI：https://platform.openai.com/ 注册后获取 Key
   > 高德地图 Key 已内置在配置模板中，无需你申请。

### 第一步：下载代码
在 PowerShell 中输入：
```powershell
git clone https://github.com/MimikyuQWER/ai-product-portfolio.git
cd ai-product-portfolio/address-audit-agent
```

### 第二步：安装依赖
在 PowerShell 中输入：
```powershell
pip install -r requirements.txt
```
看到 `Successfully installed ...` 即成功。若提示 `pip` 不是命令，说明 Python 没勾选 PATH，请重新安装并勾选。

### 第三步：填入你自己的 AI API Key
在 PowerShell 中输入：
```powershell
copy .env.example .env
notepad .env
```
在打开的记事本里，把这一行：
```
LLM_API_KEY=替换为你的Key
```
改成你自己的真实 Key（例如 `LLM_API_KEY=sk-xxxx`），**保存并关闭记事本**。其余配置保持不动。

### 第四步：启动应用
在 PowerShell 中输入：
```powershell
python -m streamlit run app.py
```
启动后浏览器会自动打开 `http://localhost:8501` 。若没有自动打开，手动复制该地址到浏览器地址栏。

### 第五步：开始使用
- 在输入框粘贴地址文本，或上传 Excel / 截图，点击「开始审核」。
- 审核完成后可下载 CSV / Markdown / 追踪日志(JSON)。
- 命令行模式（可选）：`python examples/demo.py "北京市海淀区中关村大街1号"`

## ⚙️ 配置项说明（.env）

| 变量 | 必填 | 说明 |
|------|------|------|
| `LLM_API_KEY` | ✅ | DeepSeek / OpenAI Key，两种方案见 `.env.example` |
| `LLM_BASE_URL` | ✅ | 模型接口地址（DeepSeek 默认 `https://api.deepseek.com`） |
| `LLM_MODEL` | ✅ | 模型名（如 `deepseek-chat` / `gpt-4o`） |
| `AMAP_API_KEY` | 🗺️ | 高德地图 Key，已预配开箱即用；失效时自行替换 |
| `BING_SEARCH_KEY` | ⬜ | 可选，填了走 Bing 搜索；留空自动回退 DuckDuckGo |

> 🔒 `.env` 已在 `.gitignore` 中，**不会被提交**。请勿将含真实 Key 的文件推送到公开仓库。

## 🤖 Coze 商店部署

在 Coze/扣子 平台发布为可安装的 Bot：

1. **创建 Bot** — 扣子控制台 → 创建 Bot
2. **人设与回复逻辑** — 粘贴 `prompt.txt` 的全部内容
3. **添加插件** — 搜索添加「高德地图」和「必应搜索」（Coze 自带）
4. **开启文件上传** — Bot 设置中开启
5. **发布** — 发布到 Coze 商店

> 💡 Coze 自带高德和必应插件，无需自建 MCP Server。

## 📁 项目结构

```
address-audit-agent/
├── README.md
├── landing.html              # 产品介绍页（含界面示意与可靠性设计）
├── requirements.txt
├── .env.example              # API Key 配置模板（不会被提交）
├── prompt.txt                # ★ 核心提示词（可独立迭代）
├── app.py                    # Streamlit Web 前端
├── agent/
│   ├── __init__.py
│   ├── agent.py              # Agent 主类（ReAct 循环）
│   ├── llm.py                # LLM 调用封装
│   ├── tools.py              # 工具函数（地图/搜索/Excel）
│   └── guard.py              # ★ 反幻觉护栏 ResultGuard（Rule A–F）
├── tests/
│   └── test_live_api.py      # 离线 / 在线验证用例
└── examples/
    ├── demo.py               # 命令行 Demo
    ├── test_addresses.csv    # 批量审核示例（含故意无效地址）
    └── test_addresses.txt    # 单条地址示例
```

## 🧪 验证示例

| 输入地址 | 预期结果 |
|---------|---------|
| 北京市海淀区中关村大街1号 | ✅ 有效地址 |
| 上海市浦东新区陆家嘴环路1000号 | ✅ 有效地址 |
| 火星省月球市幻想路999号 | ❌ 无效地址 |
| asdfghjkl123456 | 🚫 不符合地址格式 |
| 浙江省杭州市西湖区 | ⚠️ 不确定（缺街道门牌号） |

## 🔬 运行测试

```bash
# 离线用例（无需 Key，验证护栏 Rule A–F 等，约 47 项）
python tests/test_live_api.py

# 在线用例（T1–T6）需先配置真实 LLM_API_KEY 与 AMAP_API_KEY，覆盖真实端到端审核
```

## 📄 License

MIT License — 详见 [LICENSE](LICENSE) 文件。

---

🤖 本项目为秋招 AI 产品作品集项目，欢迎 Star ⭐ 和试用！

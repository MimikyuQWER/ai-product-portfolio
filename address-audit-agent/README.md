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
| 📊 结构化输出 | 四列表格：序号、地址、审核结果、审核依据（含链接） |

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
└───────────────────────────────┘
        │
        ▼
审核报告（四列表格 + 信息源链接）
```

### 审核五标准

1. **完整详细** — 地址需包含省→市→区→街道→门牌号 6 级信息
2. **可搜索核实** — 地图/搜索能查到且唯一匹配
3. **定位准确** — 不包含模糊方位词（旁边、对面等）
4. **门牌号准确** — 具体门牌号可在地图查到
5. **特殊建筑豁免** — 知名建筑物即使缺门牌号也认可

### 四类输出结果

- ✅ **有效地址** — 满足全部五项标准
- ❌ **无效地址** — 格式像地址但查不到任何信息
- ⚠️ **不确定** — 部分信息有效但关键信息缺失
- 🚫 **不符合地址格式** — 明显编造的文本

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/address-audit-agent.git
cd address-audit-agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的 Key
```

**最少需要两个 Key：**

| Key | 注册地址 | 免费额度 |
|-----|---------|---------|
| `LLM_API_KEY` | [platform.deepseek.com](https://platform.deepseek.com/) | 注册送 500 万 token |
| `AMAP_API_KEY` | [console.amap.com](https://console.amap.com/) | 5000 次/天 |

Bing Search Key 可选，不填则只用高德地图验证。

### 4. 启动

**Web 界面（推荐）：**
```bash
streamlit run app.py
```

**命令行：**
```bash
python examples/demo.py "北京市海淀区中关村大街1号"
python examples/demo.py  # 交互模式
```

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
├── requirements.txt
├── .env.example              # API Key 配置模板
├── prompt.txt                # ★ 核心提示词（可独立迭代）
├── app.py                    # Streamlit Web 前端
├── agent/
│   ├── __init__.py
│   ├── agent.py              # Agent 主类（ReAct 循环）
│   ├── llm.py                # LLM 调用封装
│   └── tools.py              # 工具函数（地图/搜索/Excel）
└── examples/
    └── demo.py               # 命令行 Demo
```

## 🧪 验证示例

| 输入地址 | 预期结果 |
|---------|---------|
| 北京市海淀区中关村大街1号 | ✅ 有效地址 |
| 上海市浦东新区陆家嘴环路1000号 | ✅ 有效地址 |
| 火星省月球市幻想路999号 | ❌ 无效地址 |
| asdfghjkl123456 | 🚫 不符合地址格式 |
| 浙江省杭州市西湖区 | ⚠️ 不确定（缺街道门牌号） |

## 📄 License

MIT License — 详见 [LICENSE](LICENSE) 文件。

---

🤖 本项目为秋招 AI 产品作品集项目，欢迎 Star ⭐ 和试用！

---
name: "cn-investment-research"
description: "中国A股/债券/衍生品投研分析。个股五层分析、DCF估值（中债利率）、可比公司（申万行业）、可转债双低策略、期货基差分析、组合诊断。数据源：AKShare优先(免费无限)+iFinD MCP兜底(付费配额)，中金研报格式，中国会计准则。触发词：分析股票/深度研报/可转债/期货/市场全景。"
version: 2.0.0
author: 张逸帆
---

# 中国市场投研分析

覆盖 **A股 + 债券（含可转债）+ 衍生品（期货/期权）** 的投研框架。

> ⚠️ 所有分析仅供参考，不构成投资建议。关键假设（WACC、增长率等）请自行复核。

---

## 数据源策略（AKShare 优先，iFinD 兜底）

```
🔴 核心原则：先吃免费午餐，不够再动配额 🔴

AKShare（Tier-1，免费无限）────────→ 行情、K线、ETF、财务、宏观
    │ AKShare 做不到 / 报错时
    ▼
iFinD MCP（Tier-2，2000次配额）──→ 基金经理、可转债条款、公告搜索、高频行情
```

| 场景 | 先试 AKShare | 不行再 iFinD |
|------|:--:|:--:|
| 行情 / K线 / ETF | ✅ `ak.stock_zh_a_spot_em()` | `stock_highfreq_quotes` |
| 历史K线 | ✅ `ak.stock_zh_a_hist()` | `get_stock_performance` |
| 基本财务（营收/利润/ROE） | ✅ `ak.stock_financial_abstract()` | `get_stock_financials` |
| 宏观（CPI/PMI/社融） | ✅ `ak.macro_china_*()` | `get_edb_data` |
| 期货行情/基差 | ✅ `ak.futures_main_sina()` | `get_edb_data` |
| 可转债行情/双低 | ✅ `ak.bond_cb_jsl()` | `bond_special_data` |
| 指数/板块数据 | ✅ `ak.stock_zh_index_*()` | `index_data` / `sector_data` |
| 基金经理/在管规模 | ❌ AKShare 没有 | ✅ `get_fund_profile` |
| 可转债条款/转股价 | ❌ AKShare 不全 | ✅ `bond_special_data` |
| 公告深度检索 | ❌ AKShare 没有 | ✅ `search_notice` |
| 高频实时行情 | ❌ AKShare 延迟大 | ✅ `stock_highfreq_quotes` |
| ESB/风险指标 | ❌ AKShare 没有 | ✅ `get_risk_indicators` |

**判断逻辑：**
1. 先看需求是否在 AKShare 能力范围内（行情/K线/基础财务/宏观/期货）→ 是就用 AKShare
2. AKShare 没有的维度（基金经理、公告搜索、可转债条款、ESG、高频行情）→ 用 iFinD
3. AKShare 报错或数据异常 → 降级到 iFinD，并在输出中注明

### 中国市场 vs 美股关键参数差异

| 参数 | A股 | 美股 |
|------|-----|------|
| 无风险利率 | 中债10年期（~2.5-3.5%） | 美债10Y |
| 股权风险溢价 | 6-8% | 5-6% |
| 企业所得税 | 25%（高新15%） | 21% |
| 永续增长率 | 3-4%（中国名义GDP） | ~2% |
| 会计准则 | CAS（中国） | US GAAP / IFRS |
| 行业分类 | 申万（2021版）/ 中信 | GICS |
| 财报截止 | 12月31日 | 各异 |
| 货币 | CNY | USD |

---

## 一、A股股票分析

### 1.1 快速个股分析（五层法）

**触发词**：「分析 XX」「看看 XX」

按 AKShare → iFinD 的顺序拉数据：

| 层 | 分析内容 | AKShare（优先） | iFinD（兜底） |
|----|---------|-----------------|---------------|
| ① 基本面 | 主营、ROE、毛利率、负债率 | `ak.stock_financial_abstract()` | `get_stock_financials` |
| ② 估值 | PE/PB/PS、历史分位 | 实时行情自带 PE/PB | `get_stock_summary`（历史分位） |
| ③ 技术面 | 均线、MACD/KDJ、量价 | `ak.stock_zh_a_hist()` 日线 | `stock_highfreq_quotes`（分钟级） |
| ④ 赛道 | 申万行业、概念板块 | 行情数据含行业字段 | `sector_data` + `search_news` |
| ⑤ 风险 | 质押、解禁、商誉 | 财务摘要含商誉数据 | `get_risk_indicators` + `get_stock_events` |

**输出**：关键指标表格 + 一句话结论

### 1.2 深度公司研报

**触发词**：「深度分析 XX」「写 XX 研报」

```
1. 投资摘要（核心结论 + 目标价/评级）
2. 公司概况（业务拆解、股东结构、管理层）
3. 行业分析（申万行业、规模排名、竞争格局）
4. 财务分析（近5年杜邦拆解、现金流质量、商誉风险——商誉>净资产30%需预警）
5. DCF估值（三情景：乐观/中性/悲观，WACC用中债10Y+ERP）
6. 可比公司（同行业PE/PB/EV/EBITDA横向对比）
7. 风险提示（≥3条具体风险）
8. 附录（关键指标一览）
```

### 1.3 DCF 估值模型

**触发词**：「估值 XX」「DCF XX」

中国市场特殊参数：
- **WACC**: Ke = Rf + β×ERP, Rf=中债10Y, ERP=6-8%
- **税率**: 默认25%，高新技术企业15%（查年报确认）
- **终值增长**: 3-4%
- **财报单位注意**: 部分报表以「千元」为单位，需检查

---

## 二、债券分析

### 2.1 可转债 ⭐（最常用）

**数据获取：先 AKShare 后 iFinD**
1. `ak.bond_cb_jsl()` → 全市场可转债行情（含价格、溢价率、双低值），**免费全覆盖**
2. 如果需查具体条款（转股价、强赎、下修）→ iFinD `bond_special_data`
3. 正股走势 → AKShare `ak.stock_zh_a_hist()` 即可

**双低策略核心公式：**
- **双低值 = 转债价格 + 转股溢价率 × 100**
- 双低值 < 130 → 候选标的

**风控要点：**
- 转债价格 < 120 有「债底」保护
- 溢价率 > 50% 股性弱，涨不动
- 临近强赎（正股连续15天 > 转股价130%）需回避

### 2.2 利率债

**触发词**：「收益率曲线」「期限利差」

用 `get_edb_data` 查中债收益率：1Y/2Y/5Y/10Y/30Y，分析期限利差（10Y-2Y）、信用利差。

---

## 三、衍生品分析

### 3.1 期货

**数据优先用 AKShare**：`ak.futures_main_sina("RB0")` 拿主力合约行情，`ak.futures_main_sina_hist()` 拿K线。

只有需查 **持仓排名（前20会员多空）、交易所仓单** 等深度数据时才用 iFinD `get_edb_data`。

### 3.2 期权

**触发词**：「期权分析」「隐含波动率」「希腊字母」

分析 IV 曲面、Delta/Gamma/Theta/Vega、Put/Call比率（市场情绪）。

---

## 四、组合与市场全景

### 4.1 市场快照

**触发词**：「今天市场」「市场全景」

一次输出：主要指数涨跌+成交额、申万行业涨跌榜、涨跌家数比/北向资金、可转债等权指数+双低中位数。

### 4.2 组合诊断

**触发词**：「看看持仓」「组合分析」

持仓集中度、相关性矩阵、Beta/VaR/最大回撤、收益归因。

---

## 五、AKShare 常用接口（优先使用）

```python
import akshare as ak
# 全市场实时行情
ak.stock_zh_a_spot_em()
# 个股历史K线（前复权）
ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20260101", end_date="20260703", adjust="qfq")
# ETF行情
ak.fund_etf_spot_em()
# 全市场可转债（含双低值）
ak.bond_cb_jsl()
# 期货主力合约
ak.futures_main_sina(symbol="RB0")
# 期货历史K线
ak.futures_main_sina_hist(symbol="RB0", period="daily")
# CPI
ak.macro_china_cpi()
# PMI
ak.macro_china_pmi()
# 货币供应量
ak.macro_china_money_supply()
```

---

## 六、iFinD MCP 兜底工具（AKShare 做不到时用）

以下是 AKShare **没有**或**不全**的能力，才动用 iFinD 配额：

---

## 六、申万一级行业（2021版）

农林牧渔 / 基础化工 / 钢铁 / 有色金属 / 电子 / 汽车 / 家用电器 / 食品饮料 / 纺织服饰 / 轻工制造 / 医药生物 / 公用事业 / 交通运输 / 房地产 / 商贸零售 / 社会服务 / 银行 / 非银金融 / 综合 / 建筑材料 / 建筑装饰 / 电力设备 / 国防军工 / 计算机 / 传媒 / 通信 / 煤炭 / 石油石化 / 环保 / 美容护理 / 机械设备

---

## 七、注意事项

1. **AKShare 优先**：行情/K线/基础财务/期货/宏观一律先走 AKShare，失败才切 iFinD
2. **iFinD 仅兜底**：基金经理、公告搜索、可转债条款、ESG、高频行情才用 iFinD
3. **行情延迟**：AKShare 有1-5秒延迟，盘中分析时注明
4. **财报单位**：部分公司财报以千元为单位，计算比率前统一
5. **商誉预警**：商誉 > 净资产30% 需重点提示
6. **合规声明**：每条分析末尾标注「仅供参考，不构成投资建议」

---

## 八、踩坑实录（Bad Case 知识库）

> 每次遇到报错并解决后，记录在此。下次同类任务可直接跳过踩坑步骤。

### 坑 #1：AKShare 日期列类型不匹配

**现象：** `'>=' not supported between 'datetime.date' and 'str'`

**原因：** AKShare 返回的日期列是 `datetime.date` 对象，不能直接和字符串 `'2026-04-01'` 比较。

**解法：** 比较前必须 `df['日期'] = pd.to_datetime(df['日期'])` 转换。

### 坑 #2：iFinD MCP 查询参数过载返回空

**现象：** `get_fund_market_performance` 返回 `工具调用结果为空`

**原因：** 一次查 6 只基金 × 5 个指标（收益率+回撤+波动率+夏普），参数组合太复杂，工具匹配不到。

**解法：** 拆成单只查询，每只基金单独调 MCP。或者先查少指标确认语法，再逐步加。

### 坑 #3：openpyxl 图表轴类型混用

**现象：** `ValueError: Min value is 2` 设置 `tickLabelSkip` 时报错

**原因：** `tickLabelSkip` / `tickMarkSkip` 是**类别轴（TextAxis）** 的属性，不能用于**日期轴（DateAxis）**。openpyxl 类型校验严格。

**解法：** 时间序列图表做横轴时，创建一列辅助标签（文本格式），只填稀疏日期（如月初 + 每隔 10 天），其余留空。用这列做 `set_categories`，自然就是稀疏标签。

### 坑 #4：Windows 文件占用导致写入失败

**现象：** `PermissionError` 保存 xlsx 时报拒绝访问

**原因：** 第一次生成的 xlsx 在 Excel 中打开着，Windows 文件锁阻止覆盖。

**解法：** 每次保存前检查文件是否被占用；或默认用新文件名（加时间戳）。

### 坑 #5：recalc.py AF_UNIX 在 Windows 不可用

**现象：** `AttributeError: module 'socket' has no attribute 'AF_UNIX'`

**原因：** xlsx skill 的 recalc 脚本依赖 LibreOffice + Unix socket，完全是 Linux/macOS 方案。

**解法（已修）：** 已重写 recalc.py，Windows 下尝试 Excel COM 自动化，如果没有则跳过重算但保留公式验证（错误扫描不需要 LibreOffice）。打开 Excel 后公式自动计算。

### 坑 #6：AKShare 基金数据覆盖有限

**现象：** `ak.fund_open_fund_info_em()` 能查到净值但不能查基金经理/持仓

**原因：** AKShare 数据来自天天基金等公开网站，只覆盖基本行情和净值。基金经理、持仓明细、公告搜索等维度不在爬取范围。

**解法：** 见本 skill 数据源策略 —— 行情/K线用 AKShare，基金经理/持仓/公告用 iFinD MCP 兜底。

### 坑 #7：A股涨跌颜色与西方相反

**现象：** 日涨跌幅数字的涨跌颜色标反了（绿涨红跌）

**原因：** 欧美金融惯例是绿涨红跌，但 **A股/中国惯例是红涨绿跌**。网上很多 Python 教程和库默认西方配色。

**解法：** 所有中国市场的涨跌幅、收益率数字，手工配色：`font_color='#D1453E'`（涨/红）、`font_color='#1C8D53'`（跌/绿）。

### 坑 #8：openpyxl 画图表不可用 → 换 xlsxwriter

**现象：** openpyxl 图表横轴挤满、标签无法控制、标题缺失、图例失控

**原因：** openpyxl 的图表 API 功能残缺，不支持 `major_unit`（横轴步长）、轴类型混用无提示、无原生悬浮 tooltip。

**解法：** 
- **数据表** → openpyxl 或 xlsxwriter 都可以
- **图表** → 必须 xlsxwriter（支持 `major_unit`、`set_x_axis`、`set_y_axis`、原生交互 tooltip）
- xlsxwriter 的 `add_chart()` 是 **workbook 级方法**（`wb.add_chart`），不是 worksheet 级
- `ws.write(row, col, value, format)` 参数顺序不能搞错，第二第三是行列位置

### 坑 #9：Shell heredoc 写长 Python 脚本不可靠

**现象：** `bash -c << 'PYEOF'` 写超过 100 行的 Python 脚本时，引号嵌套、中文编码、反斜杠转义极容易出错。`unexpected EOF` 是最常见报错。

**解法：** 复杂脚本先 `Write` 工具写成 .py 文件，再 `python xxx.py` 执行。调试时可反复修改 .py 文件再运行，不用每次都重写全文。

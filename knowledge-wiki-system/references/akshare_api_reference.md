# AKShare API 参考文档

> 来源：AKShare 官方文档 (github.com/akfamily/akshare)
> 保存日期：2026-07-09
> 使用规范：每次爬取 AKShare 数据前，先检索本文档确认接口参数和返回字段

---

## 🔑 核心接口（当前项目使用）

### 申万一级行业指数

#### 获取行业列表
```python
ak.sw_index_first_info()
```
返回：行业代码、行业名称、成份个数、市盈率、市净率、股息率

#### 获取历史日频数据
```python
ak.index_hist_sw(symbol='801010', period='day')
```
**参数：**
- `symbol`: str, 指数代码（如 '801010'，不带 .SI 后缀）
- `period`: str, `"day"` / `"week"` / `"month"`

**返回字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| 日期 | object | 交易日 |
| 开盘 | float64 | 开盘价 |
| 收盘 | float64 | 收盘价 |
| 最高 | float64 | 最高价 |
| 最低 | float64 | 最低价 |
| 成交量 | float64 | 成交量 |
| 成交额 | float64 | 成交额 |

**注意：** 无 start_date/end_date 参数，返回全部历史数据，需自行切片。

---

## 📋 其他常用接口速查

### A股历史行情
```python
ak.stock_zh_a_hist(symbol='000001', period='daily', start_date='20200101', end_date='20251231', adjust='hfq')
```
- adjust: `""` 不复权, `"qfq"` 前复权, `"hfq"` 后复权
- 返回：日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、涨跌额、换手率

### 实时行情
```python
ak.stock_zh_a_spot_em()  # 全部A股实时行情
```

### 行业板块（东方财富）
```python
ak.stock_board_industry_name_em()           # 行业板块列表
ak.stock_board_industry_cons_em(symbol="小金属")  # 板块成分股
ak.stock_board_industry_hist_em(symbol="小金属", period="日k", start_date="20200101", end_date="20251231")
```

### 概念板块（东方财富）
```python
ak.stock_board_concept_name_em()            # 概念板块列表
ak.stock_board_concept_cons_em(symbol="融资融券")  # 板块成分股
ak.stock_board_concept_hist_em(symbol="绿色电力", period="daily", start_date="20200101", end_date="20251231")
```

### 财务报表
```python
ak.stock_balance_sheet_by_report_em(symbol="SH600519")  # 资产负债表
ak.stock_profit_sheet_by_report_em(symbol="SH600519")   # 利润表
ak.stock_cash_flow_sheet_by_report_em(symbol="SH600519") # 现金流量表
ak.stock_financial_analysis_indicator_em(symbol="301389.SZ") # 主要财务指标
```

### 资金流向
```python
ak.stock_individual_fund_flow(stock="600094", market="sh")    # 个股资金流
ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流") # 板块资金流排名
```

### 股东相关
```python
ak.stock_gdfx_free_top_10_em(symbol="sh688686", date="20240930")  # 十大流通股东
ak.stock_gdfx_top_10_em(symbol="sh688686", date="20210630")       # 十大股东
ak.stock_zh_a_gdhs(symbol="20230930")                             # 股东户数
```

### 融资融券
```python
ak.stock_margin_sse(start_date="20200101", end_date="20201231")   # 沪市两融汇总
ak.stock_margin_detail_sse(date="20230922")                       # 沪市两融明细
ak.stock_margin_account_info()                                     # 两融账户信息
```

### 大宗交易
```python
ak.stock_dzjy_mrmx(symbol='A股', start_date='20220101', end_date='20220131')
ak.stock_dzjy_mrtj(start_date='20220101', end_date='20220131')
```

### 龙虎榜
```python
ak.stock_lhb_detail_em(start_date="20220314", end_date="20220315")
ak.stock_lhb_stock_detail_em(symbol="600077", date="20070416", flag="买入")
```

### 指数数据
```python
# 指数历史行情（通过 iFinD MCP 或 AKShare）
ak.index_hist_sw(symbol='801010', period='day')  # 申万指数
```

## ⚠️ 复权说明

- 量化回测统一使用后复权（`hfq`）
- AKShare 的 `stock_zh_a_hist` 支持 `adjust="hfq"` 参数
- 申万指数 `index_hist_sw` 无需复权（指数会自动处理）

## 📎 完整文档

完整 AKShare API 文档见：https://github.com/akfamily/akshare
推荐使用 `ak.<tab>` 或 `dir(ak)` 在 Python 中探索可用接口。

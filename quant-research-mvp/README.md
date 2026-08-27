# 量化研究工作台：脱敏作品集 Demo

这是作品集展示版本，重点是把一次量化研究拆成可理解、可复核的七段流程，而不是展示某个策略的收益预测能力。

完整中文 Demo PRD 见 [PRD.md](PRD.md)。

## 两种使用形态和页面

- `site/index.html`：产品功能页。展示数据准备、策略选择、回测结果、风险指标和证据链。
- `site/research.html`：专业投研工作台。支持自然语言研究提案、配置保存、单因子评估、因子审批、正交化与综合因子、策略审批、真实本地回测和版本归档。
- `site/wealth.html`：手机 APP 版。用移动端的渐进流程独立完成同一套七步研究，不依赖 PC 工作台；页面明确为概念演示。
- `site/design.html`：设计思路页。解释模块权责、输入输出契约、时间纪律、工程取舍以及 AI 如何参与研发。

页面使用静态 HTML/CSS/JavaScript；PC 与财富端均由同一个本地 Python 服务提供真实运行和归档接口，便于面试官体验“输入 → 计算 → 决策 → 归档”。没有依赖真实账号或外部 API。

## 快速运行

提交作品集时，建议直接把整个本文件夹（即包含 `site/`、`backend/`、`vendor/`、`requirements.txt`、`启动Demo.bat` 的文件夹）复制或压缩发送。`vendor/` 中包含 Demo 需要的最小回测、契约、指标和因子评估代码，页面和后端不再依赖外层正式仓库。

### 方式 A：只看界面（零依赖，推荐先试）

直接双击打开 `site/index.html`（产品功能页），或 `site/research.html`（专业投研工作台），或 `site/wealth.html`（手机 APP 版）。
页面已**内置演示数据**，无需安装任何环境、无需联网，可离线浏览全部界面与七段流程展示。
（此方式下“运行并归档”等需要后端计算的按钮不可用，仅作界面浏览。）

### 方式 B：完整体验（含“运行并归档”真实后端）

需要本机已安装 **Python 3.11+**，且安装时勾选 “Add python.exe to PATH”（Windows 自带 `py` 启动器也可）。

最简单：双击根目录的 **`启动Demo.bat`**，它会自动完成——定位 Python → 首次运行建虚拟环境并安装依赖（约 1–2 分钟，需联网）→ 启动本地服务 → 自动打开浏览器 `http://127.0.0.1:8765/index.html`。
若本机没有 Python，脚本会提示你先安装，并仍可改用方式 A 看界面。关闭弹出的后端窗口即可停止服务。

手动等价命令（在文件夹根目录执行）：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m backend.run_server
```

启动后打开 `http://127.0.0.1:8765/index.html`。进入研究工作台后，点击“运行并归档”，后端会调用统一回测入口，并在 `runs/<运行号>/` 写入七个阶段的 `input.json` 和 `output.json`。

（可选）如需重新生成演示数据 `site/data/demo-run.json`，可额外执行：

```powershell
.venv\Scripts\python.exe -m backend.generate_demo
```

该文件已随仓库附带，通常无需重复生成。

## Demo 的实际链路

```text
数据提取与存储
  → 单因子挖掘和测试
  → 因子正交化、标准化与综合加权
  → 风控与调仓
  → 策略设计与迭代
  → 回测报告
  → 版本管理与运行记录
```

策略使用仓库中的通用 `DataBundle`、`FactorSpec`、`SplitConfig`、`BacktestConfig`、`StrategyContext`、`run_backtest` 和记录契约，所以展示版本保留了正式研究系统的工程骨架；数据层替换为确定性的合成数据，避免泄露本地行情和配置。示例包含动量、价值、低波、正交化综合因子，以及基于 12 个月趋势过滤的动量择时策略。`demo-run.json` 中的 `architecture`、`config.sample_split`、`factor_research`、`strategy_iterations` 和 `versioning` 分别记录每个阶段的责任、输入输出、时间切分、迭代和版本信息。

## iFinD 真实接口冒烟

如果本机已经配置 iFinD，可以在本地运行：

```powershell
.venv\Scripts\python.exe -m backend.run_ifind_smoke
```

适配器只读取历史指数收盘价，并在内存中转成月频 `DataBundle`，运行动量、低波和等权策略；输出文件是 `validation/ifind_smoke_report.json`，只保存接口元数据和派生指标，不保存原始价格、账号或 token。没有 iFinD 环境时，页面和默认 demo 不受影响。

## 测试和检查

```powershell
node --check site\app.js
node --check site\research.js
node --check site\assistant.js
node --check site\wealth.js
```

页面资源可以用任意本地静态服务器访问。作品集展示应明确说明：合成数据用于脱敏和可复现；iFinD 报告用于证明真实数据适配链路曾被冒烟验证；二者都不构成投资建议。

v2.1 增加专业协作与受约束自主研究两种模式、独立验证模块、双端首次使用指引和阶段化 AI 解读。当前 AI 助手采用本地规则生成结构化研究方案，并引用预置且已核验的研究来源；它不是在线大模型或实时论文检索服务。金融计算和独立验证均由确定性后端完成，避免用生成式文案替代计算结果。

## 已知边界

本 Demo 已经是可独立运行的作品集 MVP，但不能包装成正式生产系统。真实仓库审计仍发现旧引擎与新 Runner 并存、成本模型有多套口径、验证集与测试集重叠、部分辅助因子未随版本冻结等风险；这些内容单独记录在正式仓库的风险报告中，不随脱敏 Demo 对外分发，也不在产品页面中混淆展示。

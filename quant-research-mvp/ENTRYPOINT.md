# 作品集交付入口

对外展示时，建议直接分发整个 `portfolio_demo` 文件夹。文件夹内已包含 Demo 所需的最小回测依赖和启动脚本，不需要把正式量化仓库一起发给面试官。

首次运行：

```powershell
cd portfolio_demo
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m backend.run_server
```

也可以在完成依赖安装后双击 `启动Demo.bat`。

如果在完整仓库中运行最终脱敏入口：

```powershell
.venv\Scripts\python.exe portfolio_demo\run_portfolio_fixed.py --output portfolio_demo\output_portfolio_fixed --seed 42
```

它使用合成行业标签和收益数据，把 recorder 的 git 根隔离到临时目录；生成的 manifest 不包含宿主仓库 dirty 文件名或本机绝对路径。`run_demo.py` 保留为开发参考入口，发送作品集时只保留 `run_portfolio_fixed.py` 与本入口说明。

浏览器展示建议按以下顺序打开：

1. `site/index.html`：先理解产品功能和展示价值；
2. `site/research.html`：体验参数锁定、因子证据、审批、回测质检和版本记录；
3. `site/design.html`：再阅读正式系统的架构取舍与人机分工。

如果要验证“前端点击 → 后端计算 → 七阶段归档”，请启动本地服务：

```powershell
.venv\Scripts\python.exe -m portfolio_demo.backend.run_server
```

然后访问 `http://127.0.0.1:8765/research.html` 或 `http://127.0.0.1:8765/wealth.html`。两种形态都能独立完成七步流程，运行结果会写入 `portfolio_demo/runs/<运行号>/`。

`research.html` 是面向专业研究人员的 PC 工作台；`wealth.html` 是面向财富平台场景的移动端轻量形态。两者共享计算和归档能力，但不互相依赖。

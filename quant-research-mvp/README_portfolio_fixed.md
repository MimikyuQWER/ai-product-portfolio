# 对外作品集 demo

使用 `run_portfolio_fixed.py`，它把审计器的 git 根隔离到临时目录，并只输出合成数据、相对 run 路径和指标，不携带宿主仓库 dirty 文件名。

```powershell
.venv\Scripts\python.exe portfolio_demo\run_portfolio_fixed.py --output portfolio_demo\output_portfolio_fixed --seed 42
```

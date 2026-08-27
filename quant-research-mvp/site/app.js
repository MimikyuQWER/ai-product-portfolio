const state = { payload: null, selected: "momentum", hasRun: false };

const fallbackPayload = {
  disclaimer: "All data and results in this file are synthetic and for product demonstration only.",
  config: { signal_lag: 1, cost_model: "demo_linear_5bp_buy_10bp_sell", benchmark: "equal_weight" },
  strategies: {
    momentum: { id: "momentum", label: "横截面动量", summary: "追踪过去 6 个月相对强势的 3 个行业", metrics: { cum: .31, ann: .041, vol: .13, sharpe: .42, max_dd: -.18 }, evidence: { cost_total: .012, turnover_mean: .41, periods: 83 }, nav: [{ date: "2019-01-31", value: 1 }, { date: "2025-12-31", value: 1.31 }] },
    low_vol: { id: "low_vol", label: "低波动", summary: "选择过去 6 个月波动率最低的 3 个行业", metrics: { cum: .26, ann: .035, vol: .09, sharpe: .46, max_dd: -.12 }, evidence: { cost_total: .008, turnover_mean: .27, periods: 83 }, nav: [{ date: "2019-01-31", value: 1 }, { date: "2025-12-31", value: 1.26 }] },
    value: { id: "value", label: "价值 / PB", summary: "选择模拟 PB 最低的 3 个行业", metrics: { cum: .21, ann: .029, vol: .11, sharpe: .29, max_dd: -.16 }, evidence: { cost_total: .009, turnover_mean: .31, periods: 83 }, nav: [{ date: "2019-01-31", value: 1 }, { date: "2025-12-31", value: 1.21 }] },
    equal_weight: { id: "equal_weight", label: "等权基准", summary: "所有行业等权持有，作为可解释基准", metrics: { cum: .18, ann: .025, vol: .12, sharpe: .22, max_dd: -.19 }, evidence: { cost_total: .016, turnover_mean: .03, periods: 83 }, nav: [{ date: "2019-01-31", value: 1 }, { date: "2025-12-31", value: 1.18 }] }
  }
};

const fmtPct = (value) => value == null ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
const fmtNum = (value, digits = 2) => value == null ? "—" : Number(value).toFixed(digits);
const byId = (id) => document.getElementById(id);

async function loadPayload() {
  try {
    const response = await fetch("data/demo-run.json", { cache: "no-store" });
    if (!response.ok) throw new Error("payload unavailable");
    return await response.json();
  } catch (error) {
    return fallbackPayload;
  }
}

function drawChart(canvas, selectedId, payload) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, rect.width * ratio);
  canvas.height = Math.max(1, rect.height * ratio);
  ctx.scale(ratio, ratio);
  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);
  const strategy = payload.strategies[selectedId];
  const benchmark = payload.strategies.equal_weight;
  const values = [...(strategy.nav || []), ...(benchmark.nav || [])].map((point) => point.value);
  const min = Math.min(...values) * .96;
  const max = Math.max(...values) * 1.04;
  const x = (i, length) => length <= 1 ? 0 : (i / (length - 1)) * (width - 12) + 6;
  const y = (v) => height - 9 - ((v - min) / (max - min || 1)) * (height - 18);
  const line = (points, color, dashed = false) => {
    if (!points.length) return;
    ctx.beginPath();
    ctx.setLineDash(dashed ? [5, 5] : []);
    points.forEach((point, index) => index ? ctx.lineTo(x(index, points.length), y(point.value)) : ctx.moveTo(x(index, points.length), y(point.value)));
    ctx.strokeStyle = color;
    ctx.lineWidth = dashed ? 1.2 : 2.2;
    ctx.stroke();
    ctx.setLineDash([]);
  };
  line(strategy.nav || [], "#b5483b");
  line(benchmark.nav || [], "#203743", true);
}

function renderStrategyList(payload) {
  const list = byId("strategy-list");
  if (!list) return;
  list.innerHTML = Object.values(payload.strategies).map((strategy) => `
    <button class="strategy-choice ${strategy.id === state.selected ? "selected" : ""}" type="button" data-strategy="${strategy.id}">
      <strong>${strategy.label}</strong><span>${fmtPct(strategy.metrics.ann)}</span>
    </button>`).join("");
  list.querySelectorAll("[data-strategy]").forEach((button) => button.addEventListener("click", () => {
    state.selected = button.dataset.strategy;
    renderStrategy(payload);
  }));
}

function renderStrategy(payload) {
  const strategy = payload.strategies[state.selected] || payload.strategies.momentum;
  byId("comparison-title").textContent = strategy.label;
  byId("comparison-copy").textContent = strategy.summary;
  byId("metric-ann").textContent = fmtPct(strategy.metrics.ann);
  byId("metric-cum").textContent = fmtPct(strategy.metrics.cum);
  byId("metric-sharpe").textContent = fmtNum(strategy.metrics.sharpe);
  byId("metric-dd").textContent = fmtPct(strategy.metrics.max_dd);
  byId("sheet-value").textContent = strategy.nav?.length ? `${fmtNum(strategy.nav[strategy.nav.length - 1].value)}x` : "—";
  byId("sheet-strategy").textContent = strategy.label;
  byId("sheet-cost").textContent = strategy.evidence?.cost_model || payload.config.cost_model;
  document.querySelectorAll("[data-strategy]").forEach((button) => button.classList.toggle("selected", button.dataset.strategy === state.selected));
  drawChart(byId("sheet-chart"), state.selected, payload);
  drawChart(byId("strategy-chart"), state.selected, payload);
}

const evidence = {
  data: ["准备数据", "先登记研究站在什么材料上。", "数据源、资产池、日期范围", "数据包与数据清单", "别人知道当时用了什么"],
  factor: ["测试因子", "先单独判断一个信号是否值得继续研究。", "因子定义、观察窗口、滞后期、预测收益", "因子值、IC、分组和衰减证据", "不让综合收益掩盖单因子问题"],
  composite: ["改进综合", "把经过测试的信号标准化、统一方向并明确加权。", "单因子证据、标准化规则、权重方案", "综合因子与权重快照", "每个组合假设都能被追问"],
  risk: ["风控调仓", "把目标权重变成受约束的实际动作。", "目标权重、上一期持仓、成本和风险约束", "执行权重、换手、成本、风险事件", "知道收益变化来自哪里"],
  strategy: ["迭代策略", "保留基准、候选版本和每次改动的理由。", "因子证据、组合规则、样本切分", "候选策略、迭代记录、待验证问题", "不只保存最后一个最好结果"],
  backtest: ["回测报告", "按时间顺序执行，不让未来数据回到过去。", "目标权重、信号滞后、资产收益、交易成本模型", "净值、持仓、绩效指标", "收益和风险使用同一套口径"],
  record: ["版本记录", "把配置、输入、输出和版本绑定成一次研究档案。", "运行配置、数据清单、代码状态", "运行清单、文件指纹、报告", "别人可以接着复盘和交接"]
};

function renderEvidence(key = "data") {
  const item = evidence[key];
  if (!item) return;
  byId("evidence-title").textContent = item[0];
  byId("evidence-copy").textContent = item[1];
  byId("evidence-input").textContent = item[2];
  byId("evidence-output").textContent = item[3];
  byId("evidence-meaning").textContent = item[4];
  document.querySelectorAll("[data-evidence]").forEach((button) => button.classList.toggle("selected", button.dataset.evidence === key));
}

function setupRun(payload) {
  const button = byId("run-demo");
  const stateLine = byId("run-state");
  if (!button) return;
  button.addEventListener("click", async () => {
    if (button.disabled) return;
    button.disabled = true;
    state.hasRun = false;
    stateLine.textContent = "正在调用本地回测入口，并归档七个阶段的输入和输出…";
    try {
      const response = await fetch("/api/research/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ asset_type: payload.config.asset_type || "index", universe_id: payload.config.universe_id || "synthetic_sector_8", start: payload.config.start, end: payload.config.end, frequency: payload.config.frequency || "monthly", signal_lag: payload.config.signal_lag || 1, strategy_ids: [state.selected] }) });
      const data = await response.json();
      if (!response.ok || data.status !== "completed") throw new Error(data.error || "运行失败");
      state.payload = data.payload;
      const strategy = data.payload.strategies[state.selected];
      state.hasRun = true;
      stateLine.textContent = `已完成并归档：${strategy.label} · ${strategy.evidence.periods} 期 · 运行号 ${data.archive.run_id}`;
      byId("run-cum").textContent = fmtPct(strategy.metrics.cum);
      byId("run-ann").textContent = fmtPct(strategy.metrics.ann);
      byId("run-cost").textContent = fmtPct(strategy.evidence.cost_total);
      renderStrategy(data.payload);
    } catch (error) {
      stateLine.textContent = `未完成：${error.message}。请使用本地 Demo 服务启动页面。`;
    } finally {
      button.disabled = false;
    }
  });
}

async function boot() {
  const payload = await loadPayload();
  state.payload = payload;
  renderStrategyList(payload);
  renderStrategy(payload);
  renderEvidence();
  document.querySelectorAll("[data-evidence]").forEach((button) => button.addEventListener("click", () => renderEvidence(button.dataset.evidence)));
  setupRun(payload);
  window.addEventListener("resize", () => drawChart(byId("strategy-chart"), state.selected, payload));
}

document.addEventListener("DOMContentLoaded", boot);

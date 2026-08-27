const PC_STORAGE_KEY = "pc-research-state-v2";
const BASE_FACTORS = ["momentum_6m", "low_vol_6m", "pb"];
const FACTOR_LABELS = {
  momentum_6m: "六个月动量",
  low_vol_6m: "六个月低波",
  pb: "价值 / 市净率",
  low_vol_orthogonal: "正交化低波",
  value_orthogonal: "正交化价值",
  composite_v1: "正交化综合因子",
};
const STAGES = ["config", "factor", "factor-approval", "composite", "strategy", "backtest", "versions"];
const STAGE_NAMES = {
  config: "研究配置",
  factor: "单因子评估",
  "factor-approval": "因子审批",
  composite: "因子改进",
  strategy: "策略设计",
  backtest: "回测质检",
  versions: "版本记录",
};
const STAGE_DETAILS = {
  config: "范围 / 成本 / 切分",
  factor: "公式 / IC / 分组",
  "factor-approval": "采纳 / 调整 / 废弃",
  composite: "正交化 / 加权",
  strategy: "持仓 / 风控 / 调仓",
  backtest: "净值 / 风险 / 校验",
  versions: "运行 / 决策 / 差异",
};
const VERSION_STATUS_LABELS = {
  superseded: "已被新版本替代",
  current_candidate: "当前候选",
  workflow_mvp: "流程演示版",
};

const state = {
  payload: null,
  history: { runs: [], decisions: [] },
  configValues: null,
  configLocked: false,
  factor: "momentum_6m",
  factorEvaluationComplete: false,
  factorDecisions: {},
  compositeApproved: false,
  compositeWeights: { momentum_6m: 50, low_vol_orthogonal: 30, value_orthogonal: 20 },
  strategyConfig: { strategy_id: "composite", top_n: 3, defensive_exposure: 50 },
  backtestComplete: false,
  strategyDecision: null,
  assistantPlan: null,
  researchMode: "professional",
  archive: null,
  localDecisionLog: [],
  stage: "config",
  loading: false,
};

const byId = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const fmtPct = (value, digits = 2) => value == null ? "暂无" : `${(Number(value) * 100).toFixed(digits)}%`;
const fmtNum = (value, digits = 3) => value == null ? "暂无" : Number(value).toFixed(digits);
const factorLabel = (id) => FACTOR_LABELS[id] || id;
const decisionLabel = (value) => ({ adopt: "采纳", adjust: "调整", discard: "废弃" }[value] || value);

async function loadPayload() {
  const response = await fetch("data/demo-run.json", { cache: "no-store" });
  if (!response.ok) throw new Error("演示数据加载失败");
  return response.json();
}

async function loadHistory() {
  try {
    const response = await fetch("/api/research/history", { cache: "no-store" });
    return response.ok ? response.json() : { runs: [], decisions: [] };
  } catch (error) {
    return { runs: [], decisions: [] };
  }
}

function defaultConfig(payload) {
  const cfg = payload.config;
  return {
    asset_type: cfg.asset_type || "index",
    universe_id: cfg.universe_id || "synthetic_sector_8",
    benchmark: cfg.benchmark || "equal_weight",
    frequency: cfg.frequency || "monthly",
    start: cfg.start,
    end: cfg.end,
    train_end: cfg.sample_split.train.end,
    validation_start: cfg.sample_split.validation.start,
    validation_end: cfg.sample_split.validation.end,
    signal_lag: Number(cfg.signal_lag ?? 1),
    cost_model: cfg.cost_model,
    sample_split: cfg.sample_split,
  };
}

function saveState() {
  const keys = ["configValues", "configLocked", "factor", "factorEvaluationComplete", "factorDecisions", "compositeApproved", "compositeWeights", "strategyConfig", "backtestComplete", "strategyDecision", "assistantPlan", "researchMode", "archive", "localDecisionLog", "stage"];
  const saved = {};
  keys.forEach((key) => { saved[key] = state[key]; });
  localStorage.setItem(PC_STORAGE_KEY, JSON.stringify(saved));
}

function restoreState() {
  try {
    const saved = JSON.parse(localStorage.getItem(PC_STORAGE_KEY) || "null");
    if (!saved) return;
    Object.keys(saved).forEach((key) => { if (key in state) state[key] = saved[key]; });
  } catch (error) {
    localStorage.removeItem(PC_STORAGE_KEY);
  }
}

async function restoreArchivedPayload() {
  const runId = state.archive?.run_id;
  if (!runId || !state.backtestComplete) return;
  try {
    const response = await fetch(`/api/research/run/${encodeURIComponent(runId)}`, { cache: "no-store" });
    const result = await response.json();
    if (response.ok && result.payload) state.payload = result.payload;
  } catch (error) {
    state.backtestComplete = false;
    state.strategyDecision = null;
  }
}

function table(headers, rows, empty = "暂无数据") {
  if (!rows?.length) return `<div class="empty-state">${empty}</div>`;
  return `<div class="data-table-wrap"><table class="data-table"><thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell ?? "暂无"}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function allFactorDecisionsComplete() {
  return BASE_FACTORS.every((id) => Boolean(state.factorDecisions[id]?.decision));
}

function isStageUnlocked(stage) {
  if (stage === "config") return true;
  if (stage === "factor") return state.configLocked;
  if (stage === "factor-approval") return state.factorEvaluationComplete;
  if (stage === "composite") return allFactorDecisionsComplete();
  if (stage === "strategy") return state.compositeApproved;
  if (stage === "backtest") return state.backtestComplete;
  return Boolean(state.strategyDecision);
}

function isStageDone(stage) {
  if (stage === "config") return state.configLocked;
  if (stage === "factor") return state.factorEvaluationComplete;
  if (stage === "factor-approval") return allFactorDecisionsComplete();
  if (stage === "composite") return state.compositeApproved;
  if (stage === "strategy") return state.backtestComplete;
  if (stage === "backtest") return Boolean(state.strategyDecision);
  return Boolean(state.strategyDecision);
}

function stageState(stage) {
  if (!isStageUnlocked(stage)) return "locked";
  return isStageDone(stage) ? "done" : "active";
}

function renderWorkflowBoard() {
  const board = byId("workflow-board");
  if (board) {
    board.innerHTML = STAGES.map((stage, index) => {
      const status = stageState(stage);
      const label = status === "done" ? "已完成" : status === "active" ? "进行中" : "待解锁";
      return `<button class="workflow-card ${status}" type="button" data-workflow="${stage}" ${status === "locked" ? "disabled" : ""}><span class="workflow-card-number">${String(index + 1).padStart(2, "0")}</span><strong>${STAGE_NAMES[stage]}</strong><small>${STAGE_DETAILS[stage]}</small><em>${label}</em></button>`;
    }).join("");
  }
  document.querySelectorAll("[data-workflow]").forEach((button) => {
    const unlocked = isStageUnlocked(button.dataset.workflow);
    button.disabled = !unlocked;
    button.classList.toggle("active", button.dataset.workflow === state.stage);
    if (!button.dataset.bound) {
      button.dataset.bound = "true";
      button.addEventListener("click", () => renderStage(button.dataset.workflow));
    }
  });
  const cfg = state.configValues || defaultConfig(state.payload);
  const context = byId("context-bar");
  if (context) context.innerHTML = `<span>当前研究范围</span><strong>${cfg.asset_type === "index" ? "指数" : escapeHtml(cfg.asset_type)}</strong><strong>${cfg.start} → ${cfg.end}</strong><strong>${cfg.frequency === "monthly" ? "月度调仓" : escapeHtml(cfg.frequency)}</strong><strong>信号滞后 ${cfg.signal_lag} 期</strong><strong>买入 5bp / 卖出 10bp</strong><small>${state.configLocked ? "已保存为本次输入" : "尚未保存"}</small>`;
}

function stageAdvice(stage) {
  const cfg = state.configValues || defaultConfig(state.payload);
  if (stage === "config") return ["配置检查", `固定 ${cfg.start} 至 ${cfg.end} 的样本范围；留出集只做最终检查。`];
  if (stage === "factor") {
    const factor = state.payload.factor_research?.[state.factor];
    const train = factor?.summary?.train?.mean;
    const validation = factor?.summary?.validation?.mean;
    if (train == null || validation == null) return ["结果解读", "当前样本不足以比较训练期和验证期。"];
    const same = train === 0 || validation === 0 || Math.sign(train) === Math.sign(validation);
    return ["结果解读", `训练期 Rank IC ${fmtNum(train)}，验证期 ${fmtNum(validation)}；${same ? "方向一致，可继续检查分组收益和换手。" : "方向不一致，建议先调整口径。"}`];
  }
  if (stage === "factor-approval") return ["审批要求", "因子去留必须同时考虑经济意义、验证期表现、分组收益、换手和时间约束。"];
  if (stage === "composite") return ["组合检查", "正交化减少重复暴露；权重变化必须形成新版本。"];
  if (stage === "strategy") return ["回测前检查", "确认因子版本、持仓数量、防守仓位、信号滞后和成本后再运行。"];
  if (stage === "backtest") return ["结果解读", "先确认规则检查，再比较收益、回撤、换手和成本。"];
  return ["研究记录", "保留成功和失败版本，下一轮从已记录的差异和原因继续。"];
}

function renderAssistantResult(plan) {
  const target = byId("assistant-result");
  if (!target || !plan) return;
  const missing = plan.missing?.length ? `<div class="assistant-warning"><strong>需要确认</strong><ul>${plan.missing.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : "";
  target.innerHTML = `<div class="assistant-result-head"><div><span>研究提案</span><h3>${escapeHtml(plan.title)}</h3></div><span class="approval-badge ${plan.missing?.length ? "pending" : "approved"}">${plan.missing?.length ? "待确认" : "可配置"}</span></div><div class="assistant-proposal"><span>研究假设</span><p>${escapeHtml(plan.hypothesis)}</p><strong>${escapeHtml(plan.proposal)}</strong></div><h4>研究依据</h4><div class="assistant-sources">${(plan.sources || []).map((source) => `<a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer"><strong>${escapeHtml(source.title)}</strong><span>${escapeHtml(source.type)} · ${escapeHtml(source.year)}</span></a>`).join("")}</div>${missing}<div class="assistant-actions"><button class="button" type="button" data-assistant-apply>采用提案</button><button class="button secondary" type="button" data-assistant-clear>清空</button></div>`;
  target.querySelector("[data-assistant-apply]").addEventListener("click", () => renderStage(state.configLocked ? "factor" : "config"));
  target.querySelector("[data-assistant-clear]").addEventListener("click", () => {
    state.assistantPlan = null;
    byId("assistant-input").value = "";
    target.innerHTML = `<div class="assistant-empty"><strong>等待研究想法</strong><p>输入资产、信号和持有方式后，助手会整理需要确认的研究条件。</p></div>`;
    saveState();
  });
}

function setupAssistant() {
  byId("assistant-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = byId("assistant-input").value.trim();
    if (!input) return;
    state.assistantPlan = window.LocalResearchAssistant.parse(input);
    saveState();
    renderAssistantResult(state.assistantPlan);
  });
  document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => {
    byId("assistant-input").value = button.dataset.prompt;
    byId("assistant-input").focus();
  }));
}

async function runPipeline(strategyIds) {
  const cfg = state.configValues;
  if (!cfg) throw new Error("请先保存研究配置");
  const request = {
    asset_type: cfg.asset_type,
    universe_id: cfg.universe_id,
    benchmark: cfg.benchmark,
    frequency: cfg.frequency,
    start: cfg.start,
    end: cfg.end,
    train_end: cfg.train_end,
    validation_start: cfg.validation_start,
    validation_end: cfg.validation_end,
    signal_lag: cfg.signal_lag,
    cost_model: cfg.cost_model,
    strategy_ids: strategyIds,
    factor_weights: {
      momentum_6m: state.compositeWeights.momentum_6m / 100,
      low_vol_orthogonal: state.compositeWeights.low_vol_orthogonal / 100,
      value_orthogonal: state.compositeWeights.value_orthogonal / 100,
    },
    top_n: state.strategyConfig.top_n,
    defensive_exposure: state.strategyConfig.defensive_exposure / 100,
    factor_decisions: state.factorDecisions,
    composite_approved: state.compositeApproved,
    strategy_decision: state.strategyDecision,
    assistant_plan: state.assistantPlan,
    source_surface: "pc",
  };
  const response = await fetch("/api/research/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
  const result = await response.json();
  if (!response.ok || result.status !== "completed") throw new Error(result.error || "运行失败");
  state.payload = result.payload;
  state.archive = result.archive;
  state.history = await loadHistory();
  return result;
}

async function persistDecision(record, title) {
  const local = { ...record, title, created_at: new Date().toISOString(), archived: false };
  try {
    const response = await fetch("/api/research/decision", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...record, run_id: state.archive?.run_id, source_surface: "pc" }) });
    const result = await response.json();
    if (!response.ok || result.status !== "completed") throw new Error(result.error || "决策归档失败");
    local.archived = true;
    local.decision_id = result.decision_id;
    state.history = await loadHistory();
  } catch (error) {
    local.error = error.message;
  }
  state.localDecisionLog.push(local);
  saveState();
  return local;
}

function renderConfig() {
  const cfg = state.configValues || defaultConfig(state.payload);
  return `<div class="panel-heading"><div><span>研究输入</span><h3>配置研究范围</h3><p>先固定标的、样本切分、信号滞后和成本，再开始任何因子计算。</p></div><span class="approval-badge ${state.configLocked ? "approved" : "pending"}">${state.configLocked ? "已保存" : "待保存"}</span></div>
    <form id="research-config" class="config-grid pc-stage-config">
      <label>资产类型<select id="config-asset-type"><option value="index">指数</option><option value="stock">股票</option><option value="fund">基金</option><option value="bond">债券</option></select></label>
      <label>投资范围<select id="config-universe"><option value="synthetic_sector_8">合成行业池 · 8 个标的</option></select></label>
      <label>频率<select id="config-frequency"><option value="monthly">月度调仓</option></select></label>
      <label>比较基准<select id="config-benchmark"><option value="equal_weight">标的池等权</option></select></label>
      <label>回测开始<input id="config-start" type="date" required></label>
      <label>训练集结束<input id="config-train-end" type="date" required></label>
      <label>验证集开始<input id="config-validation-start" type="date" required></label>
      <label>验证集结束<input id="config-validation-end" type="date" required></label>
      <label>回测结束<input id="config-end" type="date" required></label>
      <label>信号滞后<select id="config-lag"><option value="1">1 期 · 禁止同期开仓</option></select></label>
      <label>交易成本<select id="config-cost"><option value="demo_linear_5bp_buy_10bp_sell">买入 5bp / 卖出 10bp</option><option value="zero_cost_warning">0 成本 · 仅敏感性测试</option></select></label>
      <div class="config-submit"><button class="button" type="submit">保存并进入因子评估</button><span id="config-message" role="status">${state.configLocked ? "已保存。修改后需重新运行后续阶段。" : "尚未保存。"}</span></div>
    </form>
    <div class="contract-grid"><div><span>输入</span><strong>标的池、日期、成本与执行滞后</strong></div><div><span>输出</span><strong>可复现的配置快照</strong></div><div><span>独立验证</span><strong>日期顺序、零成本和同期开仓检查</strong></div><div><span>人工权限</span><strong>保存后才允许进入因子评估</strong></div></div>`;
}

function factorNames() {
  return ["momentum_6m", "low_vol_6m", "pb", "low_vol_orthogonal", "value_orthogonal", "composite_v1"].filter((id) => state.payload.factor_research?.[id]);
}

function renderFactor() {
  const factor = state.payload.factor_research?.[state.factor];
  if (!factor || factor.status === "not_available") return `<div class="empty-state">当前数据包没有该因子。</div>`;
  const summary = factor.tables?.ic_summary || {};
  const groupRows = Object.entries(factor.tables?.group_mean_return || {}).map(([key, value]) => [key, fmtPct(value), fmtPct(factor.tables?.group_excess_return?.[key])]);
  const sensitivity = Object.entries(factor.sensitivity?.forward_periods || {}).map(([period, item]) => [`${period} 期`, fmtNum(item.rank_ic_mean), fmtNum(item.rank_icir), item.observations]);
  const [adviceTitle, adviceText] = stageAdvice("factor");
  return `<div class="panel-heading"><div><span>第 2 步 / ${state.factorEvaluationComplete ? "本次运行" : "预置样例"}</span><h3>单因子评估：${factorLabel(state.factor)}</h3><p>${escapeHtml(factor.definition?.economic_meaning || "查看因子口径和证据。")}</p></div><span class="approval-badge ${state.factorEvaluationComplete ? "approved" : "pending"}">${state.factorEvaluationComplete ? "已计算" : "待运行"}</span></div><div class="factor-switcher">${factorNames().map((id) => `<button class="mini-tab ${id === state.factor ? "selected" : ""}" type="button" data-factor="${id}">${factorLabel(id)}</button>`).join("")}</div><div class="formula-sheet"><div><span>公式</span><strong>${escapeHtml(factor.definition?.formula || "暂无")}</strong></div><div><span>方向</span><strong>${factor.definition?.direction === "higher_is_better" ? "数值越高越优" : "数值越低越优"}</strong></div><div><span>时间规则</span><strong>滞后 ${factor.definition?.lag_periods} 期 · 预测 ${factor.definition?.forward_periods} 期</strong></div></div><div class="metric-strip"><div><span>Rank IC</span><strong>${fmtNum(summary.mean)}</strong></div><div><span>ICIR</span><strong>${fmtNum(summary.icir)}</strong></div><div><span>胜率</span><strong>${fmtPct(summary.win_rate)}</strong></div><div><span>G1-G5</span><strong>${fmtPct(factor.tables?.g1_g5_long_short)}</strong></div></div><div class="evidence-columns"><div><h4>分组收益</h4>${table(["分组", "平均收益", "截面超额"], groupRows)}</div><div><h4>敏感性</h4>${table(["持有期", "Rank IC", "ICIR", "样本数"], sensitivity)}</div></div><div class="observer-note"><strong>${adviceTitle}</strong><p>${adviceText}</p></div><div class="panel-actions"><button class="button" type="button" data-run-factor ${state.loading ? "disabled" : ""}>${state.loading ? "正在计算…" : state.factorEvaluationComplete ? "重新运行因子测试" : "运行因子测试"}</button><button class="button secondary" type="button" data-goto="factor-approval" ${state.factorEvaluationComplete ? "" : "disabled"}>进入因子审批</button><span id="factor-run-message">运行后将生成七阶段档案，并用本次结果替换预置样例。</span></div>`;
}

function renderFactorApproval() {
  const cards = BASE_FACTORS.map((id) => {
    const decision = state.factorDecisions[id];
    return `<div class="decision-row ${decision ? "decided" : ""}"><div><strong>${factorLabel(id)}</strong><span>${decision ? `已${decisionLabel(decision.decision)} · ${decision.version}` : "待决定"}</span></div><div class="decision-buttons"><button class="small-button" type="button" data-decision="adopt" data-factor-id="${id}">采纳</button><button class="small-button" type="button" data-decision="adjust" data-factor-id="${id}">调整口径</button><button class="small-button danger" type="button" data-decision="discard" data-factor-id="${id}">废弃</button></div></div>`;
  }).join("");
  return `<div class="panel-heading"><div><span>第 3 步 / 人工审批</span><h3>因子审批</h3><p>每个因子都要记录去留、理由和版本。系统不会自动批准。</p></div><span class="approval-badge ${allFactorDecisionsComplete() ? "approved" : "pending"}">${allFactorDecisionsComplete() ? "已完成" : "待确认"}</span></div><label class="decision-reason">判断依据<input id="factor-reason" type="text" placeholder="说明为什么采纳、调整或废弃" /></label><label class="decision-reason">调整后的观察窗口<select id="factor-adjust-window"><option value="9">9 个月</option><option value="12">12 个月</option></select></label><div class="decision-list">${cards}</div><div id="factor-decision-message" class="observer-note"><strong>审批要求</strong><p>请先填写判断依据。调整口径会生成新版本。</p></div><div class="panel-actions"><button class="button secondary" type="button" data-goto="composite" ${allFactorDecisionsComplete() ? "" : "disabled"}>进入因子改进</button></div>`;
}

function renderComposite() {
  const weights = state.compositeWeights;
  const total = Object.values(weights).reduce((sum, value) => sum + Number(value), 0);
  const workflow = state.payload.research_workflow.composite_design;
  return `<div class="panel-heading"><div><span>第 4 步 / 因子改进</span><h3>正交化与综合权重</h3><p>先减少重复暴露，再按研究员确认的权重形成综合分数。</p></div><span class="approval-badge ${state.compositeApproved ? "approved" : "pending"}">${state.compositeApproved ? "已保存" : "候选方案"}</span></div><div class="formula-sheet"><div><span>正交化</span><strong>${escapeHtml(workflow.orthogonalization)}</strong></div><div><span>输出</span><strong>综合因子 + 权重快照</strong></div></div><form id="pc-composite-form"><div class="config-grid"><label>动量权重<input id="pc-weight-momentum" type="number" min="0" max="100" value="${weights.momentum_6m}" /></label><label>低波权重<input id="pc-weight-lowvol" type="number" min="0" max="100" value="${weights.low_vol_orthogonal}" /></label><label>价值权重<input id="pc-weight-value" type="number" min="0" max="100" value="${weights.value_orthogonal}" /></label></div><div class="panel-actions"><button class="button" type="submit">保存综合方案</button><span id="composite-message">当前合计 ${total}%，必须等于 100%。</span></div></form>`;
}

function approvedFactorList() {
  return BASE_FACTORS.filter((id) => state.factorDecisions[id]?.decision !== "discard").map((id) => `${factorLabel(id)} ${state.factorDecisions[id]?.version || "v1.0"}`).join(" · ") || "暂无已采纳因子";
}

function renderStrategy() {
  const cfg = state.strategyConfig;
  return `<div class="panel-heading"><div><span>第 5 步 / 策略契约</span><h3>策略与风控规则</h3><p>先确认使用的因子版本、持仓数量和防守仓位，再发起回测。</p></div><span class="approval-badge pending">待回测</span></div><div class="contract-grid"><div><span>已批准因子</span><strong>${approvedFactorList()}</strong></div><div><span>执行约束</span><strong>只做多 · 月度调仓 · 信号滞后 1 期</strong></div><div><span>成本</span><strong>买入 5bp · 卖出 10bp</strong></div></div><form id="pc-strategy-form"><div class="config-grid"><label>策略类型<select id="pc-strategy-id"><option value="composite" ${cfg.strategy_id === "composite" ? "selected" : ""}>多因子策略</option><option value="momentum_timing" ${cfg.strategy_id === "momentum_timing" ? "selected" : ""}>动量择时策略</option></select></label><label>持仓数量<select id="pc-top-n"><option value="2" ${cfg.top_n === 2 ? "selected" : ""}>前 2 个</option><option value="3" ${cfg.top_n === 3 ? "selected" : ""}>前 3 个</option><option value="4" ${cfg.top_n === 4 ? "selected" : ""}>前 4 个</option></select></label><label>趋势转弱时仓位<select id="pc-defensive"><option value="0" ${cfg.defensive_exposure === 0 ? "selected" : ""}>0%</option><option value="25" ${cfg.defensive_exposure === 25 ? "selected" : ""}>25%</option><option value="50" ${cfg.defensive_exposure === 50 ? "selected" : ""}>50%</option><option value="75" ${cfg.defensive_exposure === 75 ? "selected" : ""}>75%</option></select></label></div><div class="observer-note"><strong>回测前检查</strong><p>本次会同时计算多因子、动量择时和等权基准，便于横向比较。</p></div><div class="panel-actions"><button class="button" type="submit" ${state.loading ? "disabled" : ""}>${state.loading ? "正在计算并归档…" : "确认并回测"}</button><span id="run-message">运行会为七个阶段分别保存输入和输出。</span></div></form>`;
}

function selectedStrategyResult() {
  return state.payload.strategies?.[state.strategyConfig.strategy_id] || state.payload.strategies?.composite || state.payload.strategies?.momentum_timing;
}

function renderBacktest() {
  const result = selectedStrategyResult();
  if (!result) return `<div class="empty-state">暂无回测结果。</div>`;
  const metrics = result.metrics;
  const checks = state.payload.research_workflow.backtest_quality.checks;
  return `<div class="panel-heading"><div><span>第 6 步 / 报告与校验</span><h3>${escapeHtml(result.label)}回测报告</h3><p>策略和等权基准来自同一次运行；所有数据为合成示例。</p></div><span class="approval-badge approved">规则检查通过</span></div><div class="factor-switcher"><button class="mini-tab ${state.strategyConfig.strategy_id === "composite" ? "selected" : ""}" type="button" data-strategy-view="composite">多因子</button><button class="mini-tab ${state.strategyConfig.strategy_id === "momentum_timing" ? "selected" : ""}" type="button" data-strategy-view="momentum_timing">动量择时</button></div><div class="metric-strip metric-strip-wide"><div><span>累计收益</span><strong>${fmtPct(metrics.cum)}</strong></div><div><span>年化收益</span><strong>${fmtPct(metrics.ann)}</strong></div><div><span>夏普</span><strong>${fmtNum(metrics.sharpe, 2)}</strong></div><div><span>索提诺</span><strong>${fmtNum(metrics.sortino, 2)}</strong></div><div><span>最大回撤</span><strong>${fmtPct(metrics.max_dd)}</strong></div></div><div class="research-chart"><canvas id="research-nav-chart" aria-label="策略和等权基准净值曲线"></canvas><p>实线：${escapeHtml(result.label)} · 虚线：等权基准</p></div><div class="check-list">${checks.map((check) => `<div><span class="check-pass">${check.status === "passed" ? "通过" : "异常"}</span><strong>${escapeHtml(check.name)}</strong><small>${escapeHtml(check.evidence)}</small></div>`).join("")}</div><div class="archive-confirm"><strong>${state.archive ? "已归档" : "未归档"}</strong><span>${state.archive ? `运行号 ${escapeHtml(state.archive.run_id)} · 七阶段输入输出已写入本地。` : "请通过本地服务重新运行。"}</span></div><label class="decision-reason">策略判断依据<input id="strategy-reason" type="text" placeholder="说明为什么采纳、改进或废弃" /></label><div class="panel-actions"><button class="small-button" type="button" data-strategy-decision="adopt">采纳</button><button class="small-button" type="button" data-strategy-decision="adjust">要求改进</button><button class="small-button danger" type="button" data-strategy-decision="discard">废弃</button><button class="button secondary" type="button" data-goto="versions" ${state.strategyDecision ? "" : "disabled"}>查看版本记录</button><span id="strategy-message">请填写判断依据。</span></div>`;
}

function renderVersions() {
  const runs = state.history.runs || [];
  const versionRows = state.payload.research_workflow.version_history || [];
  const decisions = [...state.localDecisionLog].reverse();
  return `<div class="panel-heading"><div><span>第 7 步 / 研究台账</span><h3>版本与研究记录</h3><p>运行、参数和人工决定分别保留，未归档动作会明确标注。</p></div><span class="approval-badge ${state.strategyDecision?.archived ? "approved" : "pending"}">${state.strategyDecision?.archived ? "已归档" : "含本地记录"}</span></div><div class="version-ledger">${versionRows.map((item) => `<div><span>${escapeHtml(item.version_id)}</span><strong>${escapeHtml(VERSION_STATUS_LABELS[item.status] || item.status)}</strong><p>${escapeHtml(item.reason)}</p></div>`).join("")}</div><h4>最近运行</h4>${runs.length ? table(["运行号", "时间", "阶段"], runs.slice(0, 8).map((item) => [escapeHtml(item.run_id), escapeHtml(item.created_at || ""), `${item.stage_count} 阶段`])) : `<div class="empty-state">本地服务暂无运行记录。</div>`}<h4>本轮决策</h4>${decisions.length ? table(["对象", "决定", "状态"], decisions.map((item) => [escapeHtml(item.title), decisionLabel(item.decision), item.archived ? "已归档" : "未归档"])) : `<div class="empty-state">暂无决策记录。</div>`}`;
}

function drawResearchChart() {
  const strategy = selectedStrategyResult();
  const benchmark = state.payload.strategies?.equal_weight;
  const canvas = byId("research-nav-chart");
  if (!canvas || !strategy?.nav?.length || !benchmark?.nav?.length) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || 700;
  const height = canvas.clientHeight || 190;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  ctx.scale(ratio, ratio);
  const series = [strategy.nav.map((point) => Number(point.value)), benchmark.nav.map((point) => Number(point.value))];
  const values = series.flat();
  const min = Math.min(...values) * 0.98;
  const max = Math.max(...values) * 1.02;
  const x = (index, length) => 8 + index / Math.max(1, length - 1) * (width - 16);
  const y = (value) => height - 8 - (value - min) / Math.max(1e-9, max - min) * (height - 16);
  ctx.clearRect(0, 0, width, height);
  series.forEach((points, index) => {
    ctx.beginPath();
    points.forEach((value, pointIndex) => pointIndex ? ctx.lineTo(x(pointIndex, points.length), y(value)) : ctx.moveTo(x(pointIndex, points.length), y(value)));
    ctx.strokeStyle = index === 0 ? "#b5483b" : "#687277";
    ctx.lineWidth = index === 0 ? 2.2 : 1.5;
    ctx.setLineDash(index === 0 ? [] : [6, 5]);
    ctx.stroke();
  });
  ctx.setLineDash([]);
}

function bindStageEvents(stage) {
  if (stage === "config") bindConfigForm();
  document.querySelectorAll("[data-factor]").forEach((button) => button.addEventListener("click", () => { state.factor = button.dataset.factor; saveState(); renderStage("factor"); }));
  document.querySelectorAll("[data-goto]").forEach((button) => button.addEventListener("click", () => renderStage(button.dataset.goto)));
  const runFactor = document.querySelector("[data-run-factor]");
  if (runFactor) runFactor.addEventListener("click", async () => {
    state.loading = true; renderStage("factor");
    try {
      await runPipeline(["momentum", "low_vol", "value", "equal_weight"]);
      state.factorEvaluationComplete = true;
      state.loading = false;
      saveState();
      renderStage("factor");
    } catch (error) {
      state.loading = false;
      renderStage("factor");
      byId("factor-run-message").textContent = `运行失败：${error.message}`;
    } finally { state.loading = false; }
  });
  document.querySelectorAll("[data-decision]").forEach((button) => button.addEventListener("click", async () => {
    const reason = byId("factor-reason").value.trim();
    if (!reason) { byId("factor-decision-message").innerHTML = `<strong>无法保存</strong><p>请先填写判断依据。</p>`; return; }
    const id = button.dataset.factorId;
    const decision = button.dataset.decision;
    const previous = state.factorDecisions[id]?.version || "v1.0";
    const version = decision === "adjust" ? `v1.${Number(previous.split(".")[1] || 0) + 1}` : previous;
    const record = { stage: "factor_pool", object_id: id, decision, reason, version, parameter_change: decision === "adjust" ? { lookback_months: Number(byId("factor-adjust-window").value) } : null };
    const saved = await persistDecision(record, `${factorLabel(id)}：${decisionLabel(decision)}`);
    state.factorDecisions[id] = { decision, reason, version, archived: saved.archived, parameter_change: record.parameter_change };
    saveState();
    renderStage("factor-approval");
  }));
  const compositeForm = byId("pc-composite-form");
  if (compositeForm) compositeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const weights = { momentum_6m: Number(byId("pc-weight-momentum").value), low_vol_orthogonal: Number(byId("pc-weight-lowvol").value), value_orthogonal: Number(byId("pc-weight-value").value) };
    const total = Object.values(weights).reduce((sum, value) => sum + value, 0);
    if (total !== 100 || Object.values(weights).some((value) => value < 0)) { byId("composite-message").textContent = "三项非负权重合计必须为 100%。"; return; }
    state.compositeWeights = weights;
    state.compositeApproved = true;
    await persistDecision({ stage: "factor_improvement", object_id: "composite_v1", decision: "adopt", reason: `正交化后按 ${weights.momentum_6m}/${weights.low_vol_orthogonal}/${weights.value_orthogonal} 合成`, version: "v1.0" }, "综合因子：采纳");
    saveState();
    renderStage("strategy");
  });
  const strategyForm = byId("pc-strategy-form");
  if (strategyForm) strategyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    state.strategyConfig = { strategy_id: byId("pc-strategy-id").value, top_n: Number(byId("pc-top-n").value), defensive_exposure: Number(byId("pc-defensive").value) };
    state.loading = true; saveState(); renderStage("strategy");
    try {
      await runPipeline(["composite", "momentum_timing", "equal_weight"]);
      state.backtestComplete = true;
      state.loading = false;
      saveState();
      renderStage("backtest");
    } catch (error) {
      state.loading = false;
      renderStage("strategy");
      byId("run-message").textContent = `运行失败：${error.message}`;
    } finally { state.loading = false; }
  });
  document.querySelectorAll("[data-strategy-view]").forEach((button) => button.addEventListener("click", () => { state.strategyConfig.strategy_id = button.dataset.strategyView; saveState(); renderStage("backtest"); }));
  document.querySelectorAll("[data-strategy-decision]").forEach((button) => button.addEventListener("click", async () => {
    const reason = byId("strategy-reason").value.trim();
    if (!reason) { byId("strategy-message").textContent = "请先填写判断依据。"; return; }
    const decision = button.dataset.strategyDecision;
    const version = decision === "adjust" ? "v1.1" : "v1.0";
    const saved = await persistDecision({ stage: "strategy_review", object_id: state.strategyConfig.strategy_id, decision, reason, version }, `${selectedStrategyResult().label}：${decisionLabel(decision)}`);
    state.strategyDecision = { decision, reason, version, archived: saved.archived };
    saveState();
    renderStage("versions");
  }));
  if (stage === "backtest") window.setTimeout(drawResearchChart, 0);
}

function aiSummaryFor(stage) {
  const [title, advice] = stageAdvice(stage);
  if (stage === "factor") {
    const factor = state.payload.factor_research?.[state.factor];
    const summary = factor?.tables?.ic_summary || {};
    return { event: `${factorLabel(state.factor)}已生成因子证据。`, evidence: `Rank IC ${fmtNum(summary.mean)}，ICIR ${fmtNum(summary.icir)}，G1-G5 ${fmtPct(factor?.tables?.g1_g5_long_short)}。`, risk: advice, next: "先检查分组单调性和验证期稳定性，再决定采纳、调整或废弃。" };
  }
  if (stage === "backtest") {
    const result = selectedStrategyResult();
    return { event: `${result?.label || "策略"}已完成回测与规则检查。`, evidence: `年化收益 ${fmtPct(result?.metrics?.ann)}，夏普 ${fmtNum(result?.metrics?.sharpe, 2)}，最大回撤 ${fmtPct(result?.metrics?.max_dd)}。`, risk: "合成样本只能验证流程，不能解释为真实投资收益。", next: "核对独立验证结果后，记录采纳、改进或废弃原因。" };
  }
  return { event: `${STAGE_NAMES[stage]}处于${isStageDone(stage) ? "已完成" : "待处理"}状态。`, evidence: advice, risk: stage === "config" ? "修改样本切分会使后续结果失效。" : "任何 AI 建议都不会自动修改研究对象。", next: title === "配置检查" ? "保存研究输入后运行单因子测试。" : advice };
}

function renderAiSummary(stage) {
  const target = byId("stage-advice");
  if (!target) return;
  const summary = aiSummaryFor(stage);
  target.innerHTML = `<h3>AI研究小结</h3><div><strong>发生了什么</strong><p>${escapeHtml(summary.event)}</p></div><div><strong>证据</strong><p>${escapeHtml(summary.evidence)}</p></div><div><strong>风险点</strong><p>${escapeHtml(summary.risk)}</p></div><div><strong>下一步建议</strong><p>${escapeHtml(summary.next)}</p></div><div class="pc-ai-summary-actions"><button type="button" data-ai-advice="adopt">采用建议</button><button type="button" data-ai-advice="hold">暂不处理</button></div>`;
  target.querySelectorAll("[data-ai-advice]").forEach((button) => button.addEventListener("click", () => {
    button.parentElement.innerHTML = `<span>${button.dataset.aiAdvice === "adopt" ? "已记录：采用建议" : "已记录：暂不处理"}</span>`;
  }));
}

function renderValidationPanel() {
  const validation = state.payload.independent_validation;
  const target = byId("validation-panel");
  const chip = byId("validation-status");
  if (!target || !chip) return;
  if (!validation) {
    chip.textContent = "等待检查";
    chip.dataset.level = "pending";
    target.innerHTML = `<h3>独立验证</h3><p>运行后检查时间顺序、成本、公式与重复计算一致性。</p>`;
    return;
  }
  const findings = validation.findings || [];
  const level = validation.level || "green";
  chip.textContent = level === "red" ? "阻断" : level === "yellow" ? "有风险" : "已通过";
  chip.dataset.level = level;
  target.innerHTML = `<h3>独立验证</h3><p>${escapeHtml(validation.summary || "检查完成")}</p><ul>${findings.slice(0, 4).map((item) => `<li data-level="${escapeHtml(item.level)}"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.message)}</span></li>`).join("")}</ul>`;
}

function renderStage(stage) {
  if (!isStageUnlocked(stage)) return;
  state.stage = stage;
  const renderers = { config: renderConfig, factor: renderFactor, "factor-approval": renderFactorApproval, composite: renderComposite, strategy: renderStrategy, backtest: renderBacktest, versions: renderVersions };
  byId("workspace-content").innerHTML = renderers[stage]();
  byId("workflow-status").textContent = `当前阶段：${STAGE_NAMES[stage]}`;
  renderWorkflowBoard();
  bindStageEvents(stage);
  renderAiSummary(stage);
  renderValidationPanel();
  saveState();
}

function validateConfig(next) {
  const dates = [next.start, next.train_end, next.validation_start, next.validation_end, next.end].map((value) => new Date(value));
  if (dates.some((date) => Number.isNaN(date.getTime()))) return "请填写完整日期。";
  if (!(dates[0] < dates[1] && dates[1] < dates[2] && dates[2] <= dates[3] && dates[3] < dates[4])) return "日期应按训练期、验证期、留出集依次排列。";
  return "";
}

function hydrateConfigInputs() {
  if (!byId("config-asset-type")) return;
  const cfg = state.configValues || defaultConfig(state.payload);
  byId("config-asset-type").value = cfg.asset_type;
  byId("config-universe").value = cfg.universe_id;
  byId("config-frequency").value = cfg.frequency;
  byId("config-start").value = cfg.start;
  byId("config-end").value = cfg.end;
  byId("config-train-end").value = cfg.train_end;
  byId("config-validation-start").value = cfg.validation_start;
  byId("config-validation-end").value = cfg.validation_end;
  byId("config-benchmark").value = cfg.benchmark;
  byId("config-lag").value = String(cfg.signal_lag);
  byId("config-cost").value = cfg.cost_model;
}

function bindConfigForm() {
  const form = byId("research-config");
  if (!form) return;
  hydrateConfigInputs();
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const next = {
      asset_type: byId("config-asset-type").value,
      universe_id: byId("config-universe").value,
      benchmark: byId("config-benchmark").value,
      frequency: byId("config-frequency").value,
      start: byId("config-start").value,
      end: byId("config-end").value,
      train_end: byId("config-train-end").value,
      validation_start: byId("config-validation-start").value,
      validation_end: byId("config-validation-end").value,
      signal_lag: Number(byId("config-lag").value),
      cost_model: byId("config-cost").value,
    };
    const error = validateConfig(next);
    if (error) { byId("config-message").textContent = error; return; }
    next.sample_split = {
      train: { start: next.start, end: next.train_end },
      validation: { start: next.validation_start, end: next.validation_end },
      holdout: { start: next.validation_end, end: next.end, purpose: "final review only" },
    };
    state.configValues = next;
    state.configLocked = true;
    state.factorEvaluationComplete = false;
    state.factorDecisions = {};
    state.compositeApproved = false;
    state.backtestComplete = false;
    state.strategyDecision = null;
    state.archive = null;
    byId("config-message").textContent = "已保存。因子测试将使用这份输入快照。";
    saveState();
    renderStage("factor");
  });
}

function syncResearchMode() {
  document.querySelectorAll("[data-research-mode]").forEach((button) => {
    const active = button.dataset.researchMode === state.researchMode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  byId("mode-description").textContent = state.researchMode === "autonomous"
    ? "AI自主研究模式：AI可连续执行，但研究方案与因子阶段仍需用户批准。"
    : "专业研究模式：每个关键阶段由用户审批。";
}

function setupModeAndGuide() {
  document.querySelectorAll("[data-research-mode]").forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.researchMode === state.researchMode) return;
    state.researchMode = button.dataset.researchMode;
    saveState();
    syncResearchMode();
  }));
  const guide = byId("pc-guide");
  const spotlight = byId("pc-guide-spotlight");
  const tour = [
    [".pc-project-strip", "先确定研究范围", "先确定标的、历史区间、训练集与验证集、信号滞后和交易成本。锁定后，后续结果才有统一口径。"],
    [".workflow-step[data-workflow=\"config\"]", "01 研究配置", "这里是研究的起点：保存输入条件，并检查日期顺序、样本区间和执行滞后。"],
    [".workflow-step[data-workflow=\"factor\"]", "02 单因子评估", "查看动量、低波、价值等因子的公式、经济意义、IC、ICIR、分组收益和敏感性。"],
    [".workflow-step[data-workflow=\"factor-approval\"]", "03 因子审批", "每个因子都要明确采纳、调整或废弃；调整会生成新版本，废弃也会留下原因。"],
    [".workflow-step[data-workflow=\"composite\"]", "04 因子改进", "在这里进行标准化、正交化和加权，形成综合因子，并保留改进前后的差异。"],
    [".workflow-step[data-workflow=\"strategy\"]", "05 策略设计", "明确使用哪些因子、如何选股或选指数、多久调仓，以及仓位和风控边界。"],
    [".workflow-step[data-workflow=\"backtest\"]", "06 回测质检", "回测输出净值、收益、夏普、索提诺、最大回撤、换手和成本；独立验证模块检查前视和漂移。"],
    [".workflow-step[data-workflow=\"versions\"]", "07 版本记录", "所有配置、结果和人工决定都能在历史记录中找到，方便比较和复盘。"],
    [".pc-ai-rail", "AI 研究助手与独立验证", "AI 负责整理想法、解释结果和提出下一步建议；独立验证只检查结构化输入和输出，不替用户做投资判断。"],
  ];
  let tourIndex = 0;
  const clearSpotlight = () => { document.querySelectorAll(".guide-tour-target").forEach((node) => node.classList.remove("guide-tour-target")); spotlight.hidden = true; };
  const renderTour = () => {
    const [selector, title, copy] = tour[tourIndex];
    byId("pc-guide-progress").textContent = `第 ${tourIndex + 1} / ${tour.length} 步`;
    byId("pc-guide-title").textContent = title;
    byId("pc-guide-copy").textContent = copy;
    const previous = guide.querySelector("[data-guide-prev]");
    const next = guide.querySelector("[data-guide-next]");
    previous.disabled = tourIndex === 0;
    next.textContent = tourIndex === tour.length - 1 ? "完成指引" : "下一步";
    clearSpotlight();
    const target = document.querySelector(selector);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    target.classList.add("guide-tour-target");
    window.setTimeout(() => { const rect = target.getBoundingClientRect(); spotlight.hidden = false; spotlight.style.top = `${Math.max(8, rect.top - 8)}px`; spotlight.style.left = `${Math.max(8, rect.left - 8)}px`; spotlight.style.width = `${rect.width + 16}px`; spotlight.style.height = `${rect.height + 16}px`; }, 180);
  };
  const openGuide = () => { guide.hidden = false; document.body.classList.add("guide-open"); tourIndex = 0; renderTour(); };
  const closeGuide = () => { guide.hidden = true; document.body.classList.remove("guide-open"); clearSpotlight(); };
  byId("pc-guide-button").addEventListener("click", openGuide);
  guide.querySelectorAll("[data-guide-close]").forEach((button) => button.addEventListener("click", closeGuide));
  guide.querySelector("[data-guide-prev]").addEventListener("click", () => { if (tourIndex > 0) { tourIndex -= 1; renderTour(); } });
  guide.querySelector("[data-guide-next]").addEventListener("click", () => { if (tourIndex === tour.length - 1) { closeGuide(); renderStage("config"); } else { tourIndex += 1; renderTour(); } });
  guide.addEventListener("click", (event) => { if (event.target === guide) closeGuide(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !guide.hidden) closeGuide(); });
  syncResearchMode();
  openGuide();
}

async function boot() {
  state.payload = await loadPayload();
  state.configValues = defaultConfig(state.payload);
  restoreState();
  await restoreArchivedPayload();
  state.history = await loadHistory();
  setupAssistant();
  setupModeAndGuide();
  if (state.assistantPlan) {
    byId("assistant-input").value = state.assistantPlan.raw || "";
    renderAssistantResult(state.assistantPlan);
  }
  const safeStage = isStageUnlocked(state.stage) ? state.stage : STAGES.filter(isStageUnlocked).at(-1) || "config";
  renderStage(safeStage);
}

document.addEventListener("DOMContentLoaded", () => boot().catch((error) => {
  byId("workspace-content").innerHTML = `<div class="empty-state">页面加载失败：${escapeHtml(error.message)}</div>`;
}));

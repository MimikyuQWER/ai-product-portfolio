const wealthById = (id) => document.getElementById(id);
const wealthEscape = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const wealthPercent = (value, digits = 1) => value == null ? "—" : `${(Number(value) * 100).toFixed(digits)}%`;
const wealthNumber = (value, digits = 2) => value == null ? "—" : Number(value).toFixed(digits);

const WEALTH_STORAGE_KEY = "wealth-research-state-v2";
const BASE_FACTORS = ["momentum_6m", "low_vol_6m", "pb"];
const FACTOR_LABELS = {
  momentum_6m: "六个月动量",
  low_vol_6m: "低波动",
  pb: "价值",
  low_vol_orthogonal: "正交低波",
  value_orthogonal: "正交价值",
  composite_v1: "综合因子",
};
const STAGES = [
  { id: "config", title: "研究范围", note: "标的、区间和成本" },
  { id: "factor", title: "信号表现", note: "公式、指标和敏感性" },
  { id: "approval", title: "因子选择", note: "采纳、调整或废弃" },
  { id: "composite", title: "组合方案", note: "正交化和权重" },
  { id: "strategy", title: "策略规则", note: "持仓、调仓和风控" },
  { id: "backtest", title: "回测结果", note: "收益、风险和检查" },
  { id: "versions", title: "研究记录", note: "版本和决策" },
];

const wealthState = {
  payload: null,
  history: { runs: [], decisions: [] },
  config: null,
  configLocked: false,
  factorRun: false,
  factor: "momentum_6m",
  factorFilter: "all",
  factorDecisions: {},
  pendingDecision: null,
  compositeApproved: false,
  strategyReady: false,
  backtestCompleted: false,
  strategyId: "composite",
  factorWeights: { momentum_6m: 50, low_vol_orthogonal: 30, value_orthogonal: 20 },
  topN: 3,
  defensiveExposure: 50,
  archive: null,
  strategyDecision: null,
  plan: null,
  researchMode: "autonomous",
  records: [],
  loading: false,
};

function defaultConfig(payload) {
  const config = payload.config;
  return {
    asset_type: config.asset_type || "index",
    universe_id: config.universe_id || "synthetic_sector_8",
    benchmark: config.benchmark || "equal_weight",
    start: config.start,
    end: config.end,
    train_end: config.sample_split.train.end,
    validation_start: config.sample_split.validation.start,
    validation_end: config.sample_split.validation.end,
    frequency: config.frequency || "monthly",
    signal_lag: Number(config.signal_lag ?? 1),
    cost_model: config.cost_model,
  };
}

function restoreState() {
  try {
    const saved = JSON.parse(localStorage.getItem(WEALTH_STORAGE_KEY) || "null");
    if (!saved) return;
    ["config", "configLocked", "factorRun", "factor", "factorFilter", "factorDecisions", "compositeApproved", "strategyReady", "backtestCompleted", "strategyId", "factorWeights", "topN", "defensiveExposure", "archive", "strategyDecision", "plan", "records", "researchMode"].forEach((key) => {
      if (saved[key] !== undefined) wealthState[key] = saved[key];
    });
  } catch (error) {
    localStorage.removeItem(WEALTH_STORAGE_KEY);
  }
}

function saveState() {
  const value = {};
  ["config", "configLocked", "factorRun", "factor", "factorFilter", "factorDecisions", "compositeApproved", "strategyReady", "backtestCompleted", "strategyId", "factorWeights", "topN", "defensiveExposure", "archive", "strategyDecision", "plan", "records", "researchMode"].forEach((key) => { value[key] = wealthState[key]; });
  localStorage.setItem(WEALTH_STORAGE_KEY, JSON.stringify(value));
}

function resetResearchProgress() {
  wealthState.config = defaultConfig(wealthState.payload);
  wealthState.configLocked = false;
  wealthState.factorRun = false;
  wealthState.factor = "momentum_6m";
  wealthState.factorDecisions = {};
  wealthState.pendingDecision = null;
  wealthState.compositeApproved = false;
  wealthState.strategyReady = false;
  wealthState.backtestCompleted = false;
  wealthState.strategyId = "composite";
  wealthState.factorWeights = { momentum_6m: 50, low_vol_orthogonal: 30, value_orthogonal: 20 };
  wealthState.topN = 3;
  wealthState.defensiveExposure = 50;
  wealthState.archive = null;
  wealthState.strategyDecision = null;
}

async function wealthLoadPayload() {
  const response = await fetch("data/demo-run.json", { cache: "no-store" });
  if (!response.ok) throw new Error("研究数据加载失败，请刷新后重试");
  return response.json();
}

async function wealthLoadHistory() {
  try {
    const response = await fetch("/api/research/history", { cache: "no-store" });
    if (!response.ok) return { runs: [], decisions: [] };
    return response.json();
  } catch (error) {
    return { runs: [], decisions: [] };
  }
}

function hydrateArchivedRun(payload, runId) {
  const input = payload.archived_input || {};
  wealthState.payload = payload;
  wealthState.config = { ...defaultConfig(payload), ...input };
  wealthState.configLocked = true;
  wealthState.factorRun = true;
  wealthState.factorDecisions = input.factor_decisions || wealthState.factorDecisions;
  wealthState.compositeApproved = input.composite_approved !== false;
  if (input.factor_weights) wealthState.factorWeights = Object.fromEntries(Object.entries(input.factor_weights).map(([key, value]) => [key, Math.round(Number(value) * 100)]));
  wealthState.strategyId = (input.strategy_ids || []).find((id) => id !== "equal_weight") || "composite";
  wealthState.topN = Number(input.top_n ?? wealthState.topN);
  wealthState.defensiveExposure = Math.round(Number(input.defensive_exposure ?? wealthState.defensiveExposure / 100) * 100);
  wealthState.strategyReady = true;
  wealthState.backtestCompleted = true;
  wealthState.strategyDecision = input.strategy_decision || null;
  wealthState.archive = payload.archive || { run_id: runId };
}

async function restoreActiveRun() {
  const runId = wealthState.archive?.run_id;
  if (!runId || !wealthState.backtestCompleted) return;
  const response = await fetch(`/api/research/run/${encodeURIComponent(runId)}`, { cache: "no-store" });
  if (!response.ok) throw new Error("已保存的运行记录暂时不可用");
  const result = await response.json();
  hydrateArchivedRun(result.payload, runId);
}

function showToast(message, tone = "info") {
  const toast = wealthById("wealth-toast");
  toast.textContent = message;
  toast.dataset.tone = tone;
  toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => { toast.hidden = true; }, 2600);
}

function completedStageCount() {
  const factorApproved = BASE_FACTORS.every((id) => Boolean(wealthState.factorDecisions[id]?.decision))
    && BASE_FACTORS.some((id) => wealthState.factorDecisions[id]?.decision !== "discard");
  return [wealthState.configLocked, wealthState.factorRun, factorApproved, wealthState.compositeApproved, wealthState.strategyReady, wealthState.backtestCompleted, Boolean(wealthState.strategyDecision)].filter(Boolean).length;
}

function stageStatus(id) {
  const index = STAGES.findIndex((stage) => stage.id === id);
  const completed = completedStageCount();
  if (index < completed) return "done";
  if (index === completed) return "current";
  return "locked";
}

function canEnterStage(id) {
  const index = STAGES.findIndex((stage) => stage.id === id);
  return index <= completedStageCount();
}

function parseRoute() {
  const raw = (location.hash || "#home").slice(1);
  const parts = raw.split("/").filter(Boolean);
  if (parts[0] === "research" && parts[1]) return { type: "stage", id: parts[1] };
  if (parts[0] === "detail" && parts[1] === "factor" && parts[2]) return { type: "factor-detail", id: parts[2] };
  return { type: "root", id: ["home", "library", "strategies", "records"].includes(parts[0]) ? parts[0] : "home" };
}

function go(route) {
  const next = route.startsWith("#") ? route : `#${route}`;
  if (location.hash === next) renderRoute();
  else location.hash = next;
}

function pageMeta(route) {
  if (route.type === "stage") return { title: STAGES.find((stage) => stage.id === route.id)?.title || "策略研究", subtitle: `${STAGES.findIndex((stage) => stage.id === route.id) + 1}/7` };
  if (route.type === "factor-detail") return { title: FACTOR_LABELS[route.id] || "因子详情", subtitle: "数据与方法" };
  return {
    home: { title: "策略研究", subtitle: "手机 APP 版" },
    library: { title: "因子库", subtitle: "研究记录" },
    strategies: { title: "策略", subtitle: "候选方案" },
    records: { title: "记录", subtitle: "运行与决策" },
  }[route.id];
}

function updateChrome(route) {
  const meta = pageMeta(route);
  wealthById("wealth-title").textContent = meta.title;
  wealthById("wealth-subtitle").textContent = meta.subtitle;
  wealthById("wealth-back").hidden = route.type === "root";
  wealthById("wealth-home").hidden = route.type === "root" && route.id === "home";
  document.querySelectorAll("[data-root-route]").forEach((button) => {
    const active = route.type === "root" && button.dataset.rootRoute === route.id;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
}

function stageHeader(id, summary) {
  const index = STAGES.findIndex((stage) => stage.id === id);
  return `<div class="wealth-stage-heading"><div><span>第 ${index + 1} 步，共 7 步</span><h1>${STAGES[index].title}</h1>${summary ? `<p>${summary}</p>` : ""}</div><div class="wealth-stage-index">${index + 1}<small>/7</small></div></div><div class="wealth-stage-line" aria-label="研究进度">${STAGES.map((stage, stageIndex) => `<span class="${stageIndex < index ? "done" : stageIndex === index ? "current" : ""}"></span>`).join("")}</div>`;
}

function renderHome() {
  const count = completedStageCount();
  const next = STAGES[Math.min(count, STAGES.length - 1)];
  const lastRun = wealthState.archive?.run_id;
  return `<section class="wealth-home-summary">
      <div class="wealth-home-copy"><h1>策略研究</h1><p>把研究想法转成可验证的策略。</p></div>
      <span class="wealth-demo-tag">合成数据</span>
      <div class="wealth-project-card">
        <div><small>当前研究</small><strong>${wealthState.plan?.title ? wealthEscape(wealthState.plan.title) : "行业多因子研究"}</strong><p>${count === 7 ? "研究已完成" : `下一步：${next.title}`}</p></div>
        <button class="wealth-primary" type="button" data-route="research/${next.id}">${count ? "继续研究" : "开始配置"}</button>
      </div>
      <div class="wealth-progress-summary"><span style="width:${Math.max(5, count / 7 * 100)}%"></span></div>
      <div class="wealth-progress-copy"><span>已完成 ${count}/7</span>${lastRun ? `<span>运行号 ${wealthEscape(lastRun)}</span>` : "<span>尚未回测</span>"}</div>
    </section>
    <section class="wealth-mode-section"><div><span>研究模式</span><strong>${wealthState.researchMode === "autonomous" ? "AI自主研究" : "专业研究"}</strong><p>${wealthState.researchMode === "autonomous" ? "AI连续执行，方案和因子阶段仍由你批准。" : "你主导每个阶段，AI负责整理与解释。"}</p></div><div class="wealth-mode-switch"><button type="button" data-wealth-mode="professional" class="${wealthState.researchMode === "professional" ? "active" : ""}">专业</button><button type="button" data-wealth-mode="autonomous" class="${wealthState.researchMode === "autonomous" ? "active" : ""}">AI自主</button></div></section>
    <section class="wealth-section">
      <div class="wealth-section-head"><h2>新建研究</h2><button type="button" data-fill-idea="我想把动量、价值和低波合成一个月度多因子策略，并比较正交化前后的结果。">使用示例</button></div>
      <form id="wealth-idea-form" class="wealth-idea-form">
        <label for="wealth-idea">研究想法</label>
        <textarea id="wealth-idea" rows="3" placeholder="例如：用六个月动量选择三个指数，趋势转弱时降低仓位。">${wealthEscape(wealthState.plan?.raw || "")}</textarea>
        <button class="wealth-primary" type="submit">整理方案</button>
      </form>
      <div id="wealth-plan-result">${wealthState.plan ? renderPlanResult(wealthState.plan) : ""}</div>
    </section>
    <section class="wealth-section">
      <div class="wealth-section-head"><h2>研究步骤</h2><span>按顺序完成</span></div>
      <div class="wealth-stage-list">${STAGES.map((stage, index) => {
        const status = stageStatus(stage.id);
        const label = status === "done" ? "已完成" : status === "current" ? "待完成" : "未开始";
        return `<button type="button" data-stage-route="${stage.id}" class="${status}" ${status === "locked" ? "disabled" : ""}><span>${index + 1}</span><div><strong>${stage.title}</strong><small>${stage.note}</small></div><em>${label}</em><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg></button>`;
      }).join("")}</div>
    </section>
    <p class="wealth-disclaimer">本页面为作品集概念演示，不提供投资建议。</p>`;
}

function renderPlanResult(plan) {
  const items = plan.recognized.slice(0, 4).map(([key, value]) => `<span><small>${wealthEscape(key)}</small>${wealthEscape(value)}</span>`).join("");
  return `<div class="wealth-plan-result"><div><strong>${wealthEscape(plan.title)}</strong><span>${plan.missing.length ? "待补充" : "已识别"}</span></div><p>${wealthEscape(plan.proposal)}</p><section>${items}</section><details class="wealth-source-list"><summary>研究依据 · ${(plan.sources || []).length} 项</summary>${(plan.sources || []).map((source) => `<a href="${wealthEscape(source.url)}" target="_blank" rel="noreferrer"><strong>${wealthEscape(source.title)}</strong><small>${wealthEscape(source.type)} · ${wealthEscape(source.year)}</small></a>`).join("")}</details><button class="wealth-secondary" type="button" data-accept-plan>采用并配置</button></div>`;
}

function renderConfig() {
  const config = wealthState.config;
  return `${stageHeader("config", "先固定研究范围。")}
    <form id="wealth-config-form" class="wealth-form-page">
      <section class="wealth-form-section"><h2>研究对象</h2>
        <label>资产类型<select id="wealth-asset"><option value="index" ${config.asset_type === "index" ? "selected" : ""}>指数</option><option value="stock" ${config.asset_type === "stock" ? "selected" : ""}>股票</option><option value="fund" ${config.asset_type === "fund" ? "selected" : ""}>基金</option><option value="bond" ${config.asset_type === "bond" ? "selected" : ""}>债券</option></select></label>
        <label>标的范围<select id="wealth-universe"><option value="synthetic_sector_8">行业指数池 · 8 个标的</option></select></label>
        <label>比较基准<select id="wealth-benchmark"><option value="equal_weight">等权基准</option></select></label>
      </section>
      <section class="wealth-form-section"><h2>回测区间</h2>
        <div class="wealth-two-fields"><label>开始日期<input id="wealth-start" type="date" value="${wealthEscape(config.start)}" /></label><label>结束日期<input id="wealth-end" type="date" value="${wealthEscape(config.end)}" /></label></div>
        <div class="wealth-split-preview"><span><b>训练</b>开始至 ${wealthEscape(config.train_end)}</span><span><b>验证</b>${wealthEscape(config.validation_start)} 至 ${wealthEscape(config.validation_end)}</span><span><b>留出</b>${wealthEscape(config.validation_end)} 之后</span></div>
        <details><summary>调整样本切分</summary><div class="wealth-two-fields"><label>训练集结束<input id="wealth-train-end" type="date" value="${wealthEscape(config.train_end)}" /></label><label>验证集结束<input id="wealth-validation-end" type="date" value="${wealthEscape(config.validation_end)}" /></label></div></details>
      </section>
      <section class="wealth-form-section"><h2>交易设置</h2>
        <div class="wealth-setting-row"><span><strong>月度调仓</strong><small>每月检查一次目标持仓</small></span><b>已选</b></div>
        <div class="wealth-setting-row"><span><strong>信号滞后 1 期</strong><small>本期信号最早用于下一期</small></span><b>必选</b></div>
        <div class="wealth-setting-row"><span><strong>交易成本</strong><small>买入 5bp，卖出 10bp</small></span><b>已计入</b></div>
      </section>
      <div id="wealth-config-error" class="wealth-inline-error" hidden></div>
      <button class="wealth-primary wealth-sticky-action" type="submit">保存并继续</button>
    </form>`;
}

function factorSummary(factorId) {
  const factor = wealthState.payload.factor_research?.[factorId];
  const summary = factor?.summary || {};
  const full = summary.full || factor?.tables?.ic_summary || {};
  return { factor, full, train: summary.train || {}, validation: summary.validation || {} };
}

function evidenceAdvice(factorId) {
  const { train, validation } = factorSummary(factorId);
  const trainIc = Number(train.mean || 0);
  const validationIc = Number(validation.mean || 0);
  if (trainIc === 0 && validationIc === 0) return "样本内外都未显示稳定方向，建议先调整口径。";
  if (Math.sign(trainIc) !== Math.sign(validationIc)) return `训练期与验证期方向不同：${wealthNumber(trainIc, 3)} / ${wealthNumber(validationIc, 3)}。`;
  const change = trainIc ? Math.abs((validationIc - trainIc) / trainIc) : 0;
  return change > 0.5 ? `验证期变化较大：${wealthNumber(trainIc, 3)} → ${wealthNumber(validationIc, 3)}。` : `训练期与验证期方向一致：${wealthNumber(trainIc, 3)} / ${wealthNumber(validationIc, 3)}。`;
}

function renderFactor() {
  const factorId = wealthState.factor;
  const { factor, full, train, validation } = factorSummary(factorId);
  if (!factor) return `${stageHeader("factor", "先运行因子测试。")}<div class="wealth-empty"><strong>暂无因子结果</strong><p>返回研究范围检查日期设置。</p></div>`;
  const group = factor.tables?.group_mean_return || {};
  return `${stageHeader("factor", "看结果，也看稳定性。")}
    <div class="wealth-segmented">${BASE_FACTORS.map((id) => `<button type="button" data-factor="${id}" class="${id === factorId ? "active" : ""}">${FACTOR_LABELS[id]}</button>`).join("")}</div>
    <section class="wealth-factor-summary"><div><h2>${FACTOR_LABELS[factorId]}</h2><small>${wealthState.factorRun ? "本次运行" : "预置样例"}</small><p>${wealthEscape(factor.definition?.economic_meaning)}</p></div><button type="button" data-route="detail/factor/${factorId}">查看口径</button></section>
    <section class="wealth-key-metrics"><div><span>Rank IC</span><strong>${wealthNumber(full.mean, 3)}</strong></div><div><span>ICIR</span><strong>${wealthNumber(full.icir, 2)}</strong></div><div><span>胜率</span><strong>${wealthPercent(full.win_rate)}</strong></div></section>
    <section class="wealth-section wealth-compact-section"><div class="wealth-section-head"><h2>样本对比</h2><span>Rank IC</span></div><div class="wealth-sample-compare"><div><span>训练期</span><strong>${wealthNumber(train.mean, 3)}</strong><small>ICIR ${wealthNumber(train.icir, 2)}</small></div><div><span>验证期</span><strong>${wealthNumber(validation.mean, 3)}</strong><small>ICIR ${wealthNumber(validation.icir, 2)}</small></div></div></section>
    <section class="wealth-section wealth-compact-section"><div class="wealth-section-head"><h2>五组收益</h2><span>单期均值</span></div><div class="wealth-group-bars">${Object.entries(group).map(([key, value]) => `<div><span>${key}</span><i><b style="width:${Math.min(100, Math.max(4, Math.abs(Number(value)) * 3500))}%"></b></i><strong>${wealthPercent(value, 2)}</strong></div>`).join("")}</div></section>
    <aside class="wealth-review-note"><strong>结果提示</strong><p>${evidenceAdvice(factorId)}</p><button type="button" data-route="detail/factor/${factorId}">查看完整数据</button></aside>
    <button class="wealth-primary wealth-sticky-action" type="button" data-run-factors ${wealthState.loading ? "disabled" : ""}>${wealthState.loading ? "正在计算" : wealthState.factorRun ? "重新测试" : "运行因子测试"}</button>`;
}

function renderFactorDetail(factorId) {
  const { factor, train, validation } = factorSummary(factorId);
  if (!factor) return `<div class="wealth-empty"><strong>暂无数据</strong></div>`;
  const sensitivity = Object.entries(factor.sensitivity?.forward_periods || {});
  const yearly = Object.entries(factor.yearly || {}).slice(-5);
  const group = factor.tables?.group_mean_return || {};
  return `<section class="wealth-detail-page"><h1>${FACTOR_LABELS[factorId]}</h1><p>${wealthEscape(factor.definition?.economic_meaning)}</p>
    <section><h2>计算口径</h2><dl class="wealth-definition-list"><div><dt>公式</dt><dd>${wealthEscape(factor.definition?.formula)}</dd></div><div><dt>方向</dt><dd>${factor.definition?.direction === "higher_is_better" ? "数值越高越优" : "数值越低越优"}</dd></div><div><dt>时间规则</dt><dd>滞后 ${factor.definition?.lag_periods} 期，预测 ${factor.definition?.forward_periods} 期</dd></div></dl></section>
    <section><h2>样本表现</h2><div class="wealth-table-wrap"><table><thead><tr><th>样本</th><th>Rank IC</th><th>ICIR</th><th>胜率</th></tr></thead><tbody><tr><td>训练期</td><td>${wealthNumber(train.mean, 3)}</td><td>${wealthNumber(train.icir, 2)}</td><td>${wealthPercent(train.win_rate)}</td></tr><tr><td>验证期</td><td>${wealthNumber(validation.mean, 3)}</td><td>${wealthNumber(validation.icir, 2)}</td><td>${wealthPercent(validation.win_rate)}</td></tr></tbody></table></div></section>
    <section><h2>分组收益</h2><div class="wealth-table-wrap"><table><thead><tr>${Object.keys(group).map((key) => `<th>${key}</th>`).join("")}</tr></thead><tbody><tr>${Object.values(group).map((value) => `<td>${wealthPercent(value, 2)}</td>`).join("")}</tr></tbody></table></div><p class="wealth-method-note">G1-G5 多空收益：${wealthPercent(factor.tables?.g1_g5_long_short, 2)}</p></section>
    <section><h2>敏感性</h2><div class="wealth-table-wrap"><table><thead><tr><th>持有期</th><th>Rank IC</th><th>ICIR</th></tr></thead><tbody>${sensitivity.map(([period, item]) => `<tr><td>${period} 期</td><td>${wealthNumber(item.rank_ic_mean, 3)}</td><td>${wealthNumber(item.rank_icir, 2)}</td></tr>`).join("")}</tbody></table></div></section>
    <section><h2>年度稳定性</h2><div class="wealth-table-wrap"><table><thead><tr><th>年份</th><th>Rank IC</th><th>ICIR</th></tr></thead><tbody>${yearly.map(([year, item]) => `<tr><td>${year}</td><td>${wealthNumber(item.mean, 3)}</td><td>${wealthNumber(item.icir, 2)}</td></tr>`).join("")}</tbody></table></div></section>
    <section><h2>研究记录</h2><p>平均换手率 ${wealthPercent(factor.summary?.turnover_mean)}。审批时会绑定当前公式、样本切分和运行版本。</p></section>
  </section>`;
}

function renderApproval() {
  const allDone = BASE_FACTORS.every((id) => wealthState.factorDecisions[id]?.decision);
  const hasActiveFactor = BASE_FACTORS.some((id) => wealthState.factorDecisions[id]?.decision && wealthState.factorDecisions[id]?.decision !== "discard");
  return `${stageHeader("approval", "逐个确认因子。")}
    <div class="wealth-decision-list">${BASE_FACTORS.map((id) => {
      const decision = wealthState.factorDecisions[id];
      const status = decision ? ({ adopt: "已采纳", adjust: "已调整", discard: "已废弃" }[decision.decision]) : "待决定";
      return `<section><button type="button" data-route="detail/factor/${id}"><span><strong>${FACTOR_LABELS[id]}</strong><small>${evidenceAdvice(id)}</small></span><em class="${decision ? "done" : ""}">${status}</em></button><div class="wealth-decision-actions"><button type="button" data-start-decision="adopt" data-factor-id="${id}">采纳</button><button type="button" data-start-decision="adjust" data-factor-id="${id}">调整</button><button type="button" data-start-decision="discard" data-factor-id="${id}">废弃</button></div></section>`;
    }).join("")}</div>
    ${wealthState.pendingDecision ? renderDecisionEditor() : ""}
    ${allDone && !hasActiveFactor ? `<div class="wealth-inline-error">至少保留一个采纳或调整后的因子，才能构建组合。</div>` : ""}
    <button class="wealth-primary wealth-sticky-action" type="button" data-route="research/composite" ${allDone && hasActiveFactor ? "" : "disabled"}>进入组合方案</button>`;
}

function renderDecisionEditor() {
  const pending = wealthState.pendingDecision;
  const label = { adopt: "采纳", adjust: "调整", discard: "废弃" }[pending.decision];
  return `<form id="wealth-decision-form" class="wealth-inline-editor"><div><h2>${label}${FACTOR_LABELS[pending.factorId]}</h2><button type="button" data-cancel-decision aria-label="关闭">取消</button></div>${pending.decision === "adjust" ? `<label>观察窗口<select id="wealth-revision-window"><option value="9">改为 9 个月</option><option value="12">改为 12 个月</option></select></label>` : ""}<label>说明<textarea id="wealth-decision-reason" rows="3" required placeholder="记录判断依据"></textarea></label><button class="wealth-primary" type="submit">确认${label}</button></form>`;
}

function renderComposite() {
  const weights = wealthState.factorWeights;
  const total = Object.values(weights).reduce((sum, value) => sum + Number(value), 0);
  return `${stageHeader("composite", "减少重复暴露。")}
    <section class="wealth-section wealth-compact-section"><div class="wealth-section-head"><h2>正交化</h2><span>已开启</span></div><p class="wealth-short-copy">先剔除因子间的共同变化，再计算综合分数。</p><div class="wealth-compare-strip"><span>动量</span><i></i><span>低波残差</span><i></i><span>价值残差</span></div><button type="button" class="wealth-text-button" data-route="detail/factor/composite_v1">查看方法和结果</button></section>
    <form id="wealth-composite-form" class="wealth-form-page">
      <section class="wealth-form-section"><div class="wealth-section-head"><h2>因子权重</h2><strong id="wealth-weight-total" class="${total === 100 ? "valid" : "invalid"}">${total}%</strong></div>
        <label>动量<input id="wealth-weight-momentum" type="number" min="0" max="100" step="5" value="${weights.momentum_6m}" /><span>%</span></label>
        <label>低波<input id="wealth-weight-lowvol" type="number" min="0" max="100" step="5" value="${weights.low_vol_orthogonal}" /><span>%</span></label>
        <label>价值<input id="wealth-weight-value" type="number" min="0" max="100" step="5" value="${weights.value_orthogonal}" /><span>%</span></label>
        <p class="wealth-field-note">三项合计需为 100%。</p>
      </section>
      <div id="wealth-composite-error" class="wealth-inline-error" hidden></div>
      <button class="wealth-primary wealth-sticky-action" type="submit">保存组合</button>
    </form>`;
}

function approvedFactorRows() {
  return BASE_FACTORS.map((id) => {
    const decision = wealthState.factorDecisions[id];
    if (!decision || decision.decision === "discard") return "";
    return `<div><span>${FACTOR_LABELS[id]}</span><strong>${decision.version || "v1.0"}</strong></div>`;
  }).join("") || "<p>暂无已采纳因子</p>";
}

function renderStrategy() {
  return `${stageHeader("strategy", "确认持仓和风险规则。")}
    <form id="wealth-strategy-form" class="wealth-form-page">
      <section class="wealth-form-section"><h2>策略类型</h2><label class="wealth-option-card"><input type="radio" name="wealth-strategy" value="composite" ${wealthState.strategyId === "composite" ? "checked" : ""} /><span><strong>多因子策略</strong><small>按综合分数选择标的</small></span></label><label class="wealth-option-card"><input type="radio" name="wealth-strategy" value="momentum_timing" ${wealthState.strategyId === "momentum_timing" ? "checked" : ""} /><span><strong>动量择时</strong><small>趋势转弱时降低仓位</small></span></label></section>
      <section class="wealth-form-section"><div class="wealth-section-head"><h2>使用因子</h2><span>绑定版本</span></div><div class="wealth-bound-factors">${approvedFactorRows()}</div></section>
      <section class="wealth-form-section"><h2>持仓规则</h2><label>持仓数量<select id="wealth-top-n"><option value="2" ${wealthState.topN === 2 ? "selected" : ""}>前 2 个</option><option value="3" ${wealthState.topN === 3 ? "selected" : ""}>前 3 个</option><option value="4" ${wealthState.topN === 4 ? "selected" : ""}>前 4 个</option></select></label><label>趋势转弱时仓位<select id="wealth-defensive"><option value="0" ${wealthState.defensiveExposure === 0 ? "selected" : ""}>0%</option><option value="25" ${wealthState.defensiveExposure === 25 ? "selected" : ""}>25%</option><option value="50" ${wealthState.defensiveExposure === 50 ? "selected" : ""}>50%</option><option value="75" ${wealthState.defensiveExposure === 75 ? "selected" : ""}>75%</option></select></label><div class="wealth-setting-row"><span><strong>只做多 · 月度调仓</strong><small>总仓位不超过 100%</small></span><b>固定</b></div></section>
      <details class="wealth-precheck"><summary>回测前检查</summary><ul><li>配置已保存</li><li>因子已完成审批</li><li>信号滞后 1 期</li><li>交易成本已计入</li><li>留出集不参与调参</li></ul></details>
      <button class="wealth-primary wealth-sticky-action" type="submit">确认并回测</button>
    </form>`;
}

function selectedResult() {
  return wealthState.payload.strategies?.[wealthState.strategyId] || wealthState.payload.strategies?.composite || wealthState.payload.strategies?.momentum_timing;
}

function renderBacktest() {
  const result = selectedResult();
  const checks = wealthState.payload.research_workflow?.backtest_quality?.checks || [];
  const archiveId = wealthState.archive?.run_id || wealthState.payload.versioning?.run_id;
  if (!result) return `${stageHeader("backtest", "运行后查看结果。")}${renderEmpty("还没有回测结果", "返回策略规则后运行回测。")}`;
  return `${stageHeader("backtest", "收益和风险一起看。")}
    <section class="wealth-report-head"><div><span>候选策略</span><h2>${wealthEscape(result.label)}</h2></div><strong>${wealthEscape(archiveId || "未归档")}</strong></section>
    <section class="wealth-key-metrics wealth-report-metrics"><div><span>年化收益</span><strong>${wealthPercent(result.metrics?.ann)}</strong></div><div><span>夏普</span><strong>${wealthNumber(result.metrics?.sharpe, 2)}</strong></div><div><span>最大回撤</span><strong>${wealthPercent(result.metrics?.max_dd)}</strong></div></section>
    <section class="wealth-section wealth-compact-section"><div class="wealth-section-head"><h2>净值走势</h2><span>策略 / 等权基准</span></div><canvas id="wealth-nav-chart" height="190" aria-label="策略和等权基准净值曲线"></canvas><div class="wealth-chart-legend"><span><i></i>策略</span><span><i></i>等权基准</span></div></section>
    <section class="wealth-section wealth-compact-section"><div class="wealth-section-head"><h2>回测指标</h2><button type="button" data-toggle-report>展开</button></div><div id="wealth-more-metrics" class="wealth-more-metrics" hidden><div><span>累计收益</span><strong>${wealthPercent(result.metrics?.cum)}</strong></div><div><span>索提诺</span><strong>${wealthNumber(result.metrics?.sortino, 2)}</strong></div><div><span>卡玛</span><strong>${wealthNumber(result.metrics?.calmar, 2)}</strong></div><div><span>平均换手</span><strong>${wealthPercent(result.evidence?.turnover_mean)}</strong></div><div><span>总成本</span><strong>${wealthPercent(result.evidence?.cost_total, 2)}</strong></div><div><span>信号滞后</span><strong>${result.evidence?.signal_lag} 期</strong></div></div></section>
    <section class="wealth-section wealth-compact-section"><div class="wealth-section-head"><h2>规则检查</h2><span>${checks.every((item) => item.status === "passed") ? "全部通过" : "需要处理"}</span></div><div class="wealth-checks">${checks.map((item) => `<div><i class="${item.status === "passed" ? "pass" : "fail"}"></i><span><strong>${wealthEscape(item.name)}</strong><small>${wealthEscape(item.evidence)}</small></span></div>`).join("")}</div></section>
    <aside class="wealth-review-note"><strong>结果提示</strong><p>${result.metrics?.max_dd < -0.2 ? "回撤超过 20%，建议比较更低仓位或更少换手的版本。" : "回撤处于当前演示阈值内，仍需检查样本外表现。"}</p></aside>
    <section class="wealth-strategy-decision"><h2>是否保留这版策略？</h2><label>说明<textarea id="wealth-strategy-reason" rows="3" placeholder="记录判断依据"></textarea></label><div><button type="button" data-strategy-decision="adopt">采纳</button><button type="button" data-strategy-decision="adjust">调整</button><button type="button" data-strategy-decision="discard">废弃</button></div></section>`;
}

function renderVersions() {
  const rows = [
    ["样本切分", "2019–2022 / 2023–2024 / 2025", `${wealthState.config.train_end} / ${wealthState.config.validation_end} / 留出`],
    ["因子权重", "50 / 30 / 20", `${wealthState.factorWeights.momentum_6m} / ${wealthState.factorWeights.low_vol_orthogonal} / ${wealthState.factorWeights.value_orthogonal}`],
    ["持仓数量", "前 3 个", `前 ${wealthState.topN} 个`],
    ["防守仓位", "50%", `${wealthState.defensiveExposure}%`],
  ];
  return `${stageHeader("versions", "保留每次修改和决定。")}
    <section class="wealth-section wealth-compact-section"><div class="wealth-section-head"><h2>当前版本</h2><span>${wealthState.strategyDecision ? "已决定" : "待决定"}</span></div><div class="wealth-version-card"><strong>${wealthState.payload.versioning?.version_id || "demo-research-v0.2.0"}</strong><p>运行号 ${wealthEscape(wealthState.archive?.run_id || "尚未生成")}</p></div></section>
    <section class="wealth-section wealth-compact-section"><h2>本版改动</h2><div class="wealth-diff-list">${rows.map(([field, before, after]) => `<div><span>${field}</span><small>${before}</small><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg><strong>${after}</strong></div>`).join("")}</div></section>
    <section class="wealth-section wealth-compact-section"><h2>决策记录</h2>${renderLocalRecords(6)}</section>
    <button class="wealth-secondary wealth-wide-button" type="button" data-root-jump="records">查看全部记录</button>`;
}

function renderLibrary() {
  const factorIds = BASE_FACTORS.filter((id) => {
    const decision = wealthState.factorDecisions[id]?.decision;
    if (wealthState.factorFilter === "adopt") return decision === "adopt" || decision === "adjust";
    if (wealthState.factorFilter === "discard") return decision === "discard";
    return true;
  });
  const items = factorIds.map((id) => {
    const decision = wealthState.factorDecisions[id];
    const status = decision ? ({ adopt: "已采纳", adjust: "已调整", discard: "已废弃" }[decision.decision]) : "待审批";
    const evidence = factorSummary(id);
    return `<button type="button" data-route="detail/factor/${id}" class="wealth-library-row"><span><strong>${FACTOR_LABELS[id]}</strong><small>${status} · ${decision?.version || "v1.0"}</small></span><div><b>${wealthNumber(evidence.full.mean, 3)}</b><small>Rank IC</small></div><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg></button>`;
  }).join("");
  const filters = [["all", "全部"], ["adopt", "已采纳"], ["discard", "已废弃"]];
  return `<section class="wealth-root-page"><div class="wealth-root-heading"><h1>因子库</h1><p>公式、证据和决策放在一起。</p></div><div class="wealth-filter-tabs">${filters.map(([id, label]) => `<button class="${wealthState.factorFilter === id ? "active" : ""}" type="button" data-factor-filter="${id}">${label}</button>`).join("")}</div><div class="wealth-library-list">${items || renderEmpty("暂无因子", "当前筛选条件下没有记录。")}</div></section>`;
}

function renderStrategies() {
  const ids = ["composite", "momentum_timing"];
  return `<section class="wealth-root-page"><div class="wealth-root-heading"><h1>策略</h1><p>查看逻辑和回测结果。</p></div><div class="wealth-strategy-list">${ids.map((id) => {
    const item = wealthState.payload.strategies?.[id];
    if (!item) return "";
    return `<button type="button" data-select-strategy="${id}"><div><span>合成数据</span><strong>${wealthEscape(item.label)}</strong><p>${wealthEscape(item.summary)}</p></div><section><span><small>年化</small><b>${wealthPercent(item.metrics?.ann)}</b></span><span><small>夏普</small><b>${wealthNumber(item.metrics?.sharpe, 2)}</b></span><span><small>回撤</small><b>${wealthPercent(item.metrics?.max_dd)}</b></span></section></button>`;
  }).join("")}</div></section>`;
}

function renderLocalRecords(limit = 20) {
  const rows = [...wealthState.records].reverse().slice(0, limit);
  if (!rows.length) return renderEmpty("暂无决策记录", "完成因子或策略审批后会显示在这里。");
  return `<div class="wealth-record-list">${rows.map((item) => `<div><i class="${item.synced ? "synced" : "local"}"></i><span><strong>${wealthEscape(item.title)}</strong><small>${wealthEscape(item.reason || "未填写说明")}</small></span><em>${item.synced ? "已归档" : "未归档"}</em></div>`).join("")}</div>`;
}

function renderRecords() {
  const runs = wealthState.history.runs || [];
  return `<section class="wealth-root-page"><div class="wealth-root-heading"><h1>研究记录</h1><p>运行、修改和决策均可复核。</p></div><section class="wealth-section wealth-compact-section"><div class="wealth-section-head"><h2>最近运行</h2><span>${runs.length} 条</span></div>${runs.length ? `<div class="wealth-run-list">${runs.slice(0, 8).map((item) => `<button type="button" data-load-run="${wealthEscape(item.run_id)}"><span><strong>${wealthEscape(item.run_id)}</strong><small>${wealthEscape(item.created_at || "")}</small></span><em>${item.stage_count} 阶段</em></button>`).join("")}</div>` : renderEmpty("暂无服务端记录", "启动本地服务并完成回测后会显示在这里。")}</section><section class="wealth-section wealth-compact-section"><h2>决策记录</h2>${renderLocalRecords()}</section></section>`;
}

function renderEmpty(title, message) {
  return `<div class="wealth-empty"><strong>${title}</strong><p>${message}</p></div>`;
}

function wealthAiSummary(route) {
  if (route.type === "stage" && route.id === "factor") {
    const { factor, full } = factorSummary(wealthState.factor);
    return { event: `${FACTOR_LABELS[wealthState.factor]}已有可检查结果。`, evidence: `Rank IC ${wealthNumber(full.mean, 3)}，ICIR ${wealthNumber(full.icir, 2)}，G1-G5 ${wealthPercent(factor?.tables?.g1_g5_long_short, 2)}。`, risk: evidenceAdvice(wealthState.factor), next: "查看完整口径后，再进入因子选择。" };
  }
  if (route.type === "stage" && route.id === "backtest") {
    const result = selectedResult();
    return { event: `${result?.label || "策略"}已完成回测。`, evidence: `年化收益 ${wealthPercent(result?.metrics?.ann)}，夏普 ${wealthNumber(result?.metrics?.sharpe)}，最大回撤 ${wealthPercent(result?.metrics?.max_dd)}。`, risk: "结果来自合成数据，只用于验证研究流程。", next: "先查看独立验证，再记录采纳、改进或废弃原因。" };
  }
  const current = route.type === "stage" ? STAGES.find((item) => item.id === route.id)?.title : "当前研究";
  return { event: `${current || "当前研究"}已载入。`, evidence: `研究进度 ${completedStageCount()}/7，信号滞后 1 期，交易成本已配置。`, risk: "AI建议不会自动修改因子、权重或策略状态。", next: route.type === "root" ? "先整理研究想法，确认后再保存研究范围。" : "完成当前页面的主要操作后继续下一阶段。" };
}

function updateWealthAiContent(route) {
  const summary = wealthAiSummary(route);
  const validation = wealthState.payload.independent_validation;
  const validationText = validation ? `${validation.level === "red" ? "阻断" : validation.level === "yellow" ? "有风险" : "通过"}：${validation.summary}` : "等待本次运行后检查";
  wealthById("wealth-ai-content").innerHTML = `<section><h3>发生了什么</h3><p>${wealthEscape(summary.event)}</p></section><section><h3>证据</h3><p>${wealthEscape(summary.evidence)}</p></section><section><h3>风险</h3><p>${wealthEscape(summary.risk)}</p></section><section><h3>下一步建议</h3><p>${wealthEscape(summary.next)}</p></section><section class="wealth-validation-summary"><h3>独立验证</h3><p>${wealthEscape(validationText)}</p></section>`;
  wealthById("wealth-ai-count").textContent = validation?.level === "red" ? "!" : "2";
}

function renderRoute() {
  const route = parseRoute();
  if (route.type === "stage" && !canEnterStage(route.id)) {
    showToast("请先完成上一步", "warning");
    go("home");
    return;
  }
  updateChrome(route);
  const renderers = {
    home: renderHome,
    library: renderLibrary,
    strategies: renderStrategies,
    records: renderRecords,
    config: renderConfig,
    factor: renderFactor,
    approval: renderApproval,
    composite: renderComposite,
    strategy: renderStrategy,
    backtest: renderBacktest,
    versions: renderVersions,
  };
  let html;
  if (route.type === "factor-detail") html = renderFactorDetail(route.id);
  else html = renderers[route.id]();
  wealthById("wealth-app").innerHTML = html;
  updateWealthAiContent(route);
  bindPageEvents(route);
  if (route.type === "stage" && route.id === "backtest") window.setTimeout(drawWealthChart, 0);
  window.scrollTo({ top: 0, behavior: "instant" });
}

function validateConfig(next) {
  const start = new Date(next.start);
  const trainEnd = new Date(next.train_end);
  const validationEnd = new Date(next.validation_end);
  const end = new Date(next.end);
  if ([start, trainEnd, validationEnd, end].some((date) => Number.isNaN(date.getTime()))) return "请填写完整日期";
  if (!(start < trainEnd && trainEnd < validationEnd && validationEnd < end)) return "日期应按训练期、验证期、留出集依次排列";
  return "";
}

async function runResearch(strategyIds) {
  wealthState.loading = true;
  renderRoute();
  const request = {
    ...wealthState.config,
    strategy_ids: strategyIds,
    factor_weights: {
      momentum_6m: wealthState.factorWeights.momentum_6m / 100,
      low_vol_orthogonal: wealthState.factorWeights.low_vol_orthogonal / 100,
      value_orthogonal: wealthState.factorWeights.value_orthogonal / 100,
    },
    top_n: wealthState.topN,
    defensive_exposure: wealthState.defensiveExposure / 100,
    factor_decisions: wealthState.factorDecisions,
    composite_approved: wealthState.compositeApproved,
    strategy_decision: wealthState.strategyDecision,
    assistant_plan: wealthState.plan,
    source_surface: "wealth",
  };
  try {
    const response = await fetch("/api/research/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "运行失败");
    wealthState.payload = result.payload;
    wealthState.archive = result.archive;
    wealthState.history = await wealthLoadHistory();
    saveState();
    showToast(`已归档：${result.archive.run_id}`, "success");
    return result;
  } catch (error) {
    showToast(`${error.message}。请通过本地服务打开页面。`, "error");
    throw error;
  } finally {
    wealthState.loading = false;
    renderRoute();
  }
}

async function persistDecision(record, title) {
  const localRecord = { ...record, title, created_at: new Date().toISOString(), synced: false };
  try {
    const response = await fetch("/api/research/decision", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...record, run_id: wealthState.archive?.run_id, source_surface: "wealth" }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "归档失败");
    localRecord.synced = true;
    localRecord.decision_id = result.decision_id;
  } catch (error) {
    showToast("决策已暂存，尚未写入运行档案", "warning");
  }
  wealthState.records.push(localRecord);
  saveState();
  return localRecord;
}

function bindPageEvents(route) {
  document.querySelectorAll("[data-route]").forEach((button) => button.addEventListener("click", () => go(button.dataset.route)));
  document.querySelectorAll("[data-stage-route]").forEach((button) => button.addEventListener("click", () => {
    if (button.disabled) return;
    go(`research/${button.dataset.stageRoute}`);
  }));
  document.querySelectorAll("[data-wealth-mode]").forEach((button) => button.addEventListener("click", () => {
    wealthState.researchMode = button.dataset.wealthMode;
    saveState();
    showToast(`已切换为${wealthState.researchMode === "autonomous" ? "AI自主研究" : "专业研究"}模式，历史记录保留`, "success");
    renderRoute();
  }));
  const fill = document.querySelector("[data-fill-idea]");
  if (fill) fill.addEventListener("click", () => { wealthById("wealth-idea").value = fill.dataset.fillIdea; wealthById("wealth-idea").focus(); });
  const ideaForm = wealthById("wealth-idea-form");
  if (ideaForm) ideaForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const raw = wealthById("wealth-idea").value.trim();
    if (!raw) { showToast("请先输入研究想法", "warning"); return; }
    wealthState.plan = window.LocalResearchAssistant.parse(raw);
    saveState();
    renderRoute();
  });
  const acceptPlan = document.querySelector("[data-accept-plan]");
  if (acceptPlan) acceptPlan.addEventListener("click", () => {
    if (completedStageCount() > 0) resetResearchProgress();
    saveState();
    go("research/config");
  });

  const configForm = wealthById("wealth-config-form");
  if (configForm) configForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const trainEnd = wealthById("wealth-train-end")?.value || wealthState.config.train_end;
    const validationEnd = wealthById("wealth-validation-end")?.value || wealthState.config.validation_end;
    const validationStart = `${Number(trainEnd.slice(0, 4)) + (trainEnd.slice(5, 7) === "12" ? 1 : 0)}-${trainEnd.slice(5, 7) === "12" ? "01" : String(Number(trainEnd.slice(5, 7)) + 1).padStart(2, "0")}-01`;
    const next = { ...wealthState.config, asset_type: wealthById("wealth-asset").value, universe_id: wealthById("wealth-universe").value, benchmark: wealthById("wealth-benchmark").value, start: wealthById("wealth-start").value, end: wealthById("wealth-end").value, train_end: trainEnd, validation_start: validationStart, validation_end: validationEnd };
    const error = validateConfig(next);
    if (error) { const target = wealthById("wealth-config-error"); target.textContent = error; target.hidden = false; return; }
    wealthState.config = next;
    wealthState.configLocked = true;
    saveState();
    showToast("研究范围已保存", "success");
    go("research/factor");
  });

  document.querySelectorAll("[data-factor]").forEach((button) => button.addEventListener("click", () => { wealthState.factor = button.dataset.factor; saveState(); renderRoute(); }));
  document.querySelectorAll("[data-factor-filter]").forEach((button) => button.addEventListener("click", () => { wealthState.factorFilter = button.dataset.factorFilter; saveState(); renderRoute(); }));
  const runFactors = document.querySelector("[data-run-factors]");
  if (runFactors) runFactors.addEventListener("click", async () => {
    try { await runResearch(["momentum", "low_vol", "value", "equal_weight"]); wealthState.factorRun = true; saveState(); go("research/approval"); } catch (error) { /* message already shown */ }
  });

  document.querySelectorAll("[data-start-decision]").forEach((button) => button.addEventListener("click", () => { wealthState.pendingDecision = { factorId: button.dataset.factorId, decision: button.dataset.startDecision }; renderRoute(); }));
  const cancelDecision = document.querySelector("[data-cancel-decision]");
  if (cancelDecision) cancelDecision.addEventListener("click", () => { wealthState.pendingDecision = null; renderRoute(); });
  const decisionForm = wealthById("wealth-decision-form");
  if (decisionForm) decisionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const pending = wealthState.pendingDecision;
    const reason = wealthById("wealth-decision-reason").value.trim();
    if (!reason) { showToast("请填写判断依据", "warning"); return; }
    const currentVersion = wealthState.factorDecisions[pending.factorId]?.version || "v1.0";
    const version = pending.decision === "adjust" ? `v1.${Number(currentVersion.split(".")[1] || 0) + 1}` : currentVersion;
    wealthState.factorDecisions[pending.factorId] = { decision: pending.decision, reason, version, parameter_change: pending.decision === "adjust" ? { lookback_months: Number(wealthById("wealth-revision-window").value) } : null };
    await persistDecision({ stage: "factor_pool", object_id: pending.factorId, decision: pending.decision, reason, version, evidence_version: wealthState.payload.versioning?.version_id }, `${FACTOR_LABELS[pending.factorId]}：${{ adopt: "采纳", adjust: "调整", discard: "废弃" }[pending.decision]}`);
    wealthState.pendingDecision = null;
    saveState();
    renderRoute();
  });

  const compositeForm = wealthById("wealth-composite-form");
  if (compositeForm) {
    const weightInputs = ["wealth-weight-momentum", "wealth-weight-lowvol", "wealth-weight-value"].map(wealthById);
    const updateTotal = () => { const total = weightInputs.reduce((sum, input) => sum + Number(input.value || 0), 0); const target = wealthById("wealth-weight-total"); target.textContent = `${total}%`; target.className = total === 100 ? "valid" : "invalid"; };
    weightInputs.forEach((input) => input.addEventListener("input", updateTotal));
    compositeForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const weights = { momentum_6m: Number(weightInputs[0].value), low_vol_orthogonal: Number(weightInputs[1].value), value_orthogonal: Number(weightInputs[2].value) };
      const total = Object.values(weights).reduce((sum, value) => sum + value, 0);
      if (total !== 100) { const target = wealthById("wealth-composite-error"); target.textContent = "三项权重合计需为 100%"; target.hidden = false; return; }
      wealthState.factorWeights = weights;
      wealthState.compositeApproved = true;
      await persistDecision({ stage: "factor_improvement", object_id: "composite_v1", decision: "adopt", reason: `正交化后按 ${weights.momentum_6m}/${weights.low_vol_orthogonal}/${weights.value_orthogonal} 合成`, version: "v1.0" }, "综合因子：采纳");
      saveState();
      showToast("组合方案已保存", "success");
      go("research/strategy");
    });
  }

  const strategyForm = wealthById("wealth-strategy-form");
  if (strategyForm) strategyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    wealthState.strategyId = new FormData(strategyForm).get("wealth-strategy");
    wealthState.topN = Number(wealthById("wealth-top-n").value);
    wealthState.defensiveExposure = Number(wealthById("wealth-defensive").value);
    try {
      await runResearch(["composite", "momentum_timing", "equal_weight"]);
      wealthState.strategyReady = true;
      wealthState.backtestCompleted = true;
      saveState();
      go("research/backtest");
    } catch (error) { /* message already shown */ }
  });

  const reportToggle = document.querySelector("[data-toggle-report]");
  if (reportToggle) reportToggle.addEventListener("click", () => { const target = wealthById("wealth-more-metrics"); target.hidden = !target.hidden; reportToggle.textContent = target.hidden ? "展开" : "收起"; });
  document.querySelectorAll("[data-strategy-decision]").forEach((button) => button.addEventListener("click", async () => {
    const reason = wealthById("wealth-strategy-reason").value.trim();
    if (!reason) { showToast("请填写判断依据", "warning"); return; }
    const decision = button.dataset.strategyDecision;
    wealthState.strategyDecision = { decision, reason, version: decision === "adjust" ? "v1.1" : "v1.0" };
    await persistDecision({ stage: "strategy_review", object_id: wealthState.strategyId, decision, reason, version: wealthState.strategyDecision.version }, `${selectedResult()?.label || "策略"}：${{ adopt: "采纳", adjust: "调整", discard: "废弃" }[decision]}`);
    saveState();
    showToast("策略决定已记录", "success");
    go("research/versions");
  }));
  const rootJump = document.querySelector("[data-root-jump]");
  if (rootJump) rootJump.addEventListener("click", () => go(rootJump.dataset.rootJump));
  document.querySelectorAll("[data-select-strategy]").forEach((button) => button.addEventListener("click", () => { wealthState.strategyId = button.dataset.selectStrategy; saveState(); if (wealthState.archive) go("research/backtest"); else go("research/strategy"); }));
  document.querySelectorAll("[data-load-run]").forEach((button) => button.addEventListener("click", async () => {
    try {
      const response = await fetch(`/api/research/run/${encodeURIComponent(button.dataset.loadRun)}`, { cache: "no-store" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "读取失败");
      hydrateArchivedRun(result.payload, button.dataset.loadRun);
      saveState();
      go("research/backtest");
    } catch (error) { showToast(error.message, "error"); }
  }));
}

function drawWealthChart() {
  const canvas = wealthById("wealth-nav-chart");
  const strategy = selectedResult();
  const benchmark = wealthState.payload.strategies?.equal_weight;
  if (!canvas || !strategy?.nav?.length) return;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(320, rect.width);
  const height = 190;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  const series = [strategy.nav, benchmark?.nav || []].filter((item) => item.length);
  const values = series.flatMap((item) => item.map((point) => Number(point.value)));
  const min = Math.min(...values) * 0.98;
  const max = Math.max(...values) * 1.02;
  const x = (index, length) => 8 + index / Math.max(1, length - 1) * (width - 16);
  const y = (value) => height - 10 - (value - min) / Math.max(1e-9, max - min) * (height - 20);
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = "#e7ebf0";
  ctx.lineWidth = 1;
  [0.25, 0.5, 0.75].forEach((step) => { ctx.beginPath(); ctx.moveTo(0, height * step); ctx.lineTo(width, height * step); ctx.stroke(); });
  series.forEach((points, index) => {
    ctx.beginPath();
    points.forEach((point, pointIndex) => pointIndex ? ctx.lineTo(x(pointIndex, points.length), y(Number(point.value))) : ctx.moveTo(x(pointIndex, points.length), y(Number(point.value))));
    ctx.strokeStyle = index === 0 ? "#1769e0" : "#98a3af";
    ctx.lineWidth = index === 0 ? 2.4 : 1.5;
    ctx.setLineDash(index === 0 ? [] : [5, 5]);
    ctx.stroke();
  });
  ctx.setLineDash([]);
}

function setupWealthOverlays() {
  const guide = wealthById("wealth-guide");
  const drawer = wealthById("wealth-ai-drawer");
  const spotlight = wealthById("wealth-guide-spotlight");
  const tour = [
    [".wealth-app-header", "先确定研究范围", "先选择资产类型、标的范围、历史区间和交易成本，后续结果都会基于这组设置。"],
    ["[data-root-route=\"home\"]", "研究：从想法到方案", "在研究页输入自然语言想法，确认因子、样本切分、执行滞后和回测规则。"],
    ["[data-root-route=\"library\"]", "因子库：看清信号依据", "这里集中查看因子定义和历史评估。因子只有在你确认后，才会进入后续组合方案。"],
    ["[data-root-route=\"strategies\"]", "策略：组合、风控和回测", "选择多因子或动量择时策略，配置正交化、权重、持仓数量和防御仓位，再运行回测。"],
    ["[data-root-route=\"records\"]", "记录：查看每次尝试", "采纳、调整、废弃和回测运行都会保留版本、原因和结果，便于之后重新打开。"],
    ["#wealth-ai-button", "研究解读：AI 给建议", "AI 解释当前阶段发生了什么、证据是什么、有哪些风险和下一步建议；最终决定仍由用户完成。"],
  ];
  let tourIndex = 0;
  const clearSpotlight = () => { document.querySelectorAll(".guide-tour-target").forEach((node) => node.classList.remove("guide-tour-target")); spotlight.hidden = true; };
  const renderTour = () => {
    const [selector, title, copy] = tour[tourIndex];
    wealthById("wealth-guide-progress").textContent = `第 ${tourIndex + 1} / ${tour.length} 步`;
    wealthById("wealth-guide-title").textContent = title;
    wealthById("wealth-guide-copy").textContent = copy;
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
  const setOpen = (target, open) => { target.hidden = !open; document.body.classList.toggle("guide-open", open); };
  const openGuide = () => { setOpen(guide, true); tourIndex = 0; renderTour(); };
  const closeGuide = () => { setOpen(guide, false); clearSpotlight(); };
  wealthById("wealth-guide-button").addEventListener("click", openGuide);
  guide.querySelectorAll("[data-guide-close]").forEach((button) => button.addEventListener("click", closeGuide));
  guide.querySelector("[data-guide-prev]").addEventListener("click", () => { if (tourIndex > 0) { tourIndex -= 1; renderTour(); } });
  guide.querySelector("[data-guide-next]").addEventListener("click", () => { if (tourIndex === tour.length - 1) closeGuide(); else { tourIndex += 1; renderTour(); } });
  wealthById("wealth-ai-button").addEventListener("click", () => setOpen(drawer, true));
  drawer.querySelectorAll("[data-close-ai]").forEach((button) => button.addEventListener("click", () => setOpen(drawer, false)));
  drawer.querySelector("[data-ai-apply]").addEventListener("click", () => { setOpen(drawer, false); showToast("建议已记录，未自动修改研究参数", "success"); });
  [guide, drawer].forEach((target) => target.addEventListener("click", (event) => { if (event.target === target) target === guide ? closeGuide() : setOpen(drawer, false); }));
  document.addEventListener("keydown", (event) => { if (event.key !== "Escape") return; if (!drawer.hidden) setOpen(drawer, false); else if (!guide.hidden) closeGuide(); });
  openGuide();
}

async function wealthBoot() {
  wealthState.payload = await wealthLoadPayload();
  wealthState.config = defaultConfig(wealthState.payload);
  restoreState();
  if (!wealthState.config) wealthState.config = defaultConfig(wealthState.payload);
  try { await restoreActiveRun(); } catch (error) { wealthState.backtestCompleted = false; wealthState.archive = null; showToast(error.message, "warning"); }
  wealthState.history = await wealthLoadHistory();
  setupWealthOverlays();
  wealthById("wealth-back").addEventListener("click", () => history.back());
  wealthById("wealth-home").addEventListener("click", () => go("home"));
  document.querySelectorAll("[data-root-route]").forEach((button) => button.addEventListener("click", () => go(button.dataset.rootRoute)));
  window.addEventListener("hashchange", renderRoute);
  if (!location.hash) location.hash = "#home";
  renderRoute();
}

document.addEventListener("DOMContentLoaded", () => wealthBoot().catch((error) => {
  wealthById("wealth-app").innerHTML = renderEmpty("页面加载失败", error.message);
}));

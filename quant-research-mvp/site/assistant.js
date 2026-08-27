(() => {
  const factorRules = [
    { id: "momentum_6m", words: ["动量", "趋势", "相对强势"], label: "六个月动量", formula: "过去六个月累计收益" },
    { id: "low_vol_6m", words: ["低波", "低波动", "波动率"], label: "六个月低波", formula: "过去六个月收益波动率" },
    { id: "pb", words: ["价值", "市净率", "pb", "估值"], label: "价值 / 市净率", formula: "观察日市净率" },
  ];
  const verifiedSources = [
    { title: "Jegadeesh & Titman：横截面动量", type: "同行评审论文", year: "1993", url: "https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1993.tb04702.x" },
    { title: "Moskowitz 等：时间序列动量", type: "同行评审论文", year: "2012", url: "https://www.sciencedirect.com/science/article/pii/S0304405X11002613" },
    { title: "Asness 等：价值与动量", type: "机构公开研究", year: "2013", url: "https://www.aqr.com/insights/research/journal-article/value-and-momentum-everywhere" },
  ];

  function matchNumber(text, pattern, fallback) {
    const match = text.match(pattern);
    if (!match) return fallback;
    const raw = match[1];
    if (/^\d+$/.test(raw)) return Number(raw);
    const chinese = { 一: 1, 两: 2, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10, 十二: 12 };
    return chinese[raw] || fallback;
  }

  function parse(text) {
    const raw = String(text || "").trim();
    const normalized = raw.toLowerCase();
    const factors = factorRules.filter((rule) => rule.words.some((word) => normalized.includes(word))).map((rule) => rule.id);
    const timing = /择时|趋势转弱|市场状态|降到一半|半仓/.test(raw);
    const composite = factors.length >= 2 || /多因子|综合因子|合成|正交化/.test(raw);
    const assetType = /基金|ETF/.test(raw) ? "基金" : /债券|固收/.test(raw) ? "债券" : /股票|个股/.test(raw) ? "股票" : "指数";
    const frequency = /周频|每周/.test(raw) ? "周度" : /日频|每天|每日/.test(raw) ? "日度" : "月度";
    const lookback = matchNumber(raw, /(\d+|十二|十|九|八|七|六|五|四|三|二|两|一)\s*(?:个?月|月)/, 6);
    const topN = matchNumber(raw, /(?:前|top\s*)(\d+|十|九|八|七|六|五|四|三|二|两|一)/i, 3);
    const holding = matchNumber(raw, /持有(?:前|top\s*)?(\d+|十|九|八|七|六|五|四|三|二|两|一)/i, topN);
    const kind = timing || composite ? "strategy" : "factor";
    const selected = composite ? "composite_v1" : timing ? "momentum_timing" : factors[0] || "momentum_6m";
    const selectedFactors = composite ? (factors.length ? factors : ["momentum_6m", "low_vol_6m", "pb"]) : [selected];
    const missing = [];
    if (!raw) missing.push("请先输入研究想法");
    if (!factors.length && !timing) missing.push("还没有识别到因子或择时信号");
    if (/股票|个股|基金|债券/.test(raw)) missing.push("当前演示数据是指数池；其他资产类型保留为数据接入口");
    const proposal = timing
      ? `以${lookback}个月趋势判断市场状态，${frequency}调仓，选择相对强势的前${holding}个标的；趋势转弱时将总仓位降至 50%。`
      : composite
        ? `在${assetType}池中测试${selectedFactors.map((id) => factorRules.find((rule) => rule.id === id)?.label || id).join("、")}，先做横截面正交化，再按明确权重形成综合分数，${frequency}调仓。`
        : `在${assetType}池中测试${factorRules.find((rule) => rule.id === selected)?.label || "动量信号"}，观察窗口 ${lookback} 个月，${frequency}调仓，重点查看 IC、分组收益和换手。`;
    return {
      raw,
      kind,
      selected,
      title: timing ? "动量择时方案" : composite ? "多因子研究方案" : `${factorRules.find((rule) => rule.id === selected)?.label || "单因子"}测试方案`,
      hypothesis: raw || "等待输入",
      proposal,
      recognized: [
        ["研究对象", assetType],
        ["研究信号", selectedFactors.map((id) => factorRules.find((rule) => rule.id === id)?.label || id).join("、")],
        ["调仓频率", frequency],
        ["观察窗口", `${lookback} 个月`],
        ["持仓数量", `前 ${holding} 个`],
      ],
      outputs: kind === "factor" ? ["因子公式和经济含义", "秩相关 IC、ICIR、G1-G5 分组收益", "敏感性和换手检查"] : ["因子组合与正交化说明", "目标权重和风险约束", "净值、夏普、索提诺和回撤"],
      checks: ["信号至少滞后 1 期", "训练集、验证集与留出集分开", "交易成本由统一成本模型计算", "研究员确认后才能进入下一阶段"],
      sources: verifiedSources,
      missing,
      nextStage: kind === "factor" ? "factor" : "strategy",
      nextAction: kind === "factor" ? "生成因子证据" : "查看策略逻辑",
    };
  }

  window.LocalResearchAssistant = { parse };
})();

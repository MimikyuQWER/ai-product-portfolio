# 地址审核 Agent — 变更记录 (Spec Delta)

> 每次重大功能/架构变更在此记录：日期、变更内容、原因。形成项目的可追溯开发历史。

---

## 2026-08-13 (第五次修订): 环节混淆根治 + 弹窗加宽 + 分块不卡 + 有效地址链接回显（按用户 CSV 实测反馈）

**变更**：
- `app.py` **消息渲染按显式 `type` 标记判定**（Issue #1）：消息体新增 `type: audit_report | preview`；渲染循环优先按 `type` 判定——`preview` 仅当普通气泡（不再误显「打开终审报告」按钮），`audit_report` 走右侧弹窗入口。移除此前脆弱的"表格+结论关键词"文本启发式（数据质量预审报告若含表格+「有效地址」字样会被误判为审核报告）。
- `app.py` 右侧弹窗 **加宽至 60vw**（Issue #2）：`div[data-testid="stDialog"]` 宽/最大宽 `46vw→60vw`、最小宽 `420px→480px`；弹窗内六列表格字号 `0.78rem→0.72rem`（略小但可读）。
- `agent/agent.py` **`confirm_and_audit` 重构为三段式**（Issue #3）：拆分为 `begin_batch_audit`（分块/注入补充信息）→ `audit_next_chunk`（单批 ReAct，返回是否还有下一批）→ `audit_finalize`（按文件顺序汇总）。`confirm_and_audit` 保留为阻塞包装（内部循环调用三段式），对 `tests` 等旧调用方兼容。
- `app.py` **分块逐批 `st.rerun` 进度驱动**：确认后进入"进度驱动"块，每批独立跑一次脚本运行（不再一次性阻塞冻结 UI），`st.status` 显示"第 X/N 批"，批次间 `rerun` 使进度可见；每批 `audit_next_chunk` **重建 messages 上下文**（仅 system+补充信息+本批），消除旧版"messages 逐批累积 → 后批越来越慢"。
- `agent/agent.py` **`chunk_ctx` 显式要求链接回显**（Issue #4）：批量指令第 4 条硬性要求「审核信息源」列必须含可点击链接——geocode 精确命中须给 marker_url（优先）/map_url，调了 web_search 且有结果须附 url，链接须来自工具实际字段、不得编造；依据列只写文字不放链接。`prompt.txt` Rule 6 已覆盖单条场景，本次把该约束明确下沉到批量分块指令。
- `tests/test_live_api.py`：新增 **T2f**（有效地址行确带回高德定位链接，断言该行的「审核信息源/依据」含 `uri.amap.com`）；新增 **T6**（12 条→3 批大文件多批次，验证全量不丢、含高德链接、且 finalize 后 LLM 上下文被重置为 1 条=不再无限膨胀）。

**验证**：真实 DeepSeek + 真实高德 + 真实联网搜索回归 **25/25 通过**（T6c 确认 `messages=1` 上下文已重置；T2f 确认有效行链接回显）；离线 mock 验证三段式管线 6 行不丢、链接全带回、finalize 后 messages=1。`py_compile` 全过。未推送远端 git。

**原因**：用户上传 CSV 实测反馈——①预审阶段主对话仍误显「打开终审报告」按钮（混淆环节）；②右侧弹窗太窄信息不全；③CSV 确认终审后一直"逐条核验中"卡住（根因：旧版单次阻塞调用 + messages 累积，且 T2 仅 2 条未覆盖大文件场景，故未被测试发现）；④有效地址行的「审核信息源」未返回地图/搜索链接（批量分块指令漏写链接要求）。

---

## 2026-08-13 (四次修订): 六列明细 + 计数对齐 + 环节分离（按用户 CSV 实测反馈）

**变更**：
- `agent/agent.py`：
  - **修复 `confirm_and_audit` 运行时崩溃**：此前循环调用了 `self._match_chunk(...)` 但该方法未定义（AttributeError）。新增 `_match_chunk`，按 chunk 的 idx/姓名/地址 把 `_extract_table_rows` 解析结果映射回 `result_by_idx`；兼容模型"按批从 1 重新编号"的兜底（还原为文件序号）。
  - `_extract_table_rows` 支持六/五/四列并始终返回 6 键 dict；`_build_merged_table` 输出六列（序号｜姓名｜地址｜审核结果｜审核依据｜审核信息源）；新增 `_esc` 转义（换行→空格、竖线→全角斜杠，防表格破坏）。
  - 批量合并改为**按文件原始 idx 对齐、不再去重**，未命中补"不确定"，从根上消除"同地址不同人 / 同结论"合法行被去重丢行导致的计数不符；保证计数=文件行数、行序=文件顺序、姓名齐全。
- `app.py`：
  - **环节分离（用户最新诉求）**：数据预审报告 = 主对话框气泡（标"📋 第 1 步 · 数据质量预审报告" + 询问是否终审）；最终审核报告 = 右侧弹窗（主对话框仅紧凑"✅ 审核完成"状态卡 + 明显"📑 打开终审报告（右侧弹窗）"按钮 + 概要计数）。侧边栏新增**步骤指示器**（第1步 数据预审 / 第2步 最终审核报告，按 `st.session_state.phase` 高亮当前环节）。
  - `_parse_audit_rows` 支持六列（含姓名）/五列/四列；`_build_detail_markdown` 六列；`_format_basis` 转义 `|` 兜底（对话框单条原始表格含竖线时不破坏明细表）；CSS 主对话表格与 dialog 表格均改为六列宽。
- `prompt.txt`：输出格式区分——对话框单条 = 五列（序号｜地址｜审核结果｜审核依据｜审核信息源）；文件/图片批量 = 六列（序号｜姓名｜地址｜…），并明确"序号=文件原始行号、姓名=原样回显"。
- `agent/guard.py` Rule D 兼容六列/五列（判定列索引自适应）。
- `tests/test_live_api.py`：新增 T0e 六列解析断言、T2c 六列表格断言。

**验证**：真实 DeepSeek + 真实高德 + 真实联网搜索回归 **21/21 通过**（T2c 已确认产出含「姓名」列六列表格，T2d 全量 2/2 不丢）。未推送远端 git。

**原因**：用户上传 CSV 实测发现①概要计数与文件对不上（根因：旧逻辑按 (地址,结论) 去重会丢合法行）②明细表缺姓名列、格式错乱、列宽不当、看不到完整地址；并要求把"数据预审报告"与"最终审核报告"在 UI 上彻底分离、让用户清晰感知当前处于哪个环节。

---

## 2026-08-13 (三次修订): 搜索超时根治 + 实时进度 + 明细扩展屏 + 五列表格（按用户实测反馈）

**变更**：
- **联网搜索超时根治**（`agent/tools.py`）：根因是 DuckDuckGo 在国内不可达且单次超时 10s、多轮叠加导致审核很慢。`web_search` 改为多级回退：Bing API（有 Key 时）→ **Bing 国内版网页搜索**（cn.bing.com，免费、国内直连、实测 ~0.5s）→ **百度搜索**（免费兜底）→ DuckDuckGo（超时缩至 4s，仅最后兜底）。全部源超时上限收紧。
- **地图优先策略**（`prompt.txt`）：geocode 精确命中（兴趣点/门牌号）可直接判定、**无需再调 web_search**；未命中或精度低（道路及以下）才搜索交叉验证。来源网页链接从"有效地址必须提供"放宽为"调用了 web_search 且有结果才必须提供"（用户明确：地图成功即可不再搜索）。
- **实时进度暴露**（`agent/agent.py` + `app.py`）：Agent 新增 `progress_callback`，`_run_agent_loop`/`_apply_guard` 每次 step_log 变化即推送；前端三条审核路径（对话框直审 / 文件确认 / 图片确认）统一用 `st.status` + 占位符实时渲染"AI 分析中 → 调用高德核验 ✓ → 联网搜索 ✓ → 结果验证 ✓"，用户可感知进程、不再像卡死。
- **明细扩展屏**（`app.py`）：「展开审核明细」改为独立、加粗、primary 醒目按钮；点击后 `st.dialog` + CSS 固定为**右侧抽屉式扩展屏**（全高 46vw、滑入动画、可滚动），内含明细表 + 下载 + 「收起 ▾」按钮；主会话区只留概要 + 按钮。
- **五列表格 + 审核信息源列**：表格从四列改为五列（+审核信息源）。`prompt.txt` 输出格式更新；`agent.py` `_extract_table_rows`/`_build_merged_table` 支持五列（兼容四列旧格式）；`guard.py` Rule D 文案同步；`app.py` 新增程序化兜底——`_format_basis`（按【标准一~五】小标题分段、`<br>` 分隔）、`_build_source_cell`（高德**定位链接**=图钉精确定位坐标 / 高德**搜索链接**=关键词搜索结果页 / 来源网页，三类各自分段并附区别说明），即使模型把链接写错列也能正确归位。
- `tests/test_live_api.py` 重写：20 项断言（前端辅助函数单测 + 三条主链路 + 进度回调 + 搜索回退链实测），web_search 改回真实链路（Bing CN 沙箱内可达，不再桩化）。

**验证**：`py_compile` 全过；单测+真实 API 回归 **20/20 通过**；Streamlit 启动无报错。实测模型已按地图优先策略执行（精确命中后自动跳过搜索），搜索 0.47s 返回。**未推送远端 git**。

**原因**：用户本地实测反馈——①联网搜索反复超时拖慢审核（DDG 国内被墙）；②审核过程无进度感知；③展开明细入口太不显眼且明细挤在主页面右列；④审核依据未分段、高德两个链接无区别说明、链接应独立成列。

---

## 2026-08-13 (二次修订): 数据质量预审 + 溯源链接强化（按用户最新澄清）

**变更**：
- `agent/agent.py`：
  - `prepare_excel_audit` / 新增 `assess_ocr_quality`：上传/截图先由模型出《数据质量预审报告》（仅文本理解，不调外部工具）——评估每条地址 6 级完整度、指出"应该有但实际没有"的信息、提示 OCR 遗漏/截断，并追问用户补充；确认后才进正式审核（呼应"上传/截图需预审、对话输入不预审"）。
  - `confirm_and_audit(supplement="")`：接收用户在预审阶段补充的信息并注入正式审核上下文。
  - `_build_quality_report` 模型调用失败时降级为机械预览，保证流程不中断。
- `app.py`：
  - 文件 / 图片上传后，对话输入框在预审阶段改作"补充信息"入口，支持多轮补充；新增「✕ 取消」退出预审；确认按钮文案改为"开始审核（信息已完整）"。
  - OCR 预览改为 `assess_ocr_quality` 质量报告。
  - 链接二次包裹 bug 修复：`_linkify_urls` 先保护已有 Markdown 链接（如 `🔗 高德地图定位`），再包裹裸 URL，避免 `[🔗 [🔗 ...](url)](url)` 坏链（prompt 要求输出 Markdown 链接，此前必触发）。
  - `render_audit_result` 统计计数改为基于解析出的「审核结果」列，避免依据列文字干扰。
- `agent/tools.py` + `.env.example` + `README.md`：移除虚假 `.xls` 支持（openpyxl 对 .xls 抛异常后落到 CSV 解析必失败），上传控件与描述统一为 `.xlsx/.csv`；高德 Key 说明改为"已预配、不可用再替换"。
- `prompt.txt`：明确"上传先数据质量预审再正式审核"两阶段；强化"有效地址必须返回地图定位链接(marker/map) + 至少一条搜索来源链接"。

**原因**：用户澄清——预审只对批量上传、且必须是模型驱动的数据质量评估+追问补充；正式报告对有效地址需可溯源链接以建立信任。

---

## 2026-08-13: 缺陷修复 + 按需求修订（反幻觉 / 预审范围 / 高德Key / 结果渲染）

**变更**：
- `agent/guard.py` `_extract_urls` 采集 geocode 的 `map_url` / `marker_url`，Rule B 不再把真实地图链接误判为"编造"（B1，核心卖点"harness 拦截编造"此前反向失效）；单测已验证
- `app.py` `render_audit_result` 重构：主会话区只显示「审核概要」，点击概要后在**右侧**展开详细表格，并提供 CSV / MD 下载；移除会 404 的 `localhost` 裸链与每轮 rerun 重写文件（B2/B3）；移除底部冗余摘要面板；表格渲染前清理 `<br>` 避免竖排错乱（回应"表格堆在主会话区、格式错乱"反馈）
- `agent/agent.py`：
  - 预审拦截改为**仅针对文件 / 截图批量上传**的工程化约束：`prepare_excel_audit` 仅解析 + 预览，`confirm_and_audit` 在用户点击「开始审核」后才调工具；**对话输入框地址直接审核、无预审**（修正上一轮误将预审加到对话输入的错误）
  - `process_excel` 改为每批 5 条分块 + 合并，**不再硬截断丢数据**（原 34 行被截到 30 行）；回归测试验证 34 条全量保留
  - 移除 `phase` 状态机（预审已改为上传按钮工程化约束）
- `agent/tools.py` DuckDuckGo fallback 正则容错（B9）
- `agent/llm.py` + `agent/tools.py` 增加 `.env.example` 兜底加载，使预配高德 Key **开箱即用**（用户无需自建 .env）
- `.env.example` 恢复预配共享高德 Key（按用户要求保留），并加"不可用如何申请替换"注释；`landing.html` 增加高德 Key 说明段落与替换步骤
- 新增 `.gitignore`：忽略个人 `.env`（LLM Key）但保留 `.env.example`（共享高德 Key）

**原因**：用户复核指出预审范围错误（应只限批量上传）、高德 Key 应保留预配、结果应主会话只显摘要 + 右侧折叠展开 + 可下载。已据此修订并单测 / 回归验证。

---

## 2026-07-27: 预审报告机制 + 审核结果展示重构

**变更**：
- `prompt.txt` 对话流程新增步骤 4-5（数据预审报告 + 等待用户确认），禁止在确认前调用外部工具
- `app.py` 对话区渲染统一为摘要 + 面板模式，所有 assistant 消息自动检测审核表格 → 展示统计行 + 📄📥 链接
- 修复 `is_audit` 检测误判（`|:---:|` 格式不匹配 `|---` 子串）、非审核消息误触发面板
- 修复 CSV 上传路径未触发审核面板的问题（消息渲染循环统一处理）

**原因**：节省 API 费用，用户确认后再审核；聊天框内不再裸渲 Markdown 表格

---

## 2026-07-24: 审核明细文件化 + 并行工具调用 + 速度优化

**变更**：
- 审核结果不再内联渲染，改为写 `audit_output/` 目录（MD + CSV），聊天框只放摘要 + 链接
- `agent.py` ReAct 循环工具调用从串行改为 `ThreadPoolExecutor` 并行执行
- `tools.py` geocode 增加内存缓存、CSV 解析去掉 `csv.Sniffer`
- `tools.py` geocode 新增 `map_url` 字段（`ditu.amap.com/search?query=...`）

**原因**：表格溢出无法在 Streamlit 解决；并行调用 geocode+search 节省 ~1.5s/条

---

## 2026-07-23: 反幻觉工程化（ResultGuard）上线

**变更**：
- 新增 `agent/guard.py`：EvidenceCollector + ResultGuard（4 条规则 + 重试机制）
- `agent.py` ReAct 循环返回前调用 Guard，不通过则注入修正指令重试
- 前端 URL 自动渲染为可点击链接 + 审核完成统计面板
- Thread 实时进度方案尝试并回退（不稳定）

**原因**：单靠 Prompt 约束 LLM 行为不可靠，需要程序化验证输出

---

## 2026-07-22: 产品主页 + 新手引导

**变更**：
- 新增 `landing.html`（Geist 字体 + Slate+Gold 配色）
- 新手引导弹窗（三步流程）
- 机器人头像集成
- `app.py` CSS 与 landing 同步

**原因**：需要美观的产品主页用于秋招展示

---

## 2026-07-17: Agent 核心功能完成

**变更**：
- `agent/` 模块搭建（agent/llm/tools）
- 高德地图 geocode + Bing 搜索 web_search + Excel 解析
- ReAct 循环实现
- Streamlit 对话界面
- 五大审核标准 Prompt

**原因**：项目启动，MVP 核心链路

---

## 2026-08-13(八次修订): 独立代码评审系统性加固

**变更**：
- 独立 agent 通读全代码评审，修复 4 严重（预审失败重放/高德失效误判无效/丢弃 count 多候选/重复 key 崩溃）+ 13 中等 + 轻微项
- `prepare_excel_audit` 改返回 `(ok, text)` 元组 + `_clear_batch_state` 防状态残留；`app.py` 仅 `ok` 时进入预审
- `geocode` 区分 `status=error`（API 故障→判不确定）与 `found=false`；暴露 `match_count/is_unique/other_candidates`
- `_extract_table_rows`/`_parse_audit_rows` 保留中间空单元格 + 表头子串判定 + 无表头按首行列数推断（防列错位）
- `_match_chunk` 加地址一致性校验防串号；`_looks_like_audit_table` 替代 `"|---"` 固定判定
- `_level_description` 对齐高德官方 level 枚举；Excel/CSV 列名候选词表统一
- `llm.py` 新增 `LLMCallError` 显式抛出，`agent` 调用点优雅降级；`_strip_links` 不再吞字
- `render_audit_result` 增 `uid` 防重复 key；审核期间禁用 chat_input；新会话清 `file_/img_` 键
- `prompt.txt` 同步：geocode error→不确定、is_unique=false→不确定、level 枚举、序号=文件行号
- `tests/test_live_api.py` 34 项全过（新增 T7 geocode 健壮性、T8 防串号）

**原因**：用户对全量代码做第三方视角评审，消除遗留正确性 bug 与健壮性缺口

## 2026-08-13(九次修订): 高德限流根治 + 重试降级 + 「审核失败」结论

**背景**：用户实测发现"高德地图 API 调用失败"偶发出现。经真实诊断定位根因为**高德共享 Key（23f710e1...）QPS 限流（infocode=10021, CUQPS_HAS_EXCEEDED_THE_LIMIT）**——连续密集调用（批量审核）必触发；单条/低频调用正常。原实现把限流/网络异常一律归为"不确定"，既不合理（地址可能真实有效）又浪费了可恢复的错误。

**变更**：
- `agent/tools.py` `geocode`：抽重试循环，**单次失败（限流/网络抖动/瞬时错误）自动重试 ≤3 次（指数退避 0.3/0.6/1.2s）**；重试耗尽返回 `status=error` 且带 `degraded=True`/`reason`（失败分类），提示调用方改用 `web_search` 降级；不可重试类（Key 失效 10001 / 配额永久耗尽 10003 等）直接失败不空耗配额；`found=false`（高德正常未找到）不重试（重试无意义）。新增 `_geocode_error` 辅助构造降级结果。
- `prompt.txt`：审核结果由**四类→五类**（新增"审核失败"）；重写技术性错误处理——geocode 重试失败**必须降级 web_search**，两级皆失败判"审核失败"（非"不确定"），依据须写明 ①地图 API 失败原因 ②已尝试联网搜索但无结果 ③下一步建议；明确"审核失败≠不确定"；新增**联网搜索强相关性要求**（查询词精确围绕地址、仅采信直接强相关证据、必须引用具体来源 URL）。
- `agent/agent.py` `chunk_ctx`：批量指令强化降级规则（geocode 重试失败→web_search→仍无果判"审核失败"），并与"地址信息不足→不确定"明确区分。
- `agent/guard.py`：`VALID_VERDICTS` 加入"审核失败"；Rule A 对"审核失败"放宽证据要求（其本身即"无成功证据"声明），并软校验依据是否含失败原因/下一步；新增 `_mentions_next_step` 辅助。
- `app.py` `render_audit_result`：状态卡新增"⛔ 审核失败"计数。
- `tests/test_live_api.py`：T7b 断言随新语义调整；新增 **T9** geocode 重试/降级离线单测（限流重试耗尽=3 次调用+degraded、限流自愈=2 次调用、不可重试错误=1 次不重试）。

**验证**：全部 .py `py_compile` 通过；真实 DeepSeek+高德+联网搜索回归 **43/43 通过**（T1d 原为脆弱负向子串断言，已修正为"未被判有效且识别为完整度不足"，非功能回归）。已先 `git commit` 本地快照 `66013b9`（仅本项目 12 文件，排除 `.env` 与父目录）。**未推送远端 git**。

**原因**：用户指出"地图 API 没搜到就一律判不确定"不合理——技术性故障不应等同于地址本身无效；并要求先存快照再改、重试≤3、降级联网搜索、失败明确回报原因与下一步。

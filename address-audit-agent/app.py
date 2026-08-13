"""
地址审核 Agent — Streamlit 前端
运行方式：streamlit run app.py
"""
import re, io, pathlib, time as _t, hashlib
from pathlib import Path
import pandas as pd
import streamlit as st
from agent import AddressAuditAgent

# 头像路径（相对于本文件所在目录）
_AVATAR = str(Path(__file__).resolve().parent / "robot-avatar.png")

# URL 匹配
_URL_RE = re.compile(r"(https?://[^\s\)\]）\]>，。；;\"]+)")
# Markdown 链接匹配 [text](url)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(\s*(https?://[^\s)]+)\)")
# 进度步骤图标
_STEP_ICONS = {"done": "✅", "running": "🔄", "error": "❌", "skipped": "⊘", "warn": "⚠️"}


def _is_table_separator(line: str) -> bool:
    """检测 Markdown 表格分隔行 |---|---|"""
    return bool(re.match(r"^\|[\s\-:]+\|[\s\-:]+", line))

def _linkify_urls(text: str) -> str:
    """将裸 URL 转为可点击的 Markdown 链接。

    关键：若文本中已存在标准 Markdown 链接 [text](url)（如 prompt 要求输出的
    「🔗 高德地图定位」），不再二次包裹，否则会生成 [🔗 [🔗 ...](url)](url) 坏链。
    """
    # 先保护已有 Markdown 链接，避免其内部 URL 被再次包裹
    _protected: list[str] = []
    def _protect(m: re.Match) -> str:
        _protected.append(m.group(0))
        return f"\x00L{len(_protected) - 1}\x00"
    text = re.sub(r"\[[^\]]*\]\(\s*https?://[^\s)]+\)", _protect, text)
    text = _URL_RE.sub(lambda m: f"[🔗 {m.group(1)}]({m.group(1)})", text)
    for i, link in enumerate(_protected):
        text = text.replace(f"\x00L{i}\x00", link)
    return text


def render_message(text: str) -> str:
    """将文本中的 URL 转为可点击的 Markdown 链接，<br> 转为真实换行"""
    # <br> → 真实换行（普通对话消息可正常换行）
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    return _linkify_urls(text)


def _classify_url(url: str) -> str:
    """链接分类：marker=高德定位链接 / map=高德搜索链接 / web=来源网页"""
    if "uri.amap.com/marker" in url:
        return "marker"
    if "ditu.amap.com" in url or "amap.com/search" in url:
        return "map"
    return "web"


def _strip_links(text: str) -> str:
    """从依据文本中剥离链接（链接统一收拢到「审核信息源」列），并清理由此留下的空标签"""
    text = _MD_LINK_RE.sub(lambda m: m.group(1), text)  # [文字](url) → 文字
    text = _URL_RE.sub("", text)  # 裸 URL → 删除
    text = re.sub(r"🔗\s*", "", text)  # 仅移除 🔗 图标，链接文本/URL 已由前两步剥离（避免吞掉后续文字）
    return text


def _format_basis(text: str) -> str:
    """审核依据按五项标准分段：每段一个小标题（加粗），段间用 <br> 分隔（表格单元格内换行）"""
    text = _strip_links(text).replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n").replace("|", "／")
    lines = [ln.strip() for ln in text.split("\n")]
    text = " ".join(ln for ln in lines if ln)
    if not text:
        return "—"
    # 在「【标准X」或裸「标准X」（前面不是【）处切段；避免零宽断言把【和标准拆成两段
    parts = [
        p.strip()
        for p in re.split(r"(?=【标准[一二三四五])|(?<!【)(?=标准[一二三四五])", text)
        if p.strip()
    ]
    out = []
    for p in parts:
        # 段首小标题加粗：【标准一·完整详细】 / 标准一（完整详细）： / 标准二： ...
        p = re.sub(r"^(【?标准[一二三四五][^：:】]{0,24}】?\s*[：:]?)", r"**\1**", p)
        out.append(p)
    return "<br>".join(out)


def _build_source_cell(basis: str, source: str) -> str:
    """构建「审核信息源」单元格：定位/搜索/网页三类链接各自分段，并说明两个高德链接的区别"""
    links: list[tuple[str, str]] = []
    for text in (source, basis):  # 优先信息源列；模型误放进依据列的链接也兜底提取
        if not text:
            continue
        for m in _MD_LINK_RE.finditer(text):
            links.append((m.group(1).strip(), m.group(2).strip()))
        covered = {u for _, u in links}
        for m in _URL_RE.finditer(text):
            if m.group(1) not in covered:
                links.append(("", m.group(1)))

    order = {"marker": 0, "map": 1, "web": 2}
    links.sort(key=lambda x: order[_classify_url(x[1])])
    seen: set[str] = set()
    entries: list[str] = []
    for label, url in links:
        if url in seen:
            continue
        seen.add(url)
        kind = _classify_url(url)
        if kind == "marker":
            entries.append(
                f"**📍 高德地图定位链接**<br>[打开地图精确定位]({url})<br>说明：打开后该地址以图钉精确定位在地图上（精确到坐标）"
            )
        elif kind == "map":
            entries.append(
                f"**🔎 高德地图搜索链接**<br>[打开高德搜索页]({url})<br>说明：打开后是以该地址为关键词的高德搜索结果页，可查看周边与相关地点"
            )
        else:
            txt = label if label and not label.startswith("🔗") else "查看来源网页"
            entries.append(f"**📰 来源网页**<br>[{txt}]({url})")
    return "<br>".join(entries) if entries else "—"


def _build_detail_markdown(rows_data: list[dict]) -> str:
    """由解析出的行重建六列明细表：依据分段 + 信息源独立成列。

    单元格内若含竖线会破坏 Markdown 表格，故全部转全角斜杠（／）兜底。
    """
    _esc = lambda v: str(v).replace("|", "／").replace("\n", " ")
    lines = ["| 序号 | 姓名 | 地址 | 审核结果 | 审核依据 | 审核信息源 |", "|---|---|---|---|---|---|"]
    for r in rows_data:
        name = _esc(r.get("姓名", ""))
        addr = _esc(r.get("地址", ""))
        verdict = _esc(r.get("审核结果", ""))
        basis = _format_basis(str(r.get("审核依据", "")))
        source = _build_source_cell(str(r.get("审核依据", "")), str(r.get("审核信息源", "")))
        lines.append(f"| {r.get('序号','')} | {name} | {addr} | {verdict} | {basis} | {source} |")
    return "\n".join(lines)


def _render_live_progress(container, step_log: list[dict]):
    """实时渲染审核进度（调用了哪些工具、走到哪一步），供 progress_callback 回调使用"""
    lines = [f"{_STEP_ICONS.get(e.get('status', ''), '·')} {e.get('text', '')}" for e in step_log]
    container.markdown("  \n".join(lines) if lines else "…")


def _parse_audit_rows(content: str) -> list[dict]:
    """从审核表格输出提取数据行（跳过表头与分隔行），兼容六列（含姓名）/五列/四列格式。

    六列：序号 | 姓名 | 地址 | 审核结果 | 审核依据 | 审核信息源
    五列：序号 | 地址 | 审核结果 | 审核依据 | 审核信息源（对话框单条审核，无姓名）
    始终返回含全部 6 个键的 dict（缺列填空），供明细渲染与 CSV 导出统一处理。

    健壮性（修复评审 🟠-5/7）：切分单元格时**保留中间空单元格**（仅去除 Markdown 表格
    首尾边框空串），避免「姓名/信息源留空」导致整行列错位（地址被错当审核结果）。
    """
    rows = []
    header_skipped = False
    is_six = False  # 表头是否含「姓名」列
    for line in content.split("\n"):
        s = line.strip()
        if not s.startswith("|") or _is_table_separator(s):
            continue
        cells = s.split("|")
        # 去掉 Markdown 表格边框产生的首尾空串，但保留中间空单元格
        if cells and not cells[0].strip():
            cells = cells[1:]
        if cells and not cells[-1].strip():
            cells = cells[:-1]
        parts = [c.strip() for c in cells]
        if not header_skipped:
            if len(parts) >= 4 and "序号" in parts[0] and ("地址" in parts or "姓名" in parts):
                header_skipped = True
                is_six = "姓名" in parts
                continue
            continue
        if len(parts) < 4:
            continue
        if is_six:
            rows.append({
                "序号": parts[0],
                "姓名": parts[1] if len(parts) > 1 else "",
                "地址": parts[2] if len(parts) > 2 else "",
                "审核结果": parts[3] if len(parts) > 3 else "",
                "审核依据": " | ".join(parts[4:-1]) if len(parts) > 5 else (parts[4] if len(parts) > 4 else ""),
                "审核信息源": parts[-1] if len(parts) > 5 else "",
            })
        else:
            rows.append({
                "序号": parts[0], "姓名": "",
                "地址": parts[1] if len(parts) > 1 else "",
                "审核结果": parts[2] if len(parts) > 2 else "",
                "审核依据": " | ".join(parts[3:-1]) if len(parts) > 4 else (parts[3] if len(parts) > 3 else ""),
                "审核信息源": parts[-1] if len(parts) > 4 else "",
            })
    return rows


def _clean_for_table(text: str) -> str:
    """用于表格渲染：<br> 转为空格（避免破坏 Markdown 表格结构），URL 转为可点击链接（不二次包裹已有链接）"""
    text = text.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    return _linkify_urls(text)


@st.dialog("📑 审核明细报告", width="large")
def show_audit_detail(content: str, content_hash: str):
    """右侧抽屉式扩展屏（配合 CSS 固定到右侧、全高、滑入）：明细六列表格（含姓名）+ 下载 + 收起"""
    rows_data = _parse_audit_rows(content)
    if rows_data:
        # unsafe_allow_html=True：让单元格内的 <br> 真实换行（依据按标准分段、信息源逐条分段）
        st.markdown(_build_detail_markdown(rows_data), unsafe_allow_html=True)
    else:
        st.markdown(_clean_for_table(content), unsafe_allow_html=True)
    st.divider()
    csv_bytes = b""
    if rows_data:
        csv_bytes = pd.DataFrame(rows_data).to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.download_button(
            "📥 下载 CSV", csv_bytes, file_name=f"audit_{content_hash}.csv",
            mime="text/csv", key=f"dlg_csv_{content_hash}", disabled=not rows_data,
        )
    with c2:
        st.download_button(
            "📄 下载明细(MD)", content.encode("utf-8"), file_name=f"audit_{content_hash}.md",
            mime="text/markdown", key=f"dlg_md_{content_hash}",
        )
    with c3:
        if st.button("收起 ▾", key=f"dlg_close_{content_hash}", use_container_width=True):
            st.rerun()


def render_audit_result(content: str, uid: str = ""):
    """渲染一条审核报告消息（第 2 步 · 最终审核报告）。

    主会话区只显示紧凑的「审核完成」状态卡（概要计数）+ 醒目的独立「打开终审报告（右侧弹窗）」
    按钮；点击后完整明细在右侧抽屉式扩展屏中展示（含收起按钮与下载）。
    主对话区【不再】铺开大表格，避免与「数据预审报告」气泡混淆，让用户清楚当前处于「终审核对」环节。

    uid：调用方传入的稳定唯一标识（如消息序号），用于拼接 widget key，避免多条相同内容的
    审核报告触发 StreamlitDuplicateElementKey（🔴-4 修复）。
    """
    rows_data = _parse_audit_rows(content)
    # 统计基于解析出的「审核结果」列，避免依据列文字（如"不满足有效地址标准"）干扰计数
    _verdicts = [r.get("审核结果", "") for r in rows_data]
    count_valid = sum(1 for v in _verdicts if "有效地址" in v)
    count_invalid = sum(1 for v in _verdicts if "无效地址" in v)
    count_uncertain = sum(1 for v in _verdicts if "不确定" in v)
    count_bad = sum(1 for v in _verdicts if "不符合地址格式" in v)
    count_failed = sum(1 for v in _verdicts if "审核失败" in v)
    content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:12]
    u = f"{uid}_" if uid else ""  # 防重复 key 前缀

    # 环节标识：明确这是第 2 步（最终审核报告），完整明细在右侧弹窗
    st.markdown("**📑 第 2 步 · 最终审核报告**")
    st.markdown(
        f"✅ **{count_valid}** 有效　⚠️ **{count_uncertain}** 不确定　"
        f"❌ **{count_invalid}** 无效　🚫 **{count_bad}** 不符合格式　"
        f"⛔ **{count_failed}** 审核失败"
    )
    # 醒目独立按钮：点击后从右侧弹出完整明细扩展屏
    if st.button("📑 打开终审报告（右侧弹窗）", key=f"{u}open_{content_hash}", type="primary"):
        show_audit_detail(content, content_hash)
    st.caption("完整明细（每条地址的审核依据与可点击信息源）请在右侧弹窗查看 ↓")

    # 下载按钮（主会话区也始终可见）
    csv_bytes = None
    if rows_data:
        csv_bytes = pd.DataFrame(rows_data).to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.download_button(
            "📥 下载 CSV",
            csv_bytes or b"",
            file_name=f"audit_{content_hash}.csv",
            mime="text/csv",
            key=f"{u}dl_csv_{content_hash}",
            disabled=not csv_bytes,
        )
    with c2:
        st.download_button(
            "📄 下载明细(MD)",
            content.encode("utf-8"),
            file_name=f"audit_{content_hash}.md",
            mime="text/markdown",
            key=f"{u}dl_md_{content_hash}",
        )

st.set_page_config(
    page_title="地址信息审核助手",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================================================================
# 设计系统 — CSS
# 色彩策略：Restrained，淡金色点缀
# 物理场景：金融机构合规岗，明亮办公室桌面，需要信任感和精确感
# ================================================================
st.markdown(
    """
<style>
    
    /* ---- Design tokens (sync with landing.html) ---- */
    :root {
        --ink: #0f172a;
        --ink-muted: #475569;
        --bg: #ffffff;
        --surface: #f8fafc;
        --border: #e2e8f0;
        --accent: #c8941e;
        --accent-hover: #a67c1a;
        --accent-light: #fef9f0;
        --success: #15803d;
        --success-light: #f0fdf4;
        --warning: #c2410c;
        --warning-light: #fff7ed;
        --danger: #b91c1c;
        --radius: 8px;
    }

    body, .stApp, .stMarkdown, .stChatMessage, .stTextInput, .stButton, .stCaption {
        font-family: 'Geist', system-ui, -apple-system, sans-serif !important;
    }
    body { background: var(--bg); }
    .main-header {
        font-size: 1.25rem; font-weight: 700; color: var(--ink);
        margin-bottom: 0.125rem; letter-spacing: -0.01em;
    }
    .sub-header {
        font-size: 0.8125rem; color: var(--ink-muted);
        margin-bottom: 1.25rem; line-height: 1.5;
    }

    /* ---- 侧边栏 ---- */
    [data-testid="stSidebar"] { background-color: #f7f5f0; }
    [data-testid="stSidebar"] .stMarkdown { font-family: 'Geist', system-ui, sans-serif !important; }
    /* ---- 头像放大 ---- */
    [data-testid="stChatMessage"] img { transform: scale(1.3); transform-origin: center; }
    .sidebar-brand {
        display: flex; align-items: center; gap: 0.5rem;
        padding: 0.25rem 0 0.75rem 0;
    }
    .sidebar-brand-name {
        font-size: 0.9rem; font-weight: 700; color: var(--ink);
    }
    .feature-list { list-style: none; padding: 0; margin: 0.25rem 0 0.75rem 0; }
    .feature-list li {
        display: flex; align-items: flex-start; gap: 0.5rem;
        padding: 0.45rem 0; border-bottom: 1px solid var(--border);
        font-size: 0.78rem; color: var(--ink-muted); line-height: 1.4;
    }
    .feature-list li:last-child { border-bottom: none; }
    .feature-icon {
        flex-shrink: 0; width: 18px; height: 18px; border-radius: 4px;
        display: flex; align-items: center; justify-content: center; font-size: 0.65rem;
    }
    .fi-excel { background: var(--success-light); color: var(--success); }
    .fi-cam   { background: var(--warning-light); color: var(--warning); }
    .fi-table { background: var(--accent-light); color: var(--accent); }

    /* ---- 按钮 ---- */
    .stButton > button {
        font-family: 'Geist', system-ui, sans-serif !important;
        font-size: 0.8rem; font-weight: 500;
        border-radius: var(--radius); transition: all 150ms ease;
        border-color: var(--border);
    }
    .stButton > button:hover { border-color: var(--accent); background: var(--accent-light); }

    hr { border-color: var(--border) !important; margin: 0.5rem 0 !important; }

    /* ---- 状态标签 ---- */
    .status-valid   { color: #15803d; font-weight: 600; }
    .status-invalid { color: #b91c1c; font-weight: 600; }
    .status-uncertain { color: #c2410c; font-weight: 600; }
    .status-bad-fmt { color: #94a3b8; font-weight: 600; }

    .stat-row { display:flex; gap:0.75rem; }
    .stat-card { flex:1; text-align:center; padding:0.6rem 0.4rem; border-radius:8px; border:1px solid #e2e8f0; }
    .stat-card.valid { background:#f0fdf4; border-color:#bbf7d0; }
    .stat-card.uncertain { background:#fffbeb; border-color:#fde68a; }
    .stat-card.invalid { background:#fef2f2; border-color:#fecaca; }
    .stat-card.badfmt { background:#f8fafc; border-color:#e2e8f0; }
    .stat-label { display:block; font-size:0.8rem; color:#475569; margin-bottom:0.2rem; }
    .stat-value { display:block; font-size:1.5rem; font-weight:600; color:#0f172a; }

    /* ---- 审核结果表格列宽（六列：序号/姓名/地址/结果/依据/信息源）---- */
    .stChatMessage table { table-layout:fixed; width:100%; border-collapse:collapse; word-break:break-word; }
    .stChatMessage table th:nth-child(1) { width:5%; }
    .stChatMessage table td:nth-child(1) { width:5%; text-align:center; }
    .stChatMessage table th:nth-child(2) { width:9%; }
    .stChatMessage table td:nth-child(2) { width:9%; }
    .stChatMessage table th:nth-child(3) { width:18%; }
    .stChatMessage table td:nth-child(3) { width:18%; }
    .stChatMessage table th:nth-child(4) { width:8%; }
    .stChatMessage table td:nth-child(4) { width:8%; text-align:center; font-weight:600; white-space:nowrap; }
    .stChatMessage table th:nth-child(5) { width:35%; }
    .stChatMessage table td:nth-child(5) { width:35%; line-height:1.6; font-size:0.78rem; overflow-wrap:break-word; word-break:break-word; }
    .stChatMessage table th:nth-child(6) { width:25%; }
    .stChatMessage table td:nth-child(6) { width:25%; line-height:1.6; font-size:0.78rem; overflow-wrap:break-word; word-break:break-word; }
    .stChatMessage table th { font-size:0.72rem; padding:0.3rem 0.35rem; white-space:nowrap; }
    .stChatMessage table td { padding:0.35rem; vertical-align:top; }

    /* ---- 侧边栏步骤指示器（让用户感知当前环节）---- */
    .audit-steps { margin: 0.35rem 0 0.75rem 0; }
    .audit-step { display:flex; align-items:center; gap:0.45rem; padding:0.4rem 0.6rem; border-radius:8px;
        font-size:0.8rem; margin-bottom:0.35rem; border:1px solid var(--border); }
    .audit-step.done { background:#f0fdf4; border-color:#bbf7d0; color:#15803d; }
    .audit-step.active { background:var(--accent-light); border-color:var(--accent); color:var(--accent); font-weight:700; }
    .audit-step.pending { background:var(--surface); color:var(--ink-muted); }
    .audit-step .dot { font-size:0.95rem; }

    /* ---- 主按钮（打开终审报告 / 开始审核等 primary 按钮）：加粗、更大、更醒目 ---- */
    .stButton > button[kind="primary"] {
        font-weight: 700 !important; font-size: 0.95rem !important;
        padding: 0.55rem 1.1rem !important; border-radius: var(--radius) !important;
        letter-spacing: 0.02em;
    }

    /* ---- 明细扩展屏：st.dialog 固定为右侧抽屉（全高、滑入） ---- */
    @keyframes slideInRight {
        from { transform: translateX(48px); opacity: 0.4; }
        to   { transform: translateX(0);    opacity: 1; }
    }
    div[data-testid="stDialog"] div[role="dialog"],
    div[data-testid="stDialog"] > div[data-testid="stModal"],
    div[data-testid="stDialog"] > div:first-child {
        position: fixed !important; top: 0 !important; right: 0 !important; left: auto !important;
        height: 100vh !important; max-height: 100vh !important;
        width: 60vw !important; max-width: 60vw !important; min-width: 480px !important;
        margin: 0 !important; border-radius: 12px 0 0 12px !important;
        overflow-y: auto !important;
        animation: slideInRight 0.25s ease;
    }

    /* ---- 扩展屏内六列明细表格列宽 ---- */
    div[data-testid="stDialog"] table { table-layout:fixed; width:100%; border-collapse:collapse; word-break:break-word; }
    div[data-testid="stDialog"] table th:nth-child(1), div[data-testid="stDialog"] table td:nth-child(1) { width:5%; text-align:center; }
    div[data-testid="stDialog"] table th:nth-child(2), div[data-testid="stDialog"] table td:nth-child(2) { width:9%; }
    div[data-testid="stDialog"] table th:nth-child(3), div[data-testid="stDialog"] table td:nth-child(3) { width:16%; }
    div[data-testid="stDialog"] table th:nth-child(4), div[data-testid="stDialog"] table td:nth-child(4) { width:8%; text-align:center; font-weight:600; white-space:nowrap; }
    div[data-testid="stDialog"] table th:nth-child(5), div[data-testid="stDialog"] table td:nth-child(5) { width:32%; line-height:1.65; font-size:0.72rem; overflow-wrap:break-word; }
    div[data-testid="stDialog"] table th:nth-child(6), div[data-testid="stDialog"] table td:nth-child(6) { width:30%; line-height:1.65; font-size:0.72rem; overflow-wrap:break-word; }
    div[data-testid="stDialog"] table th { font-size:0.72rem; padding:0.3rem 0.35rem; white-space:nowrap; }
    div[data-testid="stDialog"] table td { padding:0.4rem 0.35rem; vertical-align:top; }
</style>
""",
    unsafe_allow_html=True,
)

# ================================================================
# 侧边栏（精简：品牌 + 功能列表 + 重置）
# ================================================================
with st.sidebar:
    st.markdown(
        """
    <div class="sidebar-brand">
        <span class="sidebar-brand-name">地址审核 Agent</span>
    </div>
    <ul class="feature-list">
        <li><span class="feature-icon fi-map">📍</span> 高德地图 + 搜索双重核验</li>
        <li><span class="feature-icon fi-excel">📁</span> Excel / CSV 批量审核</li>
        <li><span class="feature-icon fi-cam">📷</span> 图片 OCR 地址提取</li>
        <li><span class="feature-icon fi-table">📋</span> Harness 护栏 · 每链可溯源</li>
    </ul>
    """,
        unsafe_allow_html=True,
    )

    # ---- 步骤指示器：让用户清晰感知当前处于哪个环节（数据预审 / 终审 / 完成）----
    _phase = st.session_state.get("phase", "idle")
    _s1 = "done" if _phase == "done" else ("active" if _phase == "precheck" else "pending")
    _s2 = "done" if _phase == "done" else "pending"
    _dot1 = "✅" if _s1 == "done" else ("🔄" if _s1 == "active" else "⚪")
    _dot2 = "✅" if _s2 == "done" else "⚪"
    st.markdown(
        f"""
    <div class="audit-steps">
      <div class="audit-step {_s1}"><span class="dot">{_dot1}</span> 第 1 步 · 数据预审</div>
      <div class="audit-step {_s2}"><span class="dot">{_dot2}</span> 第 2 步 · 最终审核报告</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.divider()
    if st.button("🔄 新会话", use_container_width=True):
        # 清理已上传文件/图片的「已处理」标记键，避免新会话复用旧文件缓存（🟠-12 修复）
        keys_to_clear = [k for k in st.session_state if k.startswith("file_") or k.startswith("img_")]
        for k in keys_to_clear:
            del st.session_state[k]
        for k in ("pending_audit_file", "pending_img_prompt", "pending_supplement",
                  "audit_in_progress", "audit_total_chunks", "audit_done_chunks"):
            st.session_state.pop(k, None)
        st.session_state.agent = AddressAuditAgent()
        st.session_state.messages = []
        st.session_state.agent_initialized = False
        st.session_state.phase = "idle"
        st.rerun()

# ================================================================
# 主页面
# ================================================================
st.markdown('<p class="main-header">地址信息审核</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">AI 驱动 · 高德地图定位 · OCR 图片识别 · 适用金融 KYC / AML 场景</p>',
    unsafe_allow_html=True,
)

# 初始化 Agent
if "agent" not in st.session_state:
    try:
        st.session_state.agent = AddressAuditAgent()
        st.session_state.messages = []
        st.session_state.agent_initialized = False
        st.session_state.phase = "idle"  # idle / precheck / done
    except ValueError as e:
        st.error(f"❌ {e}")
        st.info("复制 `.env.example` 为 `.env`，填入你的 LLM_API_KEY 即可（高德地图 Key 已预配，开箱即用）")
        st.stop()

agent: AddressAuditAgent = st.session_state.agent

if not st.session_state.agent_initialized:
    with st.spinner(""):
        greeting = agent.start()
    st.session_state.messages.append({"role": "assistant", "content": greeting})
    st.session_state.agent_initialized = True

# ================================================================
# 对话区
# ================================================================
for midx, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar=_AVATAR):
            content = msg["content"]
            mtype = msg.get("type", "")
            if mtype == "audit_report":
                # 第 2 步 · 最终审核报告：主会话仅状态卡 + 右侧弹窗入口
                render_audit_result(content, uid=str(midx))
            elif mtype == "preview":
                # 第 1 步 · 数据质量预审报告：普通气泡（不显示「打开终审报告」按钮）
                st.markdown(render_message(content))
            else:
                # 兜底：无 type 标记的历史消息用关键词启发式判定（仅作容错）
                has_table = "|---" in content or any(
                    "|" in l and "---" in l for l in content.split("\n")[:5]
                )
                has_verdict = any(
                    v in content for v in ("有效地址", "无效地址", "不确定", "不符合地址格式")
                )
                if has_table and has_verdict:
                    render_audit_result(content)
                else:
                    st.markdown(render_message(content))

# ================================================================
# 底部输入栏
# ================================================================
st.markdown('<p style="font-size:0.7rem;color:#a8a29e;margin:0 0 0.2rem 0;">📂 支持拖拽 Excel / CSV / 图片到输入框区域</p>', unsafe_allow_html=True)

uploaded_file = None
uploaded_img = None

# Upload + export row
cu1, cu2 = st.columns([0.06, 0.94])
with cu1:
    with st.popover("➕", use_container_width=True):
        uploaded_file = st.file_uploader(
            "📁 上传表格", type=["xlsx", "csv"],
            key="file_popover", label_visibility="collapsed",
        )
        uploaded_img = st.file_uploader(
            "🖼️ 上传图片", type=["png", "jpg", "jpeg"],
            key="img_popover", label_visibility="collapsed",
        )

_paused = bool(st.session_state.get("pending_audit_file") or st.session_state.get("pending_img_prompt"))
prompt = st.chat_input(
    "补充缺失信息后点击「开始审核」确认；或点「取消」退出预审…" if _paused else "输入地址开始审核…",
    # 批量审核进行中禁用输入，防止用户中途插入消息打乱分块上下文（🟡 修复）
    disabled=bool(st.session_state.get("audit_in_progress")),
)

# 处理表格上传（Excel / CSV）
if uploaded_file is not None:
    file_key = f"file_{uploaded_file.name}_{uploaded_file.size}"
    if file_key not in st.session_state:
        with st.spinner(f"解析 {uploaded_file.name}…"):
            try:
                # 仅解析 + 生成「数据预审报告」预览，不调工具（工程化预审拦截）
                # prepare_excel_audit 现返回 (ok, text) 元组：ok=False 时不应进入待确认态（🔴-1）
                ok, preview = agent.prepare_excel_audit(uploaded_file.getvalue(), uploaded_file.name)
            except Exception as e:
                st.error(f"处理出错：{e}")
                agent.reset()
                st.stop()
        # 解析失败（无有效地址 / 文件损坏）→ 报错并终止本回合，绝不复用上一轮报告
        if not ok:
            st.error(f"❌ {preview}")
            agent.reset()
            st.stop()
        st.session_state[file_key] = True
        st.session_state.messages.append(
            {"role": "user", "content": f"📁 上传文件：{uploaded_file.name}"}
        )
        # 第 1 步 · 数据预审报告：以对话气泡形式说明数据情况，并询问用户是否进行最终审核
        st.session_state.messages.append(
            {"role": "assistant", "content": f"📋 **第 1 步 · 数据质量预审报告**\n\n{preview}", "type": "preview"}
        )
        st.session_state["pending_audit_file"] = file_key  # 等待用户点击「开始审核」
        st.session_state["phase"] = "precheck"
        st.rerun()

# 文件预审确认：用户确认信息完整后才真正调工具审核（工程化约束，仅针对批量上传）
if st.session_state.get("pending_audit_file") and not st.session_state.get("audit_in_progress"):
    _supp = st.session_state.get("pending_supplement", "")
    if _supp:
        st.info(f"📝 已记录补充信息：{_supp}")
    c_confirm, c_cancel = st.columns([0.8, 0.2])
    with c_confirm:
        if st.button("▶ 开始审核（信息已完整）", key="btn_confirm_file", use_container_width=True):
            # 初始化批量审核状态（分块）；随后由下方「进度驱动」块逐批 rerun 处理
            _init = agent.begin_batch_audit(supplement=st.session_state.get("pending_supplement", ""))
            st.session_state["audit_in_progress"] = True
            st.session_state["audit_total_chunks"] = _init.get("chunks", 0)
            st.session_state["audit_done_chunks"] = 0
            st.session_state["pending_audit_file"] = None
            st.session_state["pending_supplement"] = ""
            st.rerun()
    with c_cancel:
        if st.button("✕ 取消", key="btn_cancel_file", use_container_width=True):
            st.session_state["pending_audit_file"] = None
            st.session_state["pending_supplement"] = ""
            st.session_state["phase"] = "idle"
            st.rerun()

# 批量审核进度驱动（Issue #3 修复核心）：
# 每批独立跑一次脚本运行（st.rerun 之间），避免单次阻塞冻结 UI；进度可见「第 X/N 批」。
if st.session_state.get("audit_in_progress"):
    _total_chunks = max(1, st.session_state.get("audit_total_chunks", 1))
    _done = st.session_state.get("audit_done_chunks", 0)
    _next = min(_done + 1, _total_chunks)
    with st.status(f"逐条核验中…（第 {_next}/{_total_chunks} 批）", expanded=True) as live_status:
        _prog = live_status.empty()
        agent.progress_callback = lambda log: _render_live_progress(_prog, log)
        _more = agent.audit_next_chunk()  # 处理单一批次（内部仍走 ReAct，进度实时流式更新）
        agent.progress_callback = None
        st.session_state["audit_done_chunks"] = _done + 1
        if _more:
            live_status.update(
                label=f"已处理 {_done + 1}/{_total_chunks} 批，继续核验…", state="running", expanded=True
            )
            st.rerun()
        else:
            report = agent.audit_finalize()
            live_status.update(label="审核完成 ✅", state="complete", expanded=False)
            st.session_state.messages.append(
                {"role": "assistant", "content": report, "type": "audit_report"}
            )
            st.session_state["audit_in_progress"] = False
            st.session_state["phase"] = "done"  # 第 2 步完成
            st.rerun()

# 处理图片上传（本地 OCR 预处理，再交给 Agent 审核）
if uploaded_img is not None:
    img_key = f"img_{uploaded_img.name}_{uploaded_img.size}"
    if img_key not in st.session_state:
        import base64

        img_b64 = base64.b64encode(uploaded_img.getvalue()).decode("utf-8")
        with st.spinner("识别图片文字…"):
            from agent.tools import ocr_image
            import json as _json

            ocr_result = _json.loads(ocr_image(img_b64))
            if ocr_result.get("status") == "success" and ocr_result.get("text"):
                ocr_text = ocr_result["text"]
                prompt_text = (
                    f"📷 用户上传了一张图片，OCR 识别出以下文字内容：\n\n"
                    f"---\n{ocr_text}\n---\n\n"
                    f"请从以上文字中找出所有地址信息，并逐一按照审核标准进行验证。"
                    f"如同普通地址一样调用 geocode 和 web_search 工具。"
                )
                # 由模型先做《数据质量预审报告》，指出缺失信息并追问用户补充
                preview = agent.assess_ocr_quality(ocr_text, uploaded_img.name)
            else:
                prompt_text = (
                    f"📷 用户上传了一张图片（{uploaded_img.name}），"
                    f"但 OCR 未能识别出文字。"
                    f"错误信息：{ocr_result.get('message', '未知')}"
                    f"\n请告知用户 OCR 识别失败，建议手动输入地址。"
                )
                preview = prompt_text
            st.session_state[img_key] = True
            st.session_state.messages.append(
                {"role": "user", "content": f"📷 上传图片：{uploaded_img.name}"}
            )
            # 第 1 步 · 数据预审报告：图片地址 OCR 文字质量预审气泡
            st.session_state.messages.append(
                {"role": "assistant", "content": f"📋 **第 1 步 · 数据质量预审报告（图片 OCR）**\n\n{preview}", "type": "preview"}
            )
            # 仅当 OCR 成功识别出文字时才进入「待确认」状态（工程化预审拦截）
            if ocr_result.get("status") == "success" and ocr_result.get("text"):
                st.session_state["pending_img_prompt"] = prompt_text
            st.session_state["phase"] = "precheck"
            st.rerun()

# 图片预审确认：用户确认信息完整后才真正调工具审核（工程化约束，仅针对截图 OCR 上传）
if st.session_state.get("pending_img_prompt"):
    _supp = st.session_state.get("pending_supplement", "")
    if _supp:
        st.info(f"📝 已记录补充信息：{_supp}")
    c_confirm, c_cancel = st.columns([0.8, 0.2])
    with c_confirm:
        if st.button("▶ 开始审核图片地址", key="btn_confirm_img", use_container_width=True):
            with st.status("逐条核验中…", expanded=True) as live_status:
                _prog = live_status.empty()
                agent.progress_callback = lambda log: _render_live_progress(_prog, log)
                _base = st.session_state["pending_img_prompt"]
                _supp_text = st.session_state.get("pending_supplement", "")
                _full = (f"【用户补充信息】：\n{_supp_text}\n\n" + _base) if _supp_text else _base
                response = agent.chat(_full)
                agent.progress_callback = None
                live_status.update(label="审核完成 ✅", state="complete", expanded=False)
            _has_table = "|---" in response or any(
                "|" in l and "---" in l for l in response.split("\n")[:5]
            )
            _has_verdict = any(
                v in response for v in ("有效地址", "无效地址", "不确定", "不符合地址格式")
            )
            _is_audit_img = _has_table and _has_verdict
            st.session_state.messages.append({
                "role": "assistant",
                "content": response,
                "type": "audit_report" if _is_audit_img else "preview",
            })
            st.session_state["pending_img_prompt"] = None
            st.session_state["pending_supplement"] = ""
            st.session_state["phase"] = "done"
            st.rerun()
    with c_cancel:
        if st.button("✕ 取消", key="btn_cancel_img", use_container_width=True):
            st.session_state["pending_img_prompt"] = None
            st.session_state["pending_supplement"] = ""
            st.session_state["phase"] = "idle"
            st.rerun()

# 处理文字输入
if prompt:
    # 处于批量上传预审阶段：输入框用于「补充信息 / 确认」，不触发独立审核
    if st.session_state.get("pending_audit_file") or st.session_state.get("pending_img_prompt"):
        st.session_state.setdefault("pending_supplement", "")
        st.session_state["pending_supplement"] = (
            st.session_state["pending_supplement"] + "\n" + prompt
            if st.session_state["pending_supplement"] else prompt
        )
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({
            "role": "assistant",
            "content": "✅ 已记录补充信息。确认底层信息完整无误后，请点击「开始审核」按钮开始正式审核。",
        })
        st.rerun()
    # 普通对话输入：直接审核（无需预审）；同时清除未确认的批量待办
    st.session_state["pending_audit_file"] = None
    st.session_state["pending_img_prompt"] = None
    st.session_state["pending_supplement"] = ""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar=_AVATAR):
        with st.status("审核中…", expanded=True) as live_status:
            # 实时进度：agent 每完成一步（理解/调用工具/验证）都会回调刷新这里
            _prog = live_status.empty()
            agent.progress_callback = lambda log: _render_live_progress(_prog, log)
            response = agent.chat(prompt)
            agent.progress_callback = None
            has_table = any("|" in l and "---" in l for l in response.split("\n")[:5]) or "|---" in response
            has_verdict = any(v in response for v in ("有效地址","无效地址","不确定","不符合地址格式"))
            is_audit = has_table and has_verdict
            live_status.update(label="审核完成 ✅" if is_audit else "完成", state="complete", expanded=False)

        # 渲染审核结果（摘要 + 内联明细 + 下载按钮，文件按内容哈希幂等写入）
        if is_audit:
            render_audit_result(response, uid="inline")
            st.session_state["phase"] = "done"  # 对话框直接审核也产出最终报告
        else:
            st.markdown(render_message(response))
    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "type": "audit_report" if is_audit else "preview",
    })
    st.rerun()

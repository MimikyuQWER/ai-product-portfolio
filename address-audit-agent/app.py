"""
地址审核 Agent — Streamlit 前端
运行方式：streamlit run app.py
"""
import re, io, pathlib, time as _t
from pathlib import Path
import pandas as pd
import streamlit as st
from agent import AddressAuditAgent

# 头像路径（相对于本文件所在目录）
_AVATAR = str(Path(__file__).resolve().parent / "robot-avatar.png")

# URL 匹配
_URL_RE = re.compile(r"(https?://[^\s\)\]）\]>，。；;\"]+)")


def _is_table_separator(line: str) -> bool:
    """检测 Markdown 表格分隔行 |---|---|"""
    return bool(re.match(r"^\|[\s\-:]+\|[\s\-:]+", line))

def render_message(text: str) -> str:
    """将文本中的 URL 转为可点击的 Markdown 链接，<br> 转为真实换行"""
    # <br> → 真实换行（Streamlit markdown 表格内不支持 <br> 标签）
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    def _link(m: re.Match) -> str:
        url = m.group(1)
        return f"[🔗 {url}]({url})"
    return _URL_RE.sub(_link, text)

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

    /* ---- 审核结果表格列宽 ---- */
    .stChatMessage table { table-layout:fixed; width:100%; border-collapse:collapse; word-break:break-word; }
    .stChatMessage table th:nth-child(1) { width:5%; }
    .stChatMessage table td:nth-child(1) { width:5%; text-align:center; }
    .stChatMessage table th:nth-child(2) { width:22%; }
    .stChatMessage table td:nth-child(2) { width:22%; }
    .stChatMessage table th:nth-child(3) { width:9%; }
    .stChatMessage table td:nth-child(3) { width:9%; text-align:center; font-weight:600; white-space:nowrap; }
    .stChatMessage table th:nth-child(4) { width:64%; }
    .stChatMessage table td:nth-child(4) { width:64%; line-height:1.6; font-size:0.78rem; overflow-wrap:break-word; word-break:break-word; }
    .stChatMessage table th { font-size:0.72rem; padding:0.3rem 0.35rem; white-space:nowrap; }
    .stChatMessage table td { padding:0.35rem; vertical-align:top; }
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

    st.divider()
    if st.button("🔄 新会话", use_container_width=True):
        keys_to_clear = [k for k in st.session_state if k.startswith("uploaded_")]
        for k in keys_to_clear:
            del st.session_state[k]
        st.session_state.agent = AddressAuditAgent()
        st.session_state.messages = []
        st.session_state.agent_initialized = False
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
    except ValueError as e:
        st.error(f"❌ {e}")
        st.info("复制 `.env.example` 为 `.env` 并填入 LLM_API_KEY 和 AMAP_API_KEY")
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
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar=_AVATAR):
            content = msg["content"]
            # 审核报告不裸渲表格，统一用摘要+面板
            table_lines = [l for l in content.split("\n") if l.strip().startswith("|") and not _is_table_separator(l.strip())]
            has_table = any("|" in l and "---" in l for l in content.split("\n")[:5]) or "|---" in content
            has_verdict = any(v in content for v in ("有效地址","无效地址","不确定","不符合地址格式"))
            # 确认有实际数据行（序号列为数字），排除开场白中提及关键词的情况
            data_rows = [l for l in table_lines if l.strip().startswith("|") and len([p for p in l.split("|") if p.strip()]) >= 4]
            has_data = len(data_rows) >= 1
            if (has_table and has_verdict and has_data) or len(table_lines) >= 3:
                count_valid = content.count("有效地址")
                count_invalid = content.count("无效地址")
                count_uncertain = content.count("不确定")
                count_bad = content.count("不符合地址格式")
                st.markdown(f"✅ {count_valid} 有效  ⚠️ {count_uncertain} 不确定  ❌ {count_invalid} 无效  🚫 {count_bad} 不符合格式")
                # 写文件 + 链接
                out_dir = pathlib.Path("audit_output")
                out_dir.mkdir(exist_ok=True)
                ts = _t.strftime("%Y%m%d_%H%M%S")
                md_path = out_dir / f"audit_{ts}.md"
                md_path.write_text(content, encoding="utf-8")
                static_base = "http://localhost:8501"
                st.markdown(f"[📄 查看审核明细]({static_base}/audit_output/{md_path.name})（新标签页打开）  ·  [📥 下载 CSV]({static_base}/audit_output/{md_path.name.replace('.md','.csv')})")
                # CSV
                rows_data = []
                header_skipped = False
                for line in content.split("\n"):
                    s = line.strip()
                    if not s.startswith("|") or _is_table_separator(s): continue
                    parts = [p.strip() for p in s.split("|") if p.strip()]
                    if not header_skipped and len(parts) >= 4 and "序号" in parts[0] and "地址" in parts[1]:
                        header_skipped = True; continue
                    if len(parts) >= 4:
                        rows_data.append({"序号": parts[0], "地址": parts[1], "审核结果": parts[2], "审核依据": parts[3]})
                if rows_data:
                    pd.DataFrame(rows_data).to_csv(out_dir / md_path.name.replace(".md", ".csv"), index=False, encoding="utf-8-sig")
            else:
                st.markdown(render_message(content))

# ================================================================
# 审核报告摘要面板（仅在包含审核结果表格的消息后展示）
# ================================================================
if st.session_state.messages:
    last_assistant = None
    for m in reversed(st.session_state.messages):
        if m["role"] == "assistant" and m["content"]:
            last_assistant = m["content"]
            break
    # 只有包含表格分隔行 |---| 的消息才可能是审核报告
    if last_assistant and "|---" in last_assistant:
        count_valid = last_assistant.count("有效地址")
        count_invalid = last_assistant.count("无效地址")
        count_uncertain = last_assistant.count("不确定")
        count_bad = last_assistant.count("不符合地址格式")
        total = count_valid + count_invalid + count_uncertain + count_bad
        if total > 0:
            with st.expander(f"📊 审核报告摘要（共 {total} 条）", expanded=False):
                st.markdown(
                    f"""
                <div class="stat-row">
                    <div class="stat-card valid"><span class="stat-label">✅ 有效</span><span class="stat-value">{count_valid}</span></div>
                    <div class="stat-card uncertain"><span class="stat-label">⚠️ 不确定</span><span class="stat-value">{count_uncertain}</span></div>
                    <div class="stat-card invalid"><span class="stat-label">❌ 无效</span><span class="stat-value">{count_invalid}</span></div>
                    <div class="stat-card badfmt"><span class="stat-label">🚫 不符合</span><span class="stat-value">{count_bad}</span></div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

# ================================================================
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
            "📁 上传表格", type=["xlsx", "xls", "csv"],
            key="file_popover", label_visibility="collapsed",
        )
        uploaded_img = st.file_uploader(
            "🖼️ 上传图片", type=["png", "jpg", "jpeg"],
            key="img_popover", label_visibility="collapsed",
        )

prompt = st.chat_input("输入地址开始审核…")

# 处理表格上传（Excel / CSV）
if uploaded_file is not None:
    file_key = f"file_{uploaded_file.name}_{uploaded_file.size}"
    if file_key not in st.session_state:
        with st.spinner(f"解析 {uploaded_file.name}…"):
            try:
                result = agent.process_excel(uploaded_file.getvalue(), uploaded_file.name)
            except Exception as e:
                st.error(f"处理出错：{e}")
                agent.reset()
                st.stop()
        st.session_state[file_key] = True
        emoji = "📷" if uploaded_file.name.endswith((".png", ".jpg", ".jpeg")) else "📁"
        st.session_state.messages.append(
            {"role": "user", "content": f"{emoji} 上传文件：{uploaded_file.name}"}
        )
        st.session_state.messages.append({"role": "assistant", "content": result})
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
            else:
                prompt_text = (
                    f"📷 用户上传了一张图片（{uploaded_img.name}），"
                    f"但 OCR 未能识别出文字。"
                    f"错误信息：{ocr_result.get('message', '未知')}"
                    f"\n请告知用户 OCR 识别失败，建议手动输入地址。"
                )
            response = agent.chat(prompt_text)
        st.session_state[img_key] = True
        st.session_state.messages.append(
            {"role": "user", "content": f"📷 上传图片：{uploaded_img.name}"}
        )
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

# 处理文字输入
_STEP_ICONS = {"done":"✅","running":"🔄","error":"❌","skipped":"⊘","warn":"⚠️"}

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar=_AVATAR):
        with st.status("审核中…", expanded=True) as live_status:
            response = agent.chat(prompt)
            for entry in agent.step_log:
                st.caption(f"{_STEP_ICONS.get(entry.get('status',''),'·')} {entry['text']}")
            has_table = any("|" in l and "---" in l for l in response.split("\n")[:5]) or "|---" in response
            has_verdict = any(v in response for v in ("有效地址","无效地址","不确定","不符合地址格式"))
            is_audit = has_table and has_verdict
            live_status.update(label="审核完成 ✅" if is_audit else "完成", state="complete", expanded=False)

        # 兜底：回复里有多行带 | 的文本且有实际数据行（序号列为数字），统一用摘要+详情面板
        table_lines = [l for l in response.split("\n") if l.strip().startswith("|") and "---" not in l]
        data_rows = [l for l in table_lines if len([p for p in l.split("|") if p.strip()]) >= 4]
        if (is_audit and len(data_rows) >= 1) or len(table_lines) >= 3:
            # 解析审核表格为 DataFrame
            rows_data = []
            header_skipped = False
            for line in response.split("\n"):
                s = line.strip()
                if not s.startswith("|") or _is_table_separator(s):
                    continue
                parts = [p.strip() for p in s.split("|") if p.strip()]
                # 跳过表头行（第一个包含 序号+地址+审核结果 的行）
                if not header_skipped and len(parts) >= 4 and "序号" in parts[0] and "地址" in parts[1]:
                    header_skipped = True
                    continue
                if len(parts) >= 4:
                    rows_data.append({"序号": parts[0], "地址": parts[1], "审核结果": parts[2], "审核依据": parts[3]})

            count_valid = response.count("有效地址")
            count_invalid = response.count("无效地址")
            count_uncertain = response.count("不确定")
            count_bad = response.count("不符合地址格式")

            # 摘要行
            st.markdown(f"✅ {count_valid} 有效  ⚠️ {count_uncertain} 不确定  ❌ {count_invalid} 无效  🚫 {count_bad} 不符合格式")

            # 写审核明细到独立文件
            out_dir = pathlib.Path("audit_output")
            out_dir.mkdir(exist_ok=True)
            ts = _t.strftime("%Y%m%d_%H%M%S")
            md_path = out_dir / f"audit_{ts}.md"
            md_path.write_text(response, encoding="utf-8")

            csv_path = out_dir / f"audit_{ts}.csv"
            if rows_data:
                pd.DataFrame(rows_data).to_csv(csv_path, index=False, encoding="utf-8-sig")

            # 查看详情链接（依赖 python -m http.server 8501 提供静态文件服务）
            static_base = "http://localhost:8501"
            detail_url = f"{static_base}/audit_output/{md_path.name}"
            csv_url = f"{static_base}/audit_output/{csv_path.name}" if rows_data else None

            c1, c2 = st.columns([0.6, 0.4])
            with c1:
                st.markdown(f"[📄 查看审核明细]({detail_url})（新标签页打开）")
            with c2:
                if csv_url:
                    st.markdown(f"[📥 下载 CSV]({csv_url})")
        else:
            st.markdown(render_message(response))
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

"""
地址审核 Agent 主类
实现 ReAct 模式：LLM 思考 → 调用工具 → 观察结果 → 输出结论
"""

import json
import re
from pathlib import Path
from .llm import LLMService, LLMCallError
from .tools import TOOL_DEFINITIONS, execute_tool
from .guard import ResultGuard


def _looks_like_audit_table(text: str) -> bool:
    """判定文本是否含审核结果表格（兼容 |---| / | --- | / |:---:| 等多种分隔行写法）。

    旧实现用固定子串 "|---" 判定，模型输出带空格的分隔行时护栏整体静默跳过（🟠-10）。
    """
    return any(re.match(r"^\s*\|[\s\-:|]+\|\s*$", line) for line in text.split("\n"))

# prompt.txt 的路径（相对于项目根目录）
_PROMPT_PATH = Path(__file__).parent.parent / "prompt.txt"


class AddressAuditAgent:
    """地址审核 Agent

    用法：
        agent = AddressAuditAgent()
        print(agent.start())             # 开场白
        result = agent.chat("请验证 北京市海淀区中关村大街1号")
        print(result)

    每次新建 Agent 实例即开启一次新的审核会话。
    """

    def __init__(self):
        self.llm = LLMService()
        self.system_prompt = self._load_prompt()
        self.tools = TOOL_DEFINITIONS
        self.messages: list[dict] = []
        self.step_log: list[dict] = []  # 操作日志，供前端进度展示

        # 初始化消息列表，注入 system prompt
        self.messages.append({"role": "system", "content": self.system_prompt})

        # 待审核文件：上传后先生成「数据预审报告」预览，用户确认后才真正调用工具审核
        self._pending_audit = None

        # 批量三段式审核状态（begin_batch_audit / audit_next_chunk / audit_finalize）
        self._filename = ""
        self._chunks: list[list[dict]] = []
        self._cap_note = ""
        self._supplement = ""
        self._audit_total = 0
        self._result_by_idx: dict[int, dict] = {}
        self._extra_rows: list[dict] = []
        self._audit_idx = 0

        # 结果验证门
        self.guard = ResultGuard(llm_chat_fn=self.llm.chat)

        # 进度回调：前端注册后，审核过程中每次 step_log 变化都会实时推送（签名为 fn(step_log)）
        self.progress_callback = None

    # ================================================================
    # 公开方法
    # ================================================================

    def start(self) -> str:
        """返回 Agent 的开场白"""
        greeting = self._call_llm("（对话刚开始，请向用户问好并介绍你的功能）")
        self.messages.append({"role": "assistant", "content": greeting})
        return greeting

    def chat(self, user_input: str) -> str:
        """处理用户文本输入（对话框地址 / 图片 OCR 后的审核指令），直接审核，不做预审拦截。

        预审拦截仅针对文件 / 截图批量上传场景，由 prepare_excel_audit + confirm_and_audit 工程化约束。
        """
        self.messages.append({"role": "user", "content": user_input})
        return self._run_agent_loop()

    def prepare_excel_audit(self, file_bytes: bytes, filename: str) -> tuple[bool, str]:
        """解析 Excel/CSV 并生成「数据质量预审报告」预览，不调用任何外部工具。

        真正的批量审核在 confirm_and_audit() 中、用户点击「开始审核」后执行
        （工程化预审拦截：未确认不调工具，避免无谓消耗 API）。

        返回 (ok, text)：
        - ok=True  表示已成功进入待审核态（self._pending_audit 已设置），text 为预览内容；
        - ok=False 表示解析失败/无有效记录（self._pending_audit 已清空），text 为错误提示，
          调用方**不应**进入「待确认/审核」态（🔴-1 修复：避免重放上一轮报告）。
        """
        import base64

        file_b64 = base64.b64encode(file_bytes).decode("utf-8")
        from .tools import parse_excel

        parse_result = parse_excel(file_b64)
        parse_data = json.loads(parse_result)

        if parse_data.get("status") == "error":
            self._pending_audit = None  # 关键：失败时清空，避免 begin_batch_audit 复用旧数据
            return False, f"Excel 文件解析失败：{parse_data.get('message')}。请检查文件格式。"

        records = parse_data.get("records", [])
        total = parse_data.get("total", 0)

        # 零记录保护：防止 LLM 收到矛盾指令后编造数据
        if total == 0:
            self._pending_audit = None
            return False, (
                f"文件「{filename}」已成功解析，但未找到任何有效的地址记录。\n"
                f"检测到的列名：{parse_data.get('columns', [])}\n"
                f"请确认 Excel 中包含'地址'或'详细地址'列，且列中有有效数据。"
            )

        # 保存待审核数据，等待用户确认（工程化约束：未确认不调工具）
        self._pending_audit = {"filename": filename, "records": records, "total": total}
        # 由模型先做【数据质量预审】：评估每条地址完整度、指出缺失信息、追问用户补充
        # 🟠-15：预审阶段也限制喂给模型的记录数（避免大文件一次性灌爆上下文/巨额 token）
        PREVIEW_CAP = 50
        sample = records[:PREVIEW_CAP]
        note = "" if total <= PREVIEW_CAP else (
            f"\n\n（仅抽样前 {PREVIEW_CAP} 条做质量预审，共 {total} 条，正式审核将处理全部）"
        )
        return True, self._build_quality_report(sample, len(sample), filename) + note

    def _build_preview(self, filename: str, records: list, total: int) -> str:
        """构造数据预审预览文本（仅展示将要审核的地址，不调用工具）"""
        lines = [f"📋 文件「{filename}」已解析，共 **{total}** 条地址。预览前 12 条：", ""]
        for i, r in enumerate(records[:12], start=1):
            lines.append(f"{i}. {r.get('address', '')}")
        if total > 12:
            lines.append(f"…（其余 {total - 12} 条略）")
        lines.append("")
        lines.append("请点击 **「▶ 开始审核」** 按钮确认，确认后我将调用高德地图 + 联网搜索逐条核验并生成报告。")
        return "\n".join(lines)

    def _build_quality_report(self, records: list, total: int, filename: str) -> str:
        """调用模型对地址数据做【数据质量与完整度】预审（仅文本理解，不调外部核验工具）。

        输出《数据质量预审报告》：整体质量概览、逐条缺失信息、是否存在 OCR/识别遗漏，
        并追问用户补充「应该有但实际没有」的信息；待用户确认完整后才进入正式审核。
        """
        qa_prompt = (
            f"用户上传了文件「{filename}」，共解析出 {total} 条地址。请作为【数据质量审核员】，"
            f"仅基于地址**文本本身**评估每条地址的【完整度与质量】，"
            f"不要判断地址真假、不要调用任何工具。\n\n"
            f"完整度标准（6 级）：0国家、1省、2市、3区/县、4镇/乡/街道、"
            f"5村庄/门牌号或街道门牌号、6房间号。\n\n"
            f"请输出一份简洁的《数据质量预审报告》，包含：\n"
            f"1. 整体质量概览：完整 / 部分缺失 / 严重缺失 的条数占比；\n"
            f"2. 逐条列出【信息不全】的地址（缺失省/市/区/街道/门牌号等），"
            f"并说明你认为「应该有但实际没有」的信息；\n"
            f"3. 指出是否可能存在 OCR/识别遗漏（如明显截断、乱码、字段错位）；\n"
            f"4. 最后请用户【补充缺失信息】，或确认信息已完整无误；"
            f"待用户确认后才会开始正式审核。\n\n"
            f"地址数据：\n```json\n{json.dumps(records, ensure_ascii=False, indent=2)}\n```"
        )
        try:
            return self._call_llm(qa_prompt)
        except Exception as e:
            # 模型调用异常时降级为机械预览，保证流程不中断
            return (
                self._build_preview(filename, records, total)
                + f"\n\n（提示：数据质量智能评估暂不可用：{e}；你仍可点击「开始审核」直接审核。）"
            )

    def assess_ocr_quality(self, ocr_text: str, filename: str) -> str:
        """对 OCR 识别出的文字做【数据质量预审】（仅文本理解，不调外部核验工具），追问缺失信息。"""
        qa_prompt = (
            f"用户上传了一张图片（{filename}），OCR 识别出如下文字：\n\n"
            f"---\n{ocr_text}\n---\n\n"
            f"请作为【数据质量审核员】，仅基于以上文字评估其中地址信息的【完整度与质量】，"
            f"不要判断地址真假、不要调用任何工具。\n\n"
            f"请输出一份简洁的《图片数据质量预审报告》，包含：\n"
            f"1. 从中能提取出几条地址、整体质量如何；\n"
            f"2. 哪些地址信息不全（缺省/市/区/街道/门牌号等），说明「应该有但实际没有」的信息；\n"
            f"3. 是否可能存在 OCR 遗漏/误识（如乱码、截断、字段错位）；\n"
            f"4. 请用户补充缺失信息或确认信息完整；确认后才会开始正式审核。\n"
        )
        try:
            return self._call_llm(qa_prompt)
        except Exception as e:
            return (
                f"📷 图片 OCR 识别到以下文字，将从中提取地址审核：\n\n{ocr_text}\n\n"
                f"点击「▶ 开始审核图片地址」确认后开始。（数据质量智能评估暂不可用：{e}）"
            )

    def confirm_and_audit(self, supplement: str = "") -> str:
        """用户确认后，对 prepare_excel_audit 解析出的地址执行真正的批量审核（一次性阻塞调用）。

        对外 API 与旧版兼容（tests 仍直接调用本方法）。
        前端 app.py 则改用 begin_batch_audit / audit_next_chunk / audit_finalize 三段式，
        以分块逐批 rerun 显示进度、避免单次阻塞卡死，并在每批前裁剪上下文提速（见 Issue #3）。
        """
        self.begin_batch_audit(supplement)
        while self.audit_next_chunk():
            pass
        return self.audit_finalize()

    def _clear_batch_state(self) -> None:
        """清空批量审核的临时状态（防止上一轮残留导致重放/串文件，🔴-1 修复核心）。"""
        self._filename = ""
        self._chunks = []
        self._cap_note = ""
        self._supplement = ""
        self._audit_total = 0
        self._result_by_idx = {}
        self._extra_rows = []
        self._audit_idx = 0

    def begin_batch_audit(self, supplement: str = "") -> dict:
        """初始化批量审核状态：解析待审数据、分块、注入补充信息。返回 {total, chunks, ok}。

        ok=False 表示没有待审核文件（通常因预审失败），调用方不应进入「待确认/审核」态。
        """
        if not self._pending_audit:
            self._clear_batch_state()  # 关键：不再复用上一轮的 _chunks/_result_by_idx 等
            return {"total": 0, "chunks": 0, "ok": False}
        pending = self._pending_audit
        self._pending_audit = None
        records = pending["records"]
        total = pending["total"]
        filename = pending["filename"]

        # 安全上限：超长文件只处理前 N 条并提示，避免无上限烧 API
        safe_cap = 100
        cap_note = ""
        if total > safe_cap:
            records = records[:safe_cap]
            cap_note = (
                f"\n\n⚠️ 文件共 {total} 条，已超过单次安全上限 {safe_cap} 条，"
                f"本次仅审核前 {safe_cap} 条，其余请在新会话中处理。"
            )

        # 为每条记录标注原始序号（文件顺序 1..N）与姓名，供模型回显、供合并时按文件顺序对齐
        indexed = [
            {
                "idx": i + 1,
                "name": (r.get("name", "") or "未知"),
                "address": r.get("address", ""),
            }
            for i, r in enumerate(records)
        ]

        # 批量分块处理：每批 5 条，所有数据均处理（不再硬截断丢数据）
        chunk_size = 5
        chunks = [indexed[i : i + chunk_size] for i in range(0, len(indexed), chunk_size)]

        # 保存状态供 audit_next_chunk / audit_finalize 使用
        self._filename = filename
        self._chunks = chunks
        self._cap_note = cap_note
        self._supplement = supplement.strip() if supplement and supplement.strip() else ""
        self._audit_total = total
        self._result_by_idx: dict[int, dict] = {}
        self._extra_rows: list[dict] = []
        self._audit_idx = 0
        return {"total": total, "chunks": len(chunks), "ok": True}

    def audit_next_chunk(self) -> bool:
        """处理下一批地址（含一次完整 ReAct 循环）。

        返回 True 表示还有更多批次需处理，False 表示全部完成。
        每批前仅保留 system + 补充信息 + 本批上下文，避免历史批次无限累积拖慢逐批速度（Issue #3）。
        """
        if self._audit_idx >= len(self._chunks):
            return False
        chunk = self._chunks[self._audit_idx]
        chunk_num = self._audit_idx + 1
        total_chunks = len(self._chunks)

        # 重建上下文：只保留 system + 补充信息 + 本批，提速且隔离批次间互相干扰
        base: list[dict] = [{"role": "system", "content": self.system_prompt}]
        if self._supplement:
            base.append({
                "role": "user",
                "content": f"【用户在预审阶段补充的信息，正式审核时请一并参考】：\n{self._supplement}",
            })

        chunk_ctx = (
            f"用户上传了文件「{self._filename}」，正在逐批审核（共 {total_chunks} 批）。\n"
            f"以下是第 {chunk_num}/{total_chunks} 批，共 {len(chunk)} 条地址，请只审核本批：\n"
            f"```json\n{json.dumps(chunk, ensure_ascii=False, indent=2)}\n```\n\n"
            f"请优先使用 geocode 工具验证本批每条地址（精确命中可不再调 web_search）。\n"
            f"**降级规则**：若某条地址 geocode 重试 3 次仍返回技术性失败（status=error），"
            f"必须改用 web_search 降级交叉验证；若 web_search 也无可靠结果，则该条结论判「审核失败」"
            f"并在「审核依据」写明①地图 API 失败原因 ②已尝试联网搜索但无结果 ③下一步建议（换 Key/稍后重试/转人工）。"
            f"「审核失败」≠「不确定」，后者是地址本身信息不足、已核验但证据不够。\n"
            f"输出**六列表格**，列顺序固定为：序号 | 姓名 | 地址 | 审核结果 | 审核依据 | 审核信息源。\n"
            f"严格要求：\n"
            f"1. 「序号」列必须填我上面 JSON 里给出的 idx（即文件原始行号 1..N），不要重排、不要从 1 开始；\n"
            f"2. 「姓名」列必须填我给出的 name；\n"
            f"3. 仅输出本批的六列表格，不要输出其他批次。\n"
            f"4. 「审核信息源」列【必须】包含可点击链接，且链接须直接来自工具实际返回字段，不得编造：\n"
            f"   - 凡经 geocode 精确命中（工具返回 marker_url / map_url），必须在该列给出对应高德链接"
            f"（优先 marker_url 精确定位，缺则 map_url 搜索链接）；\n"
            f"   - 凡调用了 web_search 且有结果，必须在该列附上来源网页 URL；\n"
            f"   - 链接放在「审核信息源」列即可，审核依据列只写文字分析、不放链接。\n"
            f"若某条地址信息不足导致无法定位唯一地点，直接判定为'不确定'，不要向用户追问（批量模式下无法交互）。"
            f"注意：此'不确定'指地址本身证据不足；若 geocode 与 web_search 均因技术故障失败，则应判'审核失败'而非'不确定'。"
            f"{self._cap_note if chunk_num == total_chunks else ''}"
        )
        self.messages = base + [{"role": "user", "content": chunk_ctx}]
        chunk_out = self._run_agent_loop()
        self._match_chunk(chunk, self._extract_table_rows(chunk_out), self._result_by_idx, self._extra_rows)
        self._audit_idx += 1
        return self._audit_idx < len(self._chunks)

    def audit_finalize(self) -> str:
        """汇总所有批次结果，按文件顺序构建六列合并表并返回（带「共审核 X/Y 条」尾注）。"""
        indexed: list[dict] = []
        for c in self._chunks:
            indexed.extend(c)
        total = self._audit_total

        # 按文件顺序汇总：文件里每条记录都对应一行（模型漏输出则补「不确定」），保证计数=文件行数
        all_rows: list[dict] = []
        for rec in indexed:
            i = rec["idx"]
            r = self._result_by_idx.get(i)
            if r is not None:
                all_rows.append({
                    "序号": str(i),
                    "姓名": rec["name"],       # 姓名以文件为准（权威），不依赖模型回显
                    "地址": rec["address"],     # 地址以文件为准，保证完整可见
                    "审核结果": r.get("审核结果", ""),
                    "审核依据": r.get("审核依据", ""),
                    "审核信息源": r.get("审核信息源", ""),
                })
            else:
                all_rows.append({
                    "序号": str(i),
                    "姓名": rec["name"],
                    "地址": rec["address"],
                    "审核结果": "不确定",
                    "审核依据": "（该条地址模型未返回审核结果，可能核验中断，建议重试本文件）",
                    "审核信息源": "",
                })
        # 兜底：模型返回了无法对应到文件的行，追加在末尾（极少见）
        for r in self._extra_rows:
            all_rows.append({
                "序号": r.get("序号", ""), "姓名": r.get("姓名", "未知"),
                "地址": r.get("地址", ""), "审核结果": r.get("审核结果", ""),
                "审核依据": r.get("审核依据", ""), "审核信息源": r.get("审核信息源", ""),
            })

        if not all_rows:
            # 重置 LLM 上下文与批量状态，避免后续交互继承半成品
            self.messages = [{"role": "system", "content": self.system_prompt}]
            self._clear_batch_state()
            return f"文件「{self._filename}」已解析出 {total} 条地址，但未能生成有效的审核表格，请重试。"

        merged = self._build_merged_table(all_rows)
        matched_count = len(indexed)
        # 🟡-19：计数严格基于源文件行数；无法对应到源文件的额外行单列说明，避免 "共审核 3/2"
        extra_note = f"；另有 {len(self._extra_rows)} 行无法对应到源文件，已附在末尾" if self._extra_rows else ""
        tail = f"\n\n（共审核 {matched_count} / {total} 条地址{extra_note}）{self._cap_note}"
        merged_full = merged + tail

        # 🟠-16：清空上下文但保留一条精简摘要，避免用户紧接着追问时模型零上下文
        self.messages = [{"role": "system", "content": self.system_prompt}]
        summary = (
            f"（已完成文件「{self._filename}」{matched_count}/{total} 条地址的批量审核。"
            f"结论摘要："
            + "；".join(
                f"{r['序号']}.{r['地址'][:12]}→{r['审核结果']}"
                for r in all_rows[:50]
            )
            + "。用户可基于以上结论追问具体某条地址的判定依据。）"
        )
        self.messages.append({"role": "assistant", "content": summary})
        self._clear_batch_state()
        return merged_full

    # ---- 批量处理辅助：表格行提取与合并 ----

    @staticmethod
    def _extract_table_rows(text: str) -> list[dict]:
        """从 LLM 的表格输出中提取数据行（跳过表头与分隔行）。

        兼容两种列数：
        - 六列（文件批量审核）：序号 | 姓名 | 地址 | 审核结果 | 审核依据 | 审核信息源
        - 五列（对话框单条审核）：序号 | 地址 | 审核结果 | 审核依据 | 审核信息源（无姓名列）
        - 四列（旧格式兜底）：序号 | 地址 | 审核结果 | 审核依据
        始终返回含全部 6 个键的 dict（缺列填空）。

        健壮性（修复评审 🟠-5/6/7）：
        - 切分表格单元格时**保留中间空单元格**（仅去除 Markdown 表格首尾边框空串），
          避免「姓名/信息源留空」导致整行列错位（地址被当结果）。
        - 表头判定用子串（兼容「**姓名**」加粗、带前缀列名）。
        - 模型省略表头时，按首个数据行的列数推断 ncols，而非回落到 4 列兜底。
        """
        raw: list[list[str]] = []
        ncols = 0
        for line in text.split("\n"):
            s = line.strip()
            if not s.startswith("|"):
                continue
            if re.match(r"^\|[\s\-:]+\|", s):  # 分隔行 |---|---|
                continue
            cells = s.split("|")
            # 去掉 Markdown 表格边框产生的首尾空串，但保留中间空单元格
            if cells and not cells[0].strip():
                cells = cells[1:]
            if cells and not cells[-1].strip():
                cells = cells[:-1]
            parts = [c.strip() for c in cells]
            if len(parts) < 4:
                continue
            if ncols == 0:
                # 表头行：首格为「序号」且含「地址」或「姓名」
                if "序号" in parts[0] and any("地址" in p or "姓名" in p for p in parts):
                    ncols = len(parts)
                    continue
                # 否则视为数据行（无表头场景），先收集
                raw.append(parts)
            else:
                raw.append(parts)
        # 无表头：以首个数据行的列数作为判定基准（🟠-6）
        if ncols == 0 and raw:
            ncols = len(raw[0])

        rows: list[dict] = []
        for parts in raw:
            if len(parts) < 4:
                continue
            is_six = ncols >= 6 or (ncols == 0 and len(parts) >= 6)
            is_five = (ncols == 5) or (ncols == 0 and len(parts) == 5)
            if is_six:
                rows.append({
                    "序号": parts[0],
                    "姓名": parts[1] if len(parts) > 1 else "",
                    "地址": parts[2] if len(parts) > 2 else "",
                    "审核结果": parts[3] if len(parts) > 3 else "",
                    "审核依据": " | ".join(parts[4:-1]) if len(parts) > 5 else (parts[4] if len(parts) > 4 else ""),
                    "审核信息源": parts[-1] if len(parts) > 5 else "",
                })
            elif is_five:
                rows.append({
                    "序号": parts[0], "姓名": "",
                    "地址": parts[1], "审核结果": parts[2],
                    "审核依据": " | ".join(parts[3:-1]) if len(parts) > 4 else (parts[3] if len(parts) > 3 else ""),
                    "审核信息源": parts[-1] if len(parts) > 4 else "",
                })
            else:  # 4 列兜底
                rows.append({
                    "序号": parts[0], "姓名": "",
                    "地址": parts[1], "审核结果": parts[2],
                    "审核依据": parts[3], "审核信息源": "",
                })
        return rows

    @staticmethod
    def _esc(v: object) -> str:
        """转义：换行→空格，竖线→全角斜杠（防止破坏 Markdown 表格）"""
        return str(v).replace("\n", " ").replace("|", "／")

    @staticmethod
    def _build_merged_table(rows: list[dict]) -> str:
        """将多批数据行合并为单张六列 Markdown 表格，按文件序号顺序"""
        lines = [
            "| 序号 | 姓名 | 地址 | 审核结果 | 审核依据 | 审核信息源 |",
            "|---|---|---|---|---|---|",
        ]
        for r in rows:
            lines.append(
                f"| {AddressAuditAgent._esc(r.get('序号', ''))} "
                f"| {AddressAuditAgent._esc(r.get('姓名', ''))} "
                f"| {AddressAuditAgent._esc(r.get('地址', ''))} "
                f"| {AddressAuditAgent._esc(r.get('审核结果', ''))} "
                f"| {AddressAuditAgent._esc(r.get('审核依据', ''))} "
                f"| {AddressAuditAgent._esc(r.get('审核信息源', ''))} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _match_chunk(chunk: list[dict], rows: list[dict], result_by_idx: dict, extra_rows: list) -> None:
        """把某一批模型返回的表格行，按文件原始序号(idx)映射回 records。

        chunk: 本批 records（含 idx / name / address）
        rows:  self._extract_table_rows(chunk_out) 解析出的六/五列数据行
        result_by_idx: 命中则 result_by_idx[文件序号] = 行（供合并时按文件顺序对齐）
        extra_rows:    无法对应到文件记录的行，追加到末尾（极少见，防丢数据）

        兼容两种编号习惯：模型正确回显文件序号(idx)；或按批从 1 重新编号
        （此时还原为 chunk 内的文件序号）。两者都无法对应才进 extra_rows。
        """
        by_idx = {rec["idx"]: rec for rec in chunk}
        for r in rows:
            raw = str(r.get("序号", "")).strip()
            idx_val = None
            try:
                idx_val = int(raw)
            except (ValueError, TypeError):
                idx_val = None
            target_idx = None
            if idx_val is not None:
                if idx_val in by_idx:
                    target_idx = idx_val              # 模型正确回显文件序号
                elif 1 <= idx_val <= len(chunk):
                    target_idx = chunk[idx_val - 1]["idx"]  # 模型按批从 1 编号 → 还原为文件序号
            if target_idx is not None:
                # 🟠-8：命中后校验地址一致性，防止「串号」把 A 的结论静默挂到 B 的地址上
                rec = by_idx[target_idx]
                a_model = re.sub(r"\s", "", str(r.get("地址", "")))
                a_file = re.sub(r"\s", "", rec["address"])
                if a_model and a_file and a_model[:8] not in a_file and a_file[:8] not in a_model:
                    r = dict(r)
                    r["_mismatch"] = (
                        f"模型回显地址「{r.get('地址', '')}」与文件第 {target_idx} 行「{rec['address']}」不一致，"
                        f"已作为无法对应行处理"
                    )
                    extra_rows.append(r)
                    continue
                result_by_idx[target_idx] = r
            else:
                extra_rows.append(r)

    def _apply_guard(self, final_content: str) -> str:
        """对最终审核报告运行 ResultGuard，返回（可能已修正的）输出；非审核报告原样返回（B8 复用）"""
        is_audit_report = (
            _looks_like_audit_table(final_content)
            and (
                "有效地址" in final_content
                or "无效地址" in final_content
                or "不确定" in final_content
                or "不符合地址格式" in final_content
            )
        )
        if not is_audit_report:
            return final_content
        self.step_log.append({"step": "guard", "status": "running", "text": "结果验证中…"})
        self._emit_progress()
        verified_output, guard_result = self.guard.check_and_retry(
            final_content, list(self.messages)
        )
        if guard_result.passed:
            self.step_log[-1] = {"step": "guard", "status": "done", "text": "结果验证通过 ✓"}
        else:
            self.step_log[-1] = {
                "step": "guard",
                "status": "warn",
                "text": f"验证未完全通过（{len(guard_result.violations)}项违规），已自动修正",
            }
        if guard_result.warnings:
            for w in guard_result.warnings:
                self.step_log.append({"step": "warn", "status": "warn", "text": w})
        self._emit_progress()
        return verified_output

    def reset(self):
        """重置会话"""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.step_log = []
        self._pending_audit = None

    # ================================================================
    # 内部方法
    # ================================================================

    def _load_prompt(self) -> str:
        """加载 prompt.txt"""
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        # 兜底：内置简化版提示词
        return "你是一个地址审核助手，帮助用户验证地址是否真实有效。请使用提供的工具进行验证。"

    def _call_llm(self, user_message: str) -> str:
        """单次调用 LLM（不使用工具），返回文本内容。LLM 调用失败时返回错误提示串（不抛异常），
        由 start/质量预审 等调用方自行决定降级展示（🟠-14 修复）。"""
        temp_messages = self.messages + [{"role": "user", "content": user_message}]
        try:
            response = self.llm.chat(temp_messages, tools=None)
        except LLMCallError as e:
            return f"（AI 服务暂不可用：{e}；请稍后重试，或点击「开始审核」直接审核。）"
        return response.content or ""

    def _emit_progress(self):
        """向前端实时推送当前进度（若已注册 progress_callback）。推送失败不影响审核主流程。"""
        cb = getattr(self, "progress_callback", None)
        if cb:
            try:
                cb([dict(e) for e in self.step_log])
            except Exception:
                pass

    def _run_agent_loop(self) -> str:
        """
        ReAct Agent 循环
        LLM 可以多次调用工具，直到给出最终文本回复
        """
        self.step_log = []  # 每轮审核重置进度日志，避免跨轮累积（B5）

        max_iterations = 10  # 防止死循环
        max_tool_rounds = max_iterations - 1  # 最后一轮留给文字总结

        for iteration in range(max_iterations):
            self.step_log.append({"step": "reasoning", "status": "running", "text": "AI 分析中…"})
            self._emit_progress()
            try:
                response = self.llm.chat(self.messages, tools=self.tools)
            except LLMCallError as e:
                # LLM 调用失败：返回明确错误信息，不把异常抛给前端导致整页崩溃（🟠-14 修复）
                msg = f"⚠️ AI 服务调用失败：{e}。请稍后重试（可点击「新会话」重置）。"
                self.step_log.append({"step": "error", "status": "error", "text": msg})
                self._emit_progress()
                self.messages.append({"role": "assistant", "content": msg})
                return msg
            self.step_log[-1]["status"] = "done"
            self.step_log[-1]["text"] = "文本理解完成" if not response.has_tool_calls else "AI 决定调用工具验证"
            self._emit_progress()

            # 非最后一轮：并行执行所有工具调用
            if response.has_tool_calls and iteration < max_tool_rounds:
                tool_call_blocks = []
                tool_results = []

                # 先记录所有调用并构建 blocks（追踪每条日志的索引位置）
                tool_log_indices: dict[str, int] = {}
                for tool_call in response.tool_calls:
                    tool_name_cn = _tool_display_name(tool_call.name)
                    tool_log_indices[tool_call.id] = len(self.step_log)
                    self.step_log.append(
                        {"step": "tool", "status": "running",
                         "text": f"调用 {tool_name_cn}…",
                         "tool": tool_call.name}
                    )
                    tool_call_blocks.append({
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                        },
                    })
                    self._emit_progress()

                # 并行执行（geocode + web_search 独立，节省 ~1.5s）
                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=4) as pool:
                    futures = {
                        pool.submit(execute_tool, tc.name, tc.arguments): tc
                        for tc in response.tool_calls
                    }
                    results_by_tc = {}
                    for f in as_completed(futures):
                        tc = futures[f]
                        results_by_tc[tc] = f.result()

                # 按原始顺序收集结果并标记日志（用正确的日志索引，不用 [-1]）
                for tool_call in response.tool_calls:
                    result = results_by_tc[tool_call]
                    tool_results.append(
                        {"role": "tool", "tool_call_id": tool_call.id, "content": result}
                    )
                    r = _safe_json(result)
                    tool_name_cn = _tool_display_name(tool_call.name)
                    log_idx = tool_log_indices.get(tool_call.id, -1)
                    updated = {"step": "tool", "tool": tool_call.name}
                    if r.get("status") == "success":
                        updated.update({"status": "done", "text": f"{tool_name_cn} ✓"})
                    elif r.get("status") == "skipped":
                        updated.update({"status": "skipped", "text": f"{tool_name_cn} ⊘ {r.get('message', '已跳过')}"})
                    else:
                        updated.update({"status": "error", "text": f"{tool_name_cn} ✗ {r.get('message', '未知错误')}"})
                    if 0 <= log_idx < len(self.step_log):
                        self.step_log[log_idx] = updated
                self._emit_progress()

                assistant_msg = {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": tool_call_blocks,
                }
                self.messages.append(assistant_msg)
                for tr in tool_results:
                    self.messages.append(tr)
                continue

            # 最后一轮仍有工具调用 → 注入停止指令 + 最后一次 LLM 调用
            if response.has_tool_calls:
                self.messages.append(
                    {
                        "role": "user",
                        "content": "已达到处理上限。请基于以上所有验证结果，直接输出最终的审核报告，不要再调用工具。",
                    }
                )
                try:
                    final_response = self.llm.chat(self.messages, tools=None)
                except LLMCallError as e:
                    msg = f"⚠️ AI 服务调用失败：{e}。请稍后重试（可点击「新会话」重置）。"
                    self.messages.append({"role": "assistant", "content": msg})
                    return msg
                final_content = final_response.content or ""
                # 超时/强制总结的最终报告也过 ResultGuard（B8）
                final_content = self._apply_guard(final_content)
                self.messages.append({"role": "assistant", "content": final_content})
                return final_content

            # 文字回复 → 最终输出
            final_content = response.content or ""

            if response.finish_reason == "length":
                final_content += "\n\n⚠️ 注意：AI 输出因长度限制被截断，审核结果可能不完整，请减少单次提交的地址数量后重试。"

            # ResultGuard：仅在输出包含审核结果时才验证，闲聊消息直接放行
            final_content = self._apply_guard(final_content)
            self.messages.append({"role": "assistant", "content": final_content})
            return final_content

        # 超时：追加终止消息到 history 后再返回
        self.step_log.append({"step": "error", "status": "error",
                              "text": "审核超时（已达最大工具调用次数）。建议：减少单次提交的地址数量，或尝试更简洁的地址描述。"})
        timeout_msg = "审核过程超时，请简化地址信息后重试。"
        self.messages.append({"role": "assistant", "content": timeout_msg})
        return timeout_msg


def _tool_display_name(name: str) -> str:
    """工具名称 → 中文展示名"""
    return {
        "geocode": "高德地图地址核验",
        "web_search": "联网搜索交叉验证",
        "parse_excel": "Excel 文件解析",
        "ocr_image": "图片 OCR 文字识别",
    }.get(name, name)


def _safe_json(text: str) -> dict:
    """安全解析 JSON，失败返回空 dict"""
    import json as _j
    try:
        return _j.loads(text)
    except Exception:
        return {}

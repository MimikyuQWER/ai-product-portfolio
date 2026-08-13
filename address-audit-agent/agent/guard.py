"""
地址审核结果验证层 (ResultGuard)
工程化反幻觉：LLM 输出必须通过硬性规则检查才放行

三层护栏：
  Layer 1 — EvidenceCollector: 从 tool 结果中提取结构化证据
  Layer 2 — ResultGuard:      4 条规则检查 + 重试机制
  Layer 3 — (在 app.py 中):   前端渲染时标注验证状态
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any


# ============================================================
# Layer 1: Evidence Extraction
# ============================================================

# 四类有效审核结果
VALID_VERDICTS = {"有效地址", "无效地址", "不确定", "不符合地址格式", "审核失败"}

# 无需工具证据的审核结果
NO_EVIDENCE_VERDICTS = {"不符合地址格式"}

# URL 匹配正则
URL_PATTERN = re.compile(r"https?://[^\s\)\]）\]>,，。；;]+")


@dataclass
class ToolEvidence:
    """单次工具调用的证据摘要"""

    tool_name: str
    call_id: str
    index: int  # 在 messages 中的位置
    urls: list[str] = field(default_factory=list)
    coordinates: str | None = None
    level: str | None = None
    found: bool | None = None
    raw_result: dict | None = None
    province: str | None = None          # geocode 返回的省（用于 Rule F 行政区划一致性）
    city: str | None = None              # geocode 返回的城市
    search_results: list[dict] = field(default_factory=list)  # web_search 的标题/摘要/链接（用于 Rule E 相关性）

    @property
    def is_valid(self) -> bool:
        """是否是一次成功的工具调用"""
        return self.raw_result is not None and self.raw_result.get("status") == "success"


@dataclass
class GuardResult:
    """验证结果"""

    passed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence: list[ToolEvidence] = field(default_factory=list)
    known_urls: set[str] = field(default_factory=set)

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class EvidenceCollector:
    """从 messages 中提取所有工具调用的结构化证据"""

    def collect(self, messages: list[dict]) -> list[ToolEvidence]:
        evidence_list = []

        for i, msg in enumerate(messages):
            if msg.get("role") != "tool":
                continue

            raw = self._parse_tool_result(msg.get("content", ""))
            if raw is None:
                continue

            call_id = msg.get("tool_call_id", f"unknown_{i}")

            ev = ToolEvidence(
                tool_name=self._infer_tool_name(raw, messages, call_id),
                call_id=call_id,
                index=i,
                urls=self._extract_urls(raw),
                coordinates=raw.get("location"),
                level=raw.get("level"),
                found=raw.get("found"),
                raw_result=raw,
                province=raw.get("province") or None,
                city=raw.get("city") or None,
                search_results=[r for r in (raw.get("results") or []) if isinstance(r, dict)],
            )
            evidence_list.append(ev)

        return evidence_list

    def _parse_tool_result(self, content: str) -> dict | None:
        """解析 tool 返回的 JSON 字符串"""
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

    def _infer_tool_name(
        self, raw: dict, messages: list[dict], call_id: str
    ) -> str:
        """从数据特征推断工具名称"""
        # 从 source 字段直接识别
        source = raw.get("source", "")
        if "高德地图" in source:
            return "geocode"
        if "Bing" in source:
            return "web_search"
        if "pytesseract" in source:
            return "ocr_image"

        # 从字段特征推断
        if "location" in raw or "formatted_address" in raw:
            return "geocode"
        if "results" in raw and isinstance(raw.get("results"), list):
            return "web_search"
        if "records" in raw:
            return "parse_excel"
        if "text" in raw and "OCR" in source:
            return "ocr_image"

        return "unknown"

    def _extract_urls(self, raw: dict) -> list[str]:
        """从工具结果中提取所有 URL

        注意：web_search 的结果在 raw["results"]（列表），而 geocode 的定位链接
        在 raw["map_url"] / raw["marker_url"]（字符串字段，无 results 键）。
        两者都要采集，否则 Rule B 会把真实的地图链接误判为"编造"。
        """
        urls = []
        for item in raw.get("results", []):
            url = item.get("url", "").strip()
            if url:
                urls.append(url)
        for key in ("map_url", "marker_url"):
            u = raw.get(key)
            if isinstance(u, str) and u.strip():
                urls.append(u.strip())
        return urls


# ============================================================
# Layer 2: Rule Checking
# ============================================================


class ResultGuard:
    """LLM 输出验证门：硬性规则检查 + 重试"""

    MAX_RETRIES = 1

    def __init__(self, llm_chat_fn):
        """
        Args:
            llm_chat_fn: LLM 调用函数签名为 (messages, tools=None) -> LLMResponse
        """
        self.collector = EvidenceCollector()
        self._llm_chat = llm_chat_fn

    def check(
        self, llm_output: str, messages: list[dict]
    ) -> GuardResult:
        """
        对 LLM 输出执行所有规则检查。
        返回 GuardResult 包含通过状态、违规项、警告项和证据。
        """
        evidence = self.collector.collect(messages)

        # 收集所有已知 URL
        known_urls: set[str] = set()
        for ev in evidence:
            known_urls.update(ev.urls)

        violations: list[str] = []
        warnings: list[str] = []

        # ---- Rule A: 工具调用最低门槛 ----
        rule_a = self._check_rule_a(llm_output, evidence)
        if rule_a:
            violations.append(rule_a)

        # ---- Rule B: URL 溯源校验 ----
        rule_b_violations, rule_b_warnings = self._check_rule_b(llm_output, known_urls)
        violations.extend(rule_b_violations)
        warnings.extend(rule_b_warnings)

        # ---- Rule C: 审核结论一致性 ----
        rule_c = self._check_rule_c(llm_output, evidence)
        if rule_c:
            violations.append(rule_c)

        # ---- Rule D: 输出格式完整性 ----
        rule_d = self._check_rule_d(llm_output)
        if rule_d:
            violations.append(rule_d)

        # ---- Rule E: 联网搜索结果强相关性（工程化校验，prompt 之外的硬约束）----
        rule_e_v, rule_e_w = self._check_rule_e(llm_output, evidence)
        violations.extend(rule_e_v)
        warnings.extend(rule_e_w)

        # ---- Rule F: 行政区划一致性（地图核验省份 vs 结论提及省份）----
        rule_f_v, rule_f_w = self._check_rule_f(llm_output, evidence)
        violations.extend(rule_f_v)
        warnings.extend(rule_f_w)

        return GuardResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            evidence=evidence,
            known_urls=known_urls,
        )

    def check_and_retry(
        self, llm_output: str, messages: list[dict]
    ) -> tuple[str, GuardResult]:
        """
        检查 LLM 输出，不通过时注入修正指令重试 1 次。
        返回 (最终输出, GuardResult)
        """
        result = self.check(llm_output, messages)

        if result.passed:
            # 有警告但无违规 → 在输出末尾追加提示
            if result.warnings:
                llm_output += "\n\n---\n" + "\n".join(
                    f"⚠️ {w}" for w in result.warnings
                )
            return llm_output, result

        # 违规 → 注入修正指令
        correction_msg = self._build_correction(result)
        messages.append({"role": "user", "content": correction_msg})

        response = self._llm_chat(messages, tools=None)
        retry_output = response.content or llm_output

        # 再检查一次
        result2 = self.check(retry_output, messages)
        if result2.passed:
            return retry_output, result2

        # 仍不通过 → 放行但标记
        retry_output += "\n\n---\n⚠️ 自动验证未通过，以下结果请人工审核：\n" + "\n".join(
            f"- {v}" for v in result2.violations
        )
        return retry_output, result2

    # ---- Rule Implementations ----

    def _check_rule_a(
        self, llm_output: str, evidence: list[ToolEvidence]
    ) -> str | None:
        """Rule A: 有效/无效地址必须有工具证据支撑"""
        verdicts = self._parse_verdicts(llm_output)
        if not verdicts:
            return None  # 无法解析审核结论，不强制要求

        valid_evidence = [e for e in evidence if e.is_valid]
        needs_evidence = any(
            v in {"有效地址", "无效地址"} for v in verdicts
        )

        # 「审核失败」是技术性核验中断的声明，本身即"无成功工具证据"，不强制要求证据；
        # 但要求依据写明失败原因与下一步，否则给出警告（软校验）。
        if "审核失败" in verdicts and not _mentions_next_step(llm_output):
            warnings.append(
                "存在'审核失败'结论，但审核依据未清晰写明失败原因与下一步操作建议，"
                "请补充①地图 API 失败原因 ②已尝试联网搜索但无结果 ③下一步建议（换 Key/稍后重试/转人工）。"
            )

        if needs_evidence and len(valid_evidence) == 0:
            return (
                "审核结论包含'有效地址'或'无效地址'，但未检测到任何成功的工具调用记录。"
                "请确保已调用 geocode 或 web_search 工具进行验证。"
            )
        return None

    def _check_rule_b(
        self, llm_output: str, known_urls: set[str]
    ) -> tuple[list[str], list[str]]:
        """Rule B: 输出中的 URL 必须在工具证据中可溯源"""
        cited = set(URL_PATTERN.findall(llm_output))
        if not cited:
            # 输出中没有 URL，但有模糊引用？
            if _has_vague_reference(llm_output):
                return [], [
                    "审核依据中提到了搜索/查询结果，但未包含具体链接。请补充可跳转的网页链接以便人工核验。"
                ]
            return [], []

        fabricated = []
        for url in cited:
            # 精确匹配或子串匹配
            if not any(url in known or known in url for known in known_urls):
                fabricated.append(url)

        if fabricated:
            return [
                f"以下链接未在工具调用结果中找到，请移除或替换为实际搜索结果：{', '.join(fabricated[:3])}"
            ], []

        return [], []

    def _check_rule_c(
        self, llm_output: str, evidence: list[ToolEvidence]
    ) -> str | None:
        """Rule C: 审核结论不能与工具证据明显矛盾"""
        verdicts = self._parse_verdicts(llm_output)
        if "有效地址" not in verdicts:
            return None

        geocode_ev = [e for e in evidence if e.tool_name == "geocode"]
        search_ev = [e for e in evidence if e.tool_name == "web_search"]

        # 过滤掉所有 error 状态的工具调用（found=None 说明工具没实际跑成功）
        geocode_ok = [e for e in geocode_ev if e.found is not None]
        search_ok = [e for e in search_ev if e.raw_result and e.raw_result.get("status") != "error"]

        # 所有有效 geocode 都未找到 AND 所有有效搜索都为空 → 与"有效"矛盾
        if not geocode_ok and not search_ok:
            return None  # 所有工具都报错，无法判断，跳过 Rule C

        all_geocode_not_found = all(e.found is False for e in geocode_ok) if geocode_ok else False
        all_search_empty = all(len(e.urls) == 0 for e in search_ok) if search_ok else False

        if geocode_ok and all_geocode_not_found and search_ok and all_search_empty:
            return (
                "审核结论为'有效地址'，但高德地图未找到该地址且联网搜索也无任何结果。"
                "请核实审核结论是否与工具证据一致。"
            )

        return None

    def _check_rule_d(self, llm_output: str) -> str | None:
        """Rule D: 输出格式必须包含合法的审核结果表格（五列或六列均可）"""
        # 检查是否有 Markdown 表格结构
        lines = llm_output.split("\n")
        table_lines = [l for l in lines if l.strip().startswith("|")]
        if len(table_lines) < 2:
            return "输出未包含审核结果表格，请按表格格式输出（含「序号 / 地址 / 审核结果 / 审核依据 / 审核信息源」列，批量场景再加「姓名」列）。"

        # 检查表头
        header = table_lines[0]
        header_parts = [p.strip() for p in header.split("|") if p.strip()]
        has_name = any("姓名" in p for p in header_parts)
        required = ["序号", "审核结果"]
        for req in required:
            if not any(req in p for p in header_parts):
                return f"表格缺少'{req}'列，请按表格格式输出（序号 | 地址 | 审核结果 | 审核依据 | 审核信息源）。"
        if not any("地址" in p for p in header_parts) and not has_name:
            return "表格缺少'地址'（或'姓名'）列，请包含地址列。"

        # 判定列索引：六列（含姓名）在第 4 列，五列在第 3 列
        verdict_col = 3 if has_name else 2
        data_lines = [l for l in table_lines[1:] if not _is_separator(l)]
        for line in data_lines:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) > verdict_col:
                verdict = _clean_verdict(parts[verdict_col])
                if verdict and verdict not in VALID_VERDICTS:
                    return (
                        f"'{parts[verdict_col]}' 不是有效的审核结果。请使用：有效地址、无效地址、不确定、不符合地址格式。"
                    )

        return None

    def _parse_verdicts(self, llm_output: str) -> set[str]:
        """从 LLM 输出中提取所有审核结论"""
        found = set()
        for v in VALID_VERDICTS:
            if v in llm_output:
                found.add(v)
        return found

    # ---- Rule E: 联网搜索结果强相关性 ----
    def _check_rule_e(
        self, llm_output: str, evidence: list[ToolEvidence]
    ) -> tuple[list[str], list[str]]:
        """Rule E: 引用的 web_search 结果必须与待核地址强相关。

        做法：从 geocode 返回的规范化地址（formatted_address）抽取地址 token，
        逐条检查 web_search 结果的标题+摘要是否命中任一 token。
        - 命中 0 个 token → 低相关结果；
        - 模型结论**引用**了低相关结果的 URL → 违规（用无关材料作证）；
        - 仅存在低相关结果但未被引用 → 警告（透明化，供人工复核）。
        """
        addr_tokens: set[str] = set()
        for e in evidence:
            if e.tool_name == "geocode" and isinstance(e.raw_result, dict):
                fa = e.raw_result.get("formatted_address") or e.raw_result.get("address") or ""
                if fa:
                    addr_tokens |= _tokenize_address(fa)
        if not addr_tokens:
            return [], []  # 无地址参照（如地图全失败降级场景），无法判定相关性，跳过

        low_rel_urls: list[str] = []
        for e in evidence:
            if e.tool_name != "web_search":
                continue
            for r in e.search_results:
                text = f"{r.get('title', '')} {r.get('snippet', '')}"
                if not text.strip():
                    continue
                if not any(tok in text for tok in addr_tokens):
                    u = r.get("url", "")
                    if u and u not in low_rel_urls:
                        low_rel_urls.append(u)

        if not low_rel_urls:
            return [], []

        warnings = [
            f"联网搜索结果中有 {len(low_rel_urls)} 条与待核地址无关键词重合（可能无关），"
            f"建议仅引用与地址直接相关的来源：{', '.join(u for u in low_rel_urls[:3] if u)}"
        ]
        # 若模型在结论中引用了无关结果 → 硬性违规
        cited = set(URL_PATTERN.findall(llm_output))
        for u in low_rel_urls:
            if u and any(u in c or c in u for c in cited):
                return [
                    f"审核结论引用了与地址无强相关的搜索结果（{u}），"
                    f"请移除或替换为与地址直接相关的来源网页。"
                ], warnings
        return [], warnings

    # ---- Rule F: 行政区划一致性 ----
    def _check_rule_f(
        self, llm_output: str, evidence: list[ToolEvidence]
    ) -> tuple[list[str], list[str]]:
        """Rule F: 结论提及的省份应与地图核验返回的省份一致。

        仅当 geocode 成功返回 province 且结论文本明确提及一个「不同」省份时才告警
        （避免多地址批量场景的误报）。属软校验（警告），不阻断输出。
        """
        geo_provs = {e.province for e in evidence if e.tool_name == "geocode" and e.province}
        if not geo_provs:
            return [], []
        out_provs = _extract_provinces(llm_output)
        if not out_provs:
            return [], []
        # 归一化：避免「北京市」与「北京」被误判为冲突（取最长匹配优先）
        norm = lambda s: max(s, key=len) if s else ""
        geo_norm = {norm({p for p in _PROVINCES if p in gp}) for gp in geo_provs}
        geo_norm = {x for x in geo_norm if x}
        conflict = {norm({p for p in _PROVINCES if p in op}) for op in out_provs}
        conflict = {x for x in conflict if x} - geo_norm
        if conflict:
            return [], [
                f"审核依据中提及的省份 {sorted(conflict)} 与地图核验返回的省份 {sorted(geo_provs)} 不一致，"
                f"请复核是否存在地址归属地判断错误。"
            ]
        return [], []

    def _build_correction(self, result: GuardResult) -> str:
        """构造修正指令"""
        lines = ["## 审核结果验证未通过，请修正以下问题后重新输出："]
        for i, v in enumerate(result.violations, 1):
            lines.append(f"{i}. {v}")
        if result.warnings:
            lines.append("\n注意事项：")
            for w in result.warnings:
                lines.append(f"- {w}")
        lines.append("\n请修正后重新输出完整的审核报告。")
        return "\n".join(lines)


# ---- Helpers ----

# 省级行政区名称（用于 Rule F 省份一致性判断；含直辖市、自治区、特别行政区）
_PROVINCES = [
    "北京市", "天津市", "上海市", "重庆市",
    "河北省", "山西省", "内蒙古自治区", "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省", "河南省",
    "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省", "四川省",
    "贵州省", "云南省", "西藏自治区", "陕西省", "甘肃省", "青海省",
    "宁夏回族自治区", "新疆维吾尔自治区", "台湾省",
    "香港特别行政区", "澳门特别行政区",
    # 短称（用于匹配结论中「浙江省」「江苏」等写法）
    "北京", "天津", "上海", "重庆", "河北", "山西", "内蒙古", "辽宁", "吉林",
    "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北",
    "湖南", "广东", "广西", "海南", "四川", "贵州", "云南", "西藏", "陕西",
    "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门",
]

# 地址切分分隔符（省/市/区/路/号/栋…）：用于把规范化地址拆成可匹配的 token
_ADDR_DELIM = re.compile(r"[省市区县旗镇乡村街道路街大道号栋幢室单元层组弄里小区广场大厦花园苑公寓省直辖县、，,。\s]+")

# 过于通用的单字/短词，作为 token 噪声应剔除（避免「路」「号」等造成假相关）
_ADDR_STOP = {"省", "市", "区", "县", "镇", "乡", "村", "路", "街", "号", "栋", "幢",
              "室", "单元", "层", "组", "弄", "里", "小区", "广场", "大厦", "花园",
              "苑", "公寓", "大道", "街道", "号室", "栋室"}


def _tokenize_address(addr: str) -> set[str]:
    """把规范化地址拆成有意义的关键词 token（省/市/区/路名/门牌号等）。"""
    if not addr:
        return set()
    tokens: set[str] = set()
    # 完整串也作为 token（兜底，覆盖「中关村大街1号」这类连写）
    tokens.add(addr.strip())
    for part in _ADDR_DELIM.split(addr):
        part = part.strip()
        if len(part) >= 2 and part not in _ADDR_STOP:
            tokens.add(part)
    # 再按 2~4 字滑动窗口补充（捕获「海淀区」「中关村」等子串）
    clean = re.sub(r"\s+", "", addr)
    for n in (2, 3, 4):
        for i in range(len(clean) - n + 1):
            tok = clean[i:i + n]
            if tok not in _ADDR_STOP:
                tokens.add(tok)
    return tokens


def _extract_provinces(text: str) -> set[str]:
    """从文本中提取出现的省份级行政区名称（剔除被更长名称包含的短称，如「北京」⊂「北京市」）。"""
    found = {p for p in _PROVINCES if p in text}
    # 去掉是其他成员子串的短称，避免「北京」与「北京市」被误判为冲突
    return {p for p in found if not any(p != q and p in q for q in found)}


def _mentions_next_step(text: str) -> bool:
    """判断审核依据是否提及失败原因/下一步（用于"审核失败"结论的软校验）"""
    signals = ["失败原因", "下一步", "转人工", "稍后重试", "更换", "配置有效", "QPS", "限流", "网络超时", "Key"]
    return any(s in text for s in signals)


def _is_separator(line: str) -> bool:
    """判断是否是 Markdown 表格分隔行 |---|"""
    stripped = line.strip().replace(" ", "")
    return bool(re.match(r"^\|[:\-]+\|", stripped))


def _clean_verdict(text: str) -> str:
    """从文本中提取审核结果关键词"""
    text = text.strip()
    for v in VALID_VERDICTS:
        if v in text:
            return v
    return ""


def _has_vague_reference(text: str) -> bool:
    """检查是否有模糊引用但无具体链接"""
    patterns = [
        r"经.*搜索",
        r"经.*地图.*查",
        r"根据.*搜索结果",
        r"参考.*网页",
        r"来源[:：]",
        r"参[见考][:：]",
    ]
    return any(re.search(p, text) for p in patterns)


def extract_urls(text: str) -> list[str]:
    """从文本中提取所有 URL"""
    return URL_PATTERN.findall(text)

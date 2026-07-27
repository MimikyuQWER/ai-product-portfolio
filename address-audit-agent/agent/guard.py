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
VALID_VERDICTS = {"有效地址", "无效地址", "不确定", "不符合地址格式"}

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
        """从工具结果中提取所有 URL"""
        urls = []
        for item in raw.get("results", []):
            url = item.get("url", "").strip()
            if url:
                urls.append(url)
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
        """Rule D: 输出格式必须包含合法的四列表格"""
        # 检查是否有 Markdown 表格结构
        lines = llm_output.split("\n")
        table_lines = [l for l in lines if l.strip().startswith("|")]
        if len(table_lines) < 2:
            return "输出未包含审核结果表格，请按四列表格格式输出（序号 | 地址 | 审核结果 | 审核依据）。"

        # 检查表头
        header = table_lines[0]
        header_parts = [p.strip().lower() for p in header.split("|") if p.strip()]
        required = ["序号", "地址", "审核结果"]
        for req in required:
            if req not in header_parts and not any(req in p for p in header_parts):
                return f"表格缺少'{req}'列，请按四列表格格式输出（序号 | 地址 | 审核结果 | 审核依据）。"

        # 检查数据行的审核结果是否为四类之一
        data_lines = [l for l in table_lines if not _is_separator(l) and l != table_lines[0]]
        for line in data_lines:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 3:
                verdict = _clean_verdict(parts[2])
                if verdict and verdict not in VALID_VERDICTS:
                    return (
                        f"'{parts[2]}' 不是有效的审核结果。请使用：有效地址、无效地址、不确定、不符合地址格式。"
                    )

        return None

    def _parse_verdicts(self, llm_output: str) -> set[str]:
        """从 LLM 输出中提取所有审核结论"""
        found = set()
        for v in VALID_VERDICTS:
            if v in llm_output:
                found.add(v)
        return found

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

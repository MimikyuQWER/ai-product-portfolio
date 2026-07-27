"""
地址审核 Agent 主类
实现 ReAct 模式：LLM 思考 → 调用工具 → 观察结果 → 输出结论
"""

import json
from pathlib import Path
from .llm import LLMService
from .tools import TOOL_DEFINITIONS, execute_tool
from .guard import ResultGuard

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

        # 结果验证门
        self.guard = ResultGuard(llm_chat_fn=self.llm.chat)

    # ================================================================
    # 公开方法
    # ================================================================

    def start(self) -> str:
        """返回 Agent 的开场白"""
        greeting = self._call_llm("（对话刚开始，请向用户问好并介绍你的功能）")
        self.messages.append({"role": "assistant", "content": greeting})
        return greeting

    def chat(self, user_input: str) -> str:
        """处理用户文本输入，返回 Agent 回复"""
        self.messages.append({"role": "user", "content": user_input})
        return self._run_agent_loop()

    def process_excel(self, file_bytes: bytes, filename: str) -> str:
        """处理上传的 Excel 文件，返回审核结果"""
        import base64

        file_b64 = base64.b64encode(file_bytes).decode("utf-8")

        # 先解析 Excel
        from .tools import parse_excel

        parse_result = parse_excel(file_b64)
        parse_data = json.loads(parse_result)

        if parse_data.get("status") == "error":
            error_msg = f"Excel 文件解析失败：{parse_data.get('message')}。请检查文件格式。"
            self.messages.append({"role": "assistant", "content": error_msg})
            return error_msg

        records = parse_data.get("records", [])
        total = parse_data.get("total", 0)

        # 零记录保护：防止 LLM 收到矛盾指令后编造数据
        if total == 0:
            msg = (
                f"文件「{filename}」已成功解析，但未找到任何有效的地址记录。\n"
                f"检测到的列名：{parse_data.get('columns', [])}\n"
                f"请确认 Excel 中包含'地址'或'详细地址'列，且列中有有效数据。"
            )
            self.messages.append({"role": "assistant", "content": msg})
            return msg

        # 大文件保护：超过批次上限时，只发送前 N 条，避免超出 LLM token 限制
        batch_limit = 30
        if total > batch_limit:
            truncated_records = records[:batch_limit]
            parse_data["records"] = truncated_records
            parse_data["total"] = batch_limit  # 修正 total 与 records 长度一致，防止 LLM 编造
            batch_note = (
                f"（共 {total} 条记录，由于单次处理限制，先审核前 {batch_limit} 条。"
                f"请告知用户剩余 {total - batch_limit} 条可在新会话中继续审核。）"
            )
        else:
            batch_note = ""

        # 告知 LLM 文件解析情况，让 LLM 主动处理
        context = (
            f"用户上传了文件「{filename}」，已解析出 {total} 条地址记录。{batch_note}\n\n"
            f"解析结果如下：\n"
            f"```json\n{json.dumps(parse_data, ensure_ascii=False, indent=2)}\n```\n\n"
            f"请确认收到文件并告知用户记录数量，然后逐条审核这些地址。"
            f"请使用 geocode 和 web_search 工具验证每条地址，"
            f"最后按四列表格（序号、地址、审核结果、审核依据）汇总输出审核结果。"
        )

        self.messages.append({"role": "user", "content": context})
        return self._run_agent_loop()

    def reset(self):
        """重置会话"""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.step_log = []

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
        """单次调用 LLM（不使用工具），返回文本内容"""
        temp_messages = self.messages + [{"role": "user", "content": user_message}]
        response = self.llm.chat(temp_messages, tools=None)
        return response.content or ""

    def _run_agent_loop(self) -> str:
        """
        ReAct Agent 循环
        LLM 可以多次调用工具，直到给出最终文本回复
        """
        max_iterations = 10  # 防止死循环
        max_tool_rounds = max_iterations - 1  # 最后一轮留给文字总结

        for iteration in range(max_iterations):
            self.step_log.append({"step": "reasoning", "status": "running", "text": "AI 分析中…"})
            response = self.llm.chat(self.messages, tools=self.tools)
            self.step_log[-1]["status"] = "done"
            self.step_log[-1]["text"] = "文本理解完成" if not response.has_tool_calls else "AI 决定调用工具验证"

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
                final_response = self.llm.chat(self.messages, tools=None)
                final_content = final_response.content or ""
                self.messages.append({"role": "assistant", "content": final_content})
                return final_content

            # 文字回复 → 最终输出
            final_content = response.content or ""

            if response.finish_reason == "length":
                final_content += "\n\n⚠️ 注意：AI 输出因长度限制被截断，审核结果可能不完整，请减少单次提交的地址数量后重试。"

            # ResultGuard：仅在输出包含审核结果时才验证，闲聊消息直接放行
            is_audit_report = (
                "|---" in final_content and (
                    "有效地址" in final_content or "无效地址" in final_content
                    or "不确定" in final_content or "不符合地址格式" in final_content
                )
            )
            if is_audit_report:
                self.step_log.append({"step": "guard", "status": "running", "text": "结果验证中…"})
                # 用 copy 隔离，防止 guard 的修正指令污染后续对话
                verified_output, guard_result = self.guard.check_and_retry(
                    final_content, list(self.messages)
                )
                if guard_result.passed:
                    self.step_log[-1] = {"step": "guard", "status": "done", "text": "结果验证通过 ✓"}
                else:
                    self.step_log[-1] = {
                        "step": "guard", "status": "warn",
                        "text": f"验证未完全通过（{len(guard_result.violations)}项违规），已自动修正"
                    }
                if guard_result.warnings:
                    for w in guard_result.warnings:
                        self.step_log.append({"step": "warn", "status": "warn", "text": w})
                self.messages.append({"role": "assistant", "content": verified_output})
                return verified_output

            # 非审核报告 → 无需 guard
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

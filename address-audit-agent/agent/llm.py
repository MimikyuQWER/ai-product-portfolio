"""
LLM 调用封装
支持 OpenAI 兼容接口（DeepSeek / OpenAI / 其他）
"""

import os
import json
import logging
from typing import Any
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 加载用户个人 .env（优先级最高）
load_dotenv()
# 兜底：若用户未创建 .env，则从 .env.example 载入预配 Key（如高德），实现开箱即用
_ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"
if _ENV_EXAMPLE.exists():
    load_dotenv(_ENV_EXAMPLE, override=False)

logger = logging.getLogger(__name__)


class LLMCallError(Exception):
    """LLM 调用失败（网络/鉴权/服务端错误）。

    旧实现会把失败吞掉、返回一个伪造的「AI 服务不可用」文本，导致上层（start / 质量预审 /
    Agent 主循环）把它当成正常回复继续处理，出现死代码降级分支（🟠-14）。现改为显式抛出，
    由各调用点决定如何优雅降级。
    """


class LLMService:
    """统一的 LLM 调用服务，支持 function calling"""

    def __init__(self):
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")

        if not api_key:
            raise ValueError(
                "未设置 LLM_API_KEY，请在 .env 文件中配置。\n"
                "复制 .env.example 为 .env 并填入你的 API Key。"
            )

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> "LLMResponse":
        """
        调用 LLM，支持 function calling

        Args:
            messages: 消息列表 [{"role": "system/user/assistant/tool", "content": "..."}]
            tools: 工具定义列表（OpenAI function calling 格式）

        Returns:
            LLMResponse 对象
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,  # 低温，确保审核结果稳定
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.warning("LLM API 调用失败：%s", e)
            # 显式上抛，由调用方决定降级策略（🟠-14 修复）
            raise LLMCallError(f"LLM 调用失败：{e}") from e

        # 保护：空 choices 列表
        if not response.choices:
            logger.warning("LLM 返回空 choices 列表")
            raise LLMCallError("LLM 返回了空响应（无 choices）")

        choice = response.choices[0]

        # 安全解析 tool_calls（含畸形 JSON 保护）
        tool_calls = []
        for tc in (choice.message.tool_calls or []):
            try:
                parsed_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                logger.warning(
                    "LLM 返回了无法解析的 tool_call arguments，已跳过：%s",
                    tc.function.arguments[:200],
                )
                continue  # 跳过这个损坏的 tool_call，不崩溃
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=parsed_args)
            )

        return LLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
        )


class LLMResponse:
    """LLM 返回结果"""

    def __init__(
        self,
        content: str | None,
        tool_calls: list["ToolCall"] | None,
        finish_reason: str | None,
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class ToolCall:
    """工具调用请求"""

    def __init__(self, id: str, name: str, arguments: dict):
        self.id = id
        self.name = name
        self.arguments = arguments

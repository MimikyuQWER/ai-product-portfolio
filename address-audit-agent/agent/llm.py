"""
LLM 调用封装
支持 OpenAI 兼容接口（DeepSeek / OpenAI / 其他）
"""

import os
import json
import logging
from typing import Any
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)


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
            return LLMResponse(
                content=f"抱歉，AI 服务暂时不可用，请稍后重试。（错误详情：{e}）",
                tool_calls=None,
                finish_reason="error",
            )

        # 保护：空 choices 列表
        if not response.choices:
            logger.warning("LLM 返回空 choices 列表")
            return LLMResponse(
                content="抱歉，AI 返回了空响应，请重试。",
                tool_calls=None,
                finish_reason="error",
            )

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

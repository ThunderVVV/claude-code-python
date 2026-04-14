"""OpenAI compatible API client using official OpenAI SDK"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI
from cc_code.utils.logging_config import log_full_exception

from cc_code.core.messages import (
    Message,
    MessageRole,
    ToolUseContent,
    ToolResultContent,
    Usage,
)
from cc_code.core.tools import ToolRegistry

logger = logging.getLogger(__name__)

PARTIAL_JSON_STRING_FIELD_RE = re.compile(
    r'"(?P<key>[^"\\]+)"\s*:\s*"(?P<value>(?:[^"\\]|\\.)*)"'
)


@dataclass
class OpenAIClientConfig:
    """Configuration for OpenAI API client"""

    api_url: str
    api_key: str
    model_name: str
    model_id: str = ""
    max_tokens: int = 16384
    temperature: float = 0.7
    timeout: float = 300.0  # 5 minutes default
    max_retries: int = 3


@dataclass
class ToolCallDelta:
    """Incremental tool call data during streaming"""

    id: str = ""
    name: str = ""
    arguments: str = ""


class OpenAIClient:
    """OpenAI compatible API client with streaming support using official SDK"""

    def __init__(self, config: OpenAIClientConfig):
        self.config = config
        # Initialize official OpenAI SDK client
        self._client = AsyncOpenAI(
            base_url=config.api_url,
            api_key=config.api_key,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )

    async def close(self) -> None:
        """Close the HTTP client"""
        await self._client.close()

    def _convert_messages_to_openai_format(
        self,
        messages: List[Message],
    ) -> List[Dict[str, Any]]:
        """Convert internal message format to OpenAI format"""
        openai_messages = []

        for msg in messages:
            if msg.type == MessageRole.SYSTEM:
                openai_messages.append(
                    {
                        "role": "system",
                        "content": msg.get_text(),
                    }
                )

            elif msg.type == MessageRole.USER:
                openai_messages.append(
                    {
                        "role": "user",
                        "content": msg.get_text(),
                    }
                )

            elif msg.type == MessageRole.ASSISTANT:
                # Check if message has tool calls
                tool_uses = msg.get_tool_uses()

                if tool_uses:
                    # Assistant message with tool calls
                    tool_calls = []
                    for tu in tool_uses:
                        tool_calls.append(
                            {
                                "id": tu.id,
                                "type": "function",
                                "function": {
                                    "name": tu.name,
                                    "arguments": json.dumps(tu.input),
                                },
                            }
                        )

                    openai_messages.append(
                        {
                            "role": "assistant",
                            "content": msg.get_text() or None,
                            "tool_calls": tool_calls,
                        }
                    )
                else:
                    # Simple text message
                    text = msg.get_text()
                    openai_messages.append(
                        {
                            "role": "assistant",
                            "content": text,
                        }
                    )

            elif msg.type == MessageRole.TOOL:
                # Tool result message
                for block in msg.content:
                    if isinstance(block, ToolResultContent):
                        openai_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": block.tool_use_id,
                                "content": block.content,
                            }
                        )

        return openai_messages

    async def chat_completion(
        self,
        messages: List[Message],
        tool_registry: Optional[ToolRegistry] = None,
        stream: bool = True,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Make a chat completion request using official OpenAI SDK.

        Yields streaming events or complete responses.
        """
        # Build messages list
        openai_messages = []

        # Add system prompt if provided
        if system_prompt:
            openai_messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        # Add conversation messages
        openai_messages.extend(self._convert_messages_to_openai_format(messages))

        # Build request parameters
        request_params = {
            "model": self.config.model_name,
            "messages": openai_messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": stream,
        }
        if stream:
            request_params["stream_options"] = {"include_usage": True}

        # Add tools if available
        if tool_registry:
            tools = tool_registry.get_tool_definitions()
            if tools:
                request_params["tools"] = tools

        try:
            if stream:
                # Streaming request using SDK
                stream_response = await self._client.chat.completions.create(
                    **request_params
                )
                chunk_index = 0
                async for chunk in stream_response:
                    chunk_index += 1
                    chunk_dict = chunk.model_dump()
                    yield chunk_dict
            else:
                # Non-streaming request using SDK
                response = await self._client.chat.completions.create(**request_params)
                yield response.model_dump()

        except Exception as e:
            log_full_exception(logger, "API error in chat completion", e)
            raise APIError(f"API error: {e}") from e

    def parse_stream_chunk(
        self,
        chunk: Dict[str, Any],
    ) -> tuple[str, str, List[ToolCallDelta]]:
        """
        Parse a stream chunk into text delta, thinking delta, and tool call deltas.

        Returns (text_delta, thinking_delta, tool_call_deltas)
        """
        text = ""
        thinking = ""
        tool_calls = []

        choices = chunk.get("choices", [])
        if not choices:
            return text, thinking, tool_calls

        delta = choices[0].get("delta", {})

        # Extract reasoning_content (thinking) - for models like DeepSeek
        if "reasoning_content" in delta and delta["reasoning_content"] is not None:
            thinking = delta["reasoning_content"]

        # Extract text content
        if "content" in delta and delta["content"] is not None:
            text = delta["content"]

        # Extract tool call deltas
        if "tool_calls" in delta and delta["tool_calls"] is not None:
            for tc in delta["tool_calls"]:
                idx = tc.get("index", 0)

                # Extend list if needed
                while idx >= len(tool_calls):
                    tool_calls.append(ToolCallDelta())

                # Update tool call delta
                if "id" in tc:
                    tool_calls[idx].id = tc["id"]
                if "function" in tc:
                    func = tc["function"]
                    if "name" in func and func["name"] is not None:
                        tool_calls[idx].name = func["name"]
                    if "arguments" in func and func["arguments"] is not None:
                        tool_calls[idx].arguments += func["arguments"]

        return text, thinking, tool_calls

    def parse_non_stream_response(
        self,
        response: Dict[str, Any],
    ) -> tuple[str, str, List[ToolUseContent], Optional[Usage]]:
        """
        Parse a non-stream response into text, thinking, tool uses, and usage.

        Returns (text, thinking, tool_uses, usage)
        """
        text = ""
        thinking = ""
        tool_uses = []
        usage = None

        choices = response.get("choices", [])
        if not choices:
            return text, thinking, tool_uses, usage

        message = choices[0].get("message", {})

        # Extract reasoning_content (thinking) - for models like DeepSeek
        if "reasoning_content" in message and message["reasoning_content"] is not None:
            thinking = message["reasoning_content"]

        # Extract text content
        if "content" in message and message["content"] is not None:
            text = message["content"]

        # Extract tool calls
        if "tool_calls" in message and message["tool_calls"] is not None:
            for tc in message["tool_calls"]:
                try:
                    args = json.loads(tc["function"]["arguments"])
                    tool_uses.append(
                        ToolUseContent(
                            id=tc["id"],
                            name=tc["function"]["name"],
                            input=args,
                        )
                    )
                except (KeyError, json.JSONDecodeError):
                    continue

        usage = self.extract_usage(response)

        return text, thinking, tool_uses, usage

    def extract_usage(self, payload: Dict[str, Any]) -> Optional[Usage]:
        """Extract usage metadata from streaming or non-streaming payloads."""
        usage_payload = payload.get("usage")
        if not isinstance(usage_payload, dict):
            return None

        return Usage(
            input_tokens=usage_payload.get("prompt_tokens", 0),
            output_tokens=usage_payload.get("completion_tokens", 0),
        )

    def accumulate_tool_calls(
        self,
        accumulated: List[ToolCallDelta],
        new_deltas: List[ToolCallDelta],
    ) -> List[ToolCallDelta]:
        """Merge new tool call deltas into accumulated list

        Note: We use position-based matching because in streaming responses,
        the id may only appear in the first chunk, while subsequent chunks
        only contain the arguments. We match by position in the list.
        """
        for i, delta in enumerate(new_deltas):
            # Extend list if needed
            while i >= len(accumulated):
                accumulated.append(ToolCallDelta())

            # Merge into existing at same position
            if delta.id:
                accumulated[i].id = delta.id
            if delta.name:
                accumulated[i].name = delta.name
            if delta.arguments:
                accumulated[i].arguments += delta.arguments

        return accumulated

    def tool_calls_to_content_blocks(
        self,
        tool_calls: List[ToolCallDelta],
        allow_partial: bool = False,
    ) -> List[ToolUseContent]:
        """Convert accumulated tool call deltas to content blocks"""
        blocks = []
        for tc in tool_calls:
            if tc.id and tc.name:
                try:
                    args = self._parse_tool_call_arguments(
                        tc.arguments,
                        allow_partial=allow_partial,
                    )
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse tool call arguments: {e}")
                    args = {}

                args_full_str = str(args)
                args_str = (
                    args_full_str[:50] + "..."
                    if len(args_full_str) > 50
                    else args_full_str
                )
                logger.debug(
                    f"Full tool call parsed: {tc.name}, id: {tc.id}, args: {args_str}"
                )
                blocks.append(
                    ToolUseContent(
                        id=tc.id,
                        name=tc.name,
                        input=args,
                    )
                )
            else:
                logger.warning(
                    f"Skipping incomplete tool call: id={tc.id}, name={tc.name}"
                )
        return blocks

    def _parse_tool_call_arguments(
        self,
        arguments: str,
        allow_partial: bool = False,
    ) -> Dict[str, Any]:
        """Parse complete tool arguments, or recover stable top-level string fields."""
        if not arguments:
            return {}

        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            if allow_partial:
                return self._extract_partial_string_fields(arguments)
            raise

        if isinstance(parsed, dict):
            return parsed
        return {}

    def partial_tool_calls_to_content_blocks(
        self,
        tool_calls: List[ToolCallDelta],
    ) -> List[ToolUseContent]:
        """Build preview tool blocks from the currently streamed tool call deltas."""
        blocks = []
        for tc in tool_calls:
            if not tc.id or not tc.name:
                continue
            args = self._parse_tool_call_arguments(tc.arguments, allow_partial=True)
            blocks.append(
                ToolUseContent(
                    id=tc.id,
                    name=tc.name,
                    input=args,
                )
            )
        return blocks

    def _extract_partial_string_fields(self, arguments: str) -> Dict[str, Any]:
        """Recover top-level string fields whose values are already fully streamed."""
        partial: Dict[str, Any] = {}
        for match in PARTIAL_JSON_STRING_FIELD_RE.finditer(arguments):
            key = match.group("key")
            if key in partial:
                continue
            raw_value = match.group("value")
            try:
                partial[key] = json.loads(f'"{raw_value}"')
            except json.JSONDecodeError:
                continue
        return partial

    async def _chat_completion_raw(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Simple non-streaming chat completion for internal use.

        Args:
            messages: List of message dicts in OpenAI format
            model: Model name (uses config default if not provided)
            max_tokens: Max tokens (uses config default if not provided)
            temperature: Temperature (uses config default if not provided)

        Returns:
            Raw response dict
        """
        request_params = {
            "model": model or self.config.model_name,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "stream": False,
        }

        response = await self._client.chat.completions.create(**request_params)
        return response.model_dump()


class APIError(Exception):
    """Base exception for API errors"""

    pass


"""OpenAI compatible API client - aligned with TypeScript claude.ts streaming logic"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx

from claude_code.core.messages import (
    ContentBlock,
    Message,
    MessageRole,
    TextContent,
    ToolUseContent,
    ToolResultContent,
    Usage,
    generate_uuid,
)
from claude_code.core.tools import ToolRegistry
from claude_code.core.prompts import create_default_system_prompt, build_context_message

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # seconds
RETRY_DELAY_MULTIPLIER = 2.0

# Network errors that should trigger retry
RETRYABLE_ERRORS = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.WriteTimeout,
    ConnectionError,
    OSError,
)


@dataclass
class OpenAIClientConfig:
    """Configuration for OpenAI API client"""
    api_url: str
    api_key: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: float = 300.0  # 5 minutes default
    max_retries: int = MAX_RETRIES


@dataclass
class ToolCallDelta:
    """Incremental tool call data during streaming"""
    id: str = ""
    name: str = ""
    arguments: str = ""


class OpenAIClient:
    """OpenAI compatible API client with streaming support"""

    def __init__(self, config: OpenAIClientConfig):
        self.config = config
        # Configure httpx with better connection handling and HTTP/2 support
        self._client = httpx.AsyncClient(
            base_url=config.api_url,
            http2=True,  # Enable HTTP/2 support for servers that require it
            timeout=httpx.Timeout(
                connect=30.0,  # Connection timeout
                read=config.timeout,  # Read timeout
                write=60.0,  # Write timeout
                pool=30.0,  # Pool timeout
            ),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30.0,
            ),
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
        )
        self._retry_count = 0

    async def close(self) -> None:
        """Close the HTTP client"""
        await self._client.aclose()

    def _convert_messages_to_openai_format(
        self,
        messages: List[Message],
    ) -> List[Dict[str, Any]]:
        """Convert internal message format to OpenAI format"""
        openai_messages = []

        logger.debug(f"Converting {len(messages)} messages to OpenAI format")
        for i, msg in enumerate(messages):
            if msg.type == MessageRole.SYSTEM:
                openai_messages.append({
                    "role": "system",
                    "content": msg.get_text(),
                })

            elif msg.type == MessageRole.USER:
                openai_messages.append({
                    "role": "user",
                    "content": msg.get_text(),
                })

            elif msg.type == MessageRole.ASSISTANT:
                # Check if message has tool calls
                tool_uses = msg.get_tool_uses()

                if tool_uses:
                    # Assistant message with tool calls
                    tool_calls = []
                    for tu in tool_uses:
                        tool_calls.append({
                            "id": tu.id,
                            "type": "function",
                            "function": {
                                "name": tu.name,
                                "arguments": json.dumps(tu.input),
                            },
                        })

                    openai_messages.append({
                        "role": "assistant",
                        "content": msg.get_text() or None,
                        "tool_calls": tool_calls,
                    })
                    logger.debug(f"  Message {i}: assistant with {len(tool_uses)} tool calls")
                else:
                    # Simple text message
                    text = msg.get_text()
                    openai_messages.append({
                        "role": "assistant",
                        "content": text,
                    })
                    logger.debug(f"  Message {i}: assistant text ({len(text)} chars)")

            elif msg.type == MessageRole.TOOL:
                # Tool result message
                for block in msg.content:
                    if isinstance(block, ToolResultContent):
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": block.tool_use_id,
                            "content": block.content,
                        })
                        logger.debug(f"  Message {i}: tool result for {block.tool_use_id}")

        logger.debug(f"Converted to {len(openai_messages)} OpenAI messages")
        return openai_messages

    async def chat_completion(
        self,
        messages: List[Message],
        tool_registry: Optional[ToolRegistry] = None,
        stream: bool = True,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Make a chat completion request with retry logic.

        Yields streaming events or complete responses.
        """
        # Build messages list
        openai_messages = []

        # Add system prompt if provided
        if system_prompt:
            openai_messages.append({
                "role": "system",
                "content": system_prompt,
            })

        # Add conversation messages
        openai_messages.extend(self._convert_messages_to_openai_format(messages))

        # Build request
        request_data = {
            "model": self.config.model_name,
            "messages": openai_messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": stream,
        }

        # Add tools if available
        if tool_registry:
            tools = tool_registry.get_tool_definitions()
            if tools:
                request_data["tools"] = tools

        # Retry loop for transient failures
        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries):
            try:
                if stream:
                    # Streaming request
                    async with self._client.stream(
                        "POST",
                        "/chat/completions",
                        json=request_data,
                        headers={
                            "Accept": "text/event-stream",
                            "Cache-Control": "no-cache",
                        },
                    ) as response:
                        response.raise_for_status()

                        async for line in response.aiter_lines():
                            line = line.strip()
                            if not line or not line.startswith("data:"):
                                continue
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                return
                            try:
                                data = json.loads(data_str)
                                yield data
                            except json.JSONDecodeError:
                                continue
                        return  # Successfully completed
                else:
                    # Non-streaming request
                    request_data["stream"] = False
                    response = await self._client.post(
                        "/chat/completions",
                        json=request_data,
                        headers={"Accept": "application/json"},
                    )
                    response.raise_for_status()
                    yield response.json()
                    return  # Successfully completed

            except RETRYABLE_ERRORS as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    delay = RETRY_DELAY_BASE * (RETRY_DELAY_MULTIPLIER ** attempt)
                    logger.warning(
                        f"Network error (attempt {attempt + 1}/{self.config.max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    # Reconnect with fresh client
                    await self._reconnect()
                else:
                    logger.error(f"Max retries ({self.config.max_retries}) exceeded. Last error: {e}")
                    raise APINetworkError(
                        f"Network error after {self.config.max_retries} attempts: {e}"
                    ) from e

            except httpx.HTTPStatusError as e:
                # HTTP errors (4xx, 5xx) - don't retry client errors (4xx)
                if e.response.status_code < 500:
                    # Client error - don't retry
                    raise APIError(
                        f"API error (HTTP {e.response.status_code}): {e.response.text}"
                    ) from e
                else:
                    # Server error - retry
                    last_error = e
                    if attempt < self.config.max_retries - 1:
                        delay = RETRY_DELAY_BASE * (RETRY_DELAY_MULTIPLIER ** attempt)
                        logger.warning(
                            f"Server error HTTP {e.response.status_code} (attempt {attempt + 1}/{self.config.max_retries}). "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise APIError(
                            f"Server error after {self.config.max_retries} attempts: HTTP {e.response.status_code}"
                        ) from e

            except json.JSONDecodeError as e:
                raise APIError(f"Invalid JSON response: {e}") from e

        # Should not reach here, but just in case
        if last_error:
            raise APINetworkError(f"Request failed: {last_error}") from last_error

    async def _reconnect(self) -> None:
        """Recreate the HTTP client for a fresh connection"""
        try:
            await self._client.aclose()
        except Exception:
            pass
        self._client = httpx.AsyncClient(
            base_url=self.config.api_url,
            http2=True,  # Enable HTTP/2 support
            timeout=httpx.Timeout(
                connect=30.0,
                read=self.config.timeout,
                write=60.0,
                pool=30.0,
            ),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30.0,
            ),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )

    def parse_stream_chunk(
        self,
        chunk: Dict[str, Any],
    ) -> tuple[str, List[ToolCallDelta]]:
        """
        Parse a stream chunk into text delta and tool call deltas.

        Returns (text_delta, tool_call_deltas)
        """
        text = ""
        tool_calls = []

        choices = chunk.get("choices", [])
        if not choices:
            return text, tool_calls

        delta = choices[0].get("delta", {})

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
                    logger.debug(f"Tool call chunk: idx={idx}, id={tc['id']}")
                if "function" in tc:
                    func = tc["function"]
                    if "name" in func:
                        tool_calls[idx].name = func["name"]
                        logger.debug(f"Tool call chunk: idx={idx}, name={func['name']}")
                    if "arguments" in func:
                        tool_calls[idx].arguments += func["arguments"]

        return text, tool_calls

    def parse_non_stream_response(
        self,
        response: Dict[str, Any],
    ) -> tuple[str, List[ToolUseContent], Optional[Usage]]:
        """
        Parse a non-stream response into text, tool uses, and usage.

        Returns (text, tool_uses, usage)
        """
        text = ""
        tool_uses = []
        usage = None

        choices = response.get("choices", [])
        if not choices:
            return text, tool_uses, usage

        message = choices[0].get("message", {})

        # Extract text content
        if "content" in message and message["content"] is not None:
            text = message["content"]

        # Extract tool calls
        if "tool_calls" in message and message["tool_calls"] is not None:
            for tc in message["tool_calls"]:
                try:
                    args = json.loads(tc["function"]["arguments"])
                    tool_uses.append(ToolUseContent(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        input=args,
                    ))
                except (KeyError, json.JSONDecodeError):
                    continue

        # Extract usage
        if "usage" in response:
            usage = Usage(
                input_tokens=response["usage"].get("prompt_tokens", 0),
                output_tokens=response["usage"].get("completion_tokens", 0),
            )

        return text, tool_uses, usage

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
    ) -> List[ToolUseContent]:
        """Convert accumulated tool call deltas to content blocks"""
        blocks = []
        logger.debug(f"Converting {len(tool_calls)} tool call deltas to content blocks")
        for tc in tool_calls:
            logger.debug(f"  Delta: id={tc.id}, name={tc.name}, args_len={len(tc.arguments)}")
            if tc.id and tc.name:
                try:
                    args = json.loads(tc.arguments) if tc.arguments else {}
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse tool call arguments: {e}, arguments: {tc.arguments}")
                    args = {}

                logger.debug(f"  Tool call: {tc.name}, id: {tc.id}, args: {args}")
                blocks.append(ToolUseContent(
                    id=tc.id,
                    name=tc.name,
                    input=args,
                ))
            else:
                logger.warning(f"  Skipping incomplete tool call: id={tc.id}, name={tc.name}")
        return blocks


class APIError(Exception):
    """Base exception for API errors"""
    pass


class APINetworkError(APIError):
    """Exception for network-related errors (connection, timeout, etc.)"""
    pass


class APIResponseError(APIError):
    """Exception for invalid API responses"""
    pass

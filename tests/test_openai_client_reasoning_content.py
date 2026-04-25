from __future__ import annotations

from cc_code.core.messages import Message, TextContent, ThinkingContent, ToolUseContent
from cc_code.services.openai_client import OpenAIClient, OpenAIClientConfig


def _build_client() -> OpenAIClient:
    return OpenAIClient(
        OpenAIClientConfig(
            api_url="https://api.example.com/v1",
            api_key="test-key",
            model_name="deepseek-v4-pro",
            model_id="deepseek-v4-pro",
        )
    )


def test_convert_messages_preserves_reasoning_for_tool_continuation() -> None:
    client = _build_client()
    messages = [
        Message.user_message("What's the weather tomorrow?"),
        Message.assistant_message(
            [
                ThinkingContent(thinking="Need to call the weather tool first."),
                ToolUseContent(
                    id="call_1",
                    name="get_weather",
                    input={"location": "Hangzhou", "date": "2026-04-26"},
                ),
            ]
        ),
        Message.tool_result_message("call_1", "Cloudy"),
    ]

    payload = client._convert_messages_to_openai_format(messages)

    assert payload[1]["role"] == "assistant"
    assert payload[1]["reasoning_content"] == "Need to call the weather tool first."
    assert payload[1]["tool_calls"][0]["function"]["name"] == "get_weather"


def test_convert_messages_drops_reasoning_after_user_turn_boundary() -> None:
    client = _build_client()
    messages = [
        Message.user_message("Solve 9.11 vs 9.8"),
        Message.assistant_message(
            [
                ThinkingContent(thinking="Compare the decimals carefully."),
                TextContent(text="9.8 is greater."),
            ]
        ),
        Message.user_message("Explain that again."),
    ]

    payload = client._convert_messages_to_openai_format(messages)

    assert payload[1]["role"] == "assistant"
    assert "reasoning_content" not in payload[1]


def test_convert_messages_keeps_reasoning_for_future_turn_after_tool_turn() -> None:
    client = _build_client()
    messages = [
        Message.user_message("Use the tool."),
        Message.assistant_message(
            [
                ThinkingContent(thinking="I should call the tool."),
                ToolUseContent(id="call_1", name="echo_hello", input={}),
            ]
        ),
        Message.tool_result_message("call_1", "hello"),
        Message.assistant_message(
            [
                ThinkingContent(thinking="The tool returned hello."),
                TextContent(text="The tool said hello."),
            ]
        ),
        Message.user_message("Repeat it."),
    ]

    payload = client._convert_messages_to_openai_format(messages)

    assert payload[1]["reasoning_content"] == "I should call the tool."
    assert payload[3]["reasoning_content"] == "The tool returned hello."


def test_parse_stream_chunk_accepts_reasoning_alias() -> None:
    client = _build_client()
    text, thinking, tool_calls = client.parse_stream_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "reasoning": "Need the tool first.",
                        "tool_calls": None,
                    }
                }
            ]
        }
    )

    assert text == ""
    assert thinking == "Need the tool first."
    assert tool_calls == []

"""Tests for core functionality"""

import asyncio
from pathlib import Path

import pytest
from claude_code.core.messages import (
    Message,
    MessageCompleteEvent,
    MessageRole,
    TextContent,
    TextEvent,
    ThinkingContent,
    ThinkingEvent,
    ToolResultEvent,
    ToolUseEvent,
    ToolUseContent,
    ToolResultContent,
    TurnCompleteEvent,
    generate_uuid,
)
from claude_code.core.query_engine import QueryConfig, QueryEngine
from claude_code.core.tools import (
    BaseTool,
    ToolRegistry,
    ToolContext,
    ToolInputSchema,
)
from claude_code.services.openai_client import OpenAIClientConfig
from claude_code.tools import (
    ReadTool,
    WriteTool,
    EditTool,
    GlobTool,
    GrepTool,
)
from claude_code.tools.bash_tool import BashTool


class FakeStreamingClient:
    """Minimal streaming client that reuses the production chunk parsers."""

    def __init__(self, chunks):
        self._chunks = chunks

    async def close(self) -> None:
        """Match the real client interface."""

    async def chat_completion(self, *_args, **_kwargs):
        for chunk in self._chunks:
            yield chunk

    def parse_stream_chunk(self, chunk):
        from claude_code.services.openai_client import OpenAIClient

        return OpenAIClient.parse_stream_chunk(self, chunk)

    def accumulate_tool_calls(self, accumulated, new_deltas):
        from claude_code.services.openai_client import OpenAIClient

        return OpenAIClient.accumulate_tool_calls(self, accumulated, new_deltas)

    def tool_calls_to_content_blocks(self, tool_calls, allow_partial=False):
        from claude_code.services.openai_client import OpenAIClient

        return OpenAIClient.tool_calls_to_content_blocks(
            self,
            tool_calls,
            allow_partial=allow_partial,
        )

    def partial_tool_calls_to_content_blocks(self, tool_calls):
        from claude_code.services.openai_client import OpenAIClient

        return OpenAIClient.partial_tool_calls_to_content_blocks(self, tool_calls)

    def _parse_tool_call_arguments(self, arguments, allow_partial=False):
        from claude_code.services.openai_client import OpenAIClient

        return OpenAIClient._parse_tool_call_arguments(
            self,
            arguments,
            allow_partial=allow_partial,
        )

    def _extract_partial_string_fields(self, arguments):
        from claude_code.services.openai_client import OpenAIClient

        return OpenAIClient._extract_partial_string_fields(self, arguments)


class TestMessages:
    """Test message types"""

    def test_user_message_creation(self):
        """Test creating a user message"""
        msg = Message.user_message("Hello, world!")
        assert msg.type == MessageRole.USER
        assert msg.get_text() == "Hello, world!"

    def test_assistant_message_creation(self):
        """Test creating an assistant message"""
        content = [TextContent(text="Hello!")]
        msg = Message.assistant_message(content)
        assert msg.type == MessageRole.ASSISTANT
        assert msg.get_text() == "Hello!"

    def test_tool_result_message(self):
        """Test creating a tool result message"""
        msg = Message.tool_result_message("tool-123", "Success", is_error=False)
        assert msg.type == MessageRole.TOOL
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], ToolResultContent)

    def test_message_with_tool_uses(self):
        """Test message with tool uses"""
        content = [
            TextContent(text="Let me help you."),
            ToolUseContent(
                id="tool-1", name="Read", input={"file_path": "/tmp/test.txt"}
            ),
        ]
        msg = Message.assistant_message(content)
        assert msg.has_tool_uses()
        tool_uses = msg.get_tool_uses()
        assert len(tool_uses) == 1
        assert tool_uses[0].name == "Read"

    def test_uuid_generation(self):
        """Test UUID generation"""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        assert uuid1 != uuid2
        assert len(uuid1) == 36  # Standard UUID format


class TestToolRegistry:
    """Test tool registry"""

    def test_registry_creation(self):
        """Test creating a tool registry"""
        registry = ToolRegistry()
        assert len(registry.list_tools()) == 0

    def test_tool_registration(self):
        """Test registering tools"""
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(WriteTool())

        tools = registry.list_tools()
        assert len(tools) == 2

    def test_get_tool_by_name(self):
        """Test getting tool by name"""
        registry = ToolRegistry()
        registry.register(ReadTool())

        tool = registry.get("Read")
        assert tool is not None
        assert tool.name == "Read"

        # Test alias
        tool = registry.get("read")
        assert tool is not None

    def test_tool_definitions(self):
        """Test getting tool definitions"""
        registry = ToolRegistry()
        registry.register(ReadTool())

        definitions = registry.get_tool_definitions()
        assert len(definitions) == 1
        assert definitions[0]["type"] == "function"
        assert definitions[0]["function"]["name"] == "Read"


class TestToolContext:
    """Test tool context"""

    def test_context_creation(self):
        """Test creating tool context"""
        ctx = ToolContext(
            working_directory="/tmp",
            project_root="/tmp",
            session_id="test-session",
        )
        assert ctx.working_directory == "/tmp"
        assert ctx.get_cwd() == "/tmp"


class TestFileTools:
    """Test file tools"""

    def test_read_tool_properties(self):
        """Test Read tool properties"""
        tool = ReadTool()
        assert tool.name == "Read"
        assert tool.is_read_only({}) is True
        assert tool.is_concurrency_safe({}) is True

    def test_write_tool_properties(self):
        """Test Write tool properties"""
        tool = WriteTool()
        assert tool.name == "Write"
        assert tool.is_read_only({}) is False
        assert tool.is_destructive({}) is True

    def test_edit_tool_properties(self):
        """Test Edit tool properties"""
        tool = EditTool()
        assert tool.name == "Edit"
        assert tool.is_read_only({}) is False
        assert tool.is_destructive({}) is True

    def test_glob_tool_properties(self):
        """Test Glob tool properties"""
        tool = GlobTool()
        assert tool.name == "Glob"
        assert tool.is_read_only({}) is True

    def test_grep_tool_properties(self):
        """Test Grep tool properties"""
        tool = GrepTool()
        assert tool.name == "Grep"
        assert tool.is_read_only({}) is True

    def test_file_and_search_tools_classify_error_results(self):
        """Read/Write/Edit/Glob/Grep should expose consistent error classification."""
        assert ReadTool().is_error_result("Error: File does not exist: /tmp/missing.txt")
        assert not ReadTool().is_error_result(
            "File: /tmp/demo.txt\nLines: 1-1 of 1\n\n     1\thello"
        )

        assert WriteTool().is_error_result("Error writing file: disk full")
        assert not WriteTool().is_error_result(
            "Successfully wrote to /tmp/demo.txt (1 lines, 5 bytes)"
        )

        assert EditTool().is_error_result("Error: Could not find the specified text in /tmp/demo.py")
        assert not EditTool().is_error_result(
            "Successfully edited /tmp/demo.py (replaced 1 occurrence)"
        )

        assert GlobTool().is_error_result("Error searching files: permission denied")
        assert not GlobTool().is_error_result("No files found matching pattern: *.py")
        assert not GlobTool().is_error_result("Found 2 files matching '*.py':\nmain.py\napp.py")

        grep_tool = GrepTool()
        assert grep_tool.is_error_result(
            "Error searching content: ripgrep failed",
            {"output_mode": "files_with_matches"},
        )
        assert not grep_tool.is_error_result(
            "Found 2 files\nREADME.md\nsrc/app.py",
            {"output_mode": "files_with_matches"},
        )
        assert not grep_tool.is_error_result(
            "src/app.py:12:Error: expected config",
            {"output_mode": "content"},
        )


class TestBashTool:
    """Test Bash tool"""

    def test_bash_tool_properties(self):
        """Test Bash tool properties"""
        tool = BashTool()
        assert tool.name == "Bash"
        assert tool.is_read_only({"command": "ls"}) is True
        assert tool.is_read_only({"command": "rm file"}) is False

    def test_is_silent_command(self):
        """Test silent command detection"""
        from claude_code.tools.bash_tool import is_silent_command

        assert is_silent_command("rm file") is True
        assert is_silent_command("ls") is False

    def test_is_search_command(self):
        """Test search command detection"""
        from claude_code.tools.bash_tool import is_search_command

        assert is_search_command("grep pattern file") is True
        assert is_search_command("find . -name '*.py'") is True
        assert is_search_command("cat file") is False

    def test_bash_tool_classifies_nonzero_exit_as_error(self):
        """Non-zero exit codes and timeouts should render as errors."""
        tool = BashTool()
        assert tool.is_error_result("Exit code: 127\n\n[stderr]\n/bin/bash: conda: command not found")
        assert tool.is_error_result("Command timed out after 2.0 seconds\n\nCommand: sleep 10")
        assert tool.is_error_result("Error executing command: boom")
        assert not tool.is_error_result("Done")
        assert not tool.is_error_result("(No output)")
        assert not tool.is_error_result("[stderr]\nwarning only")

    def test_bash_tool_raises_cancelled_error_when_query_is_interrupted(self):
        """Cancellation should stop long-running shell commands instead of leaving them detached."""
        async def run_test() -> None:
            tool = BashTool()
            cancel_event = asyncio.Event()
            context = ToolContext(
                working_directory=".",
                project_root=".",
                session_id="test-session",
                cancel_event=cancel_event,
            )

            async def trigger_cancel() -> None:
                await asyncio.sleep(0.05)
                cancel_event.set()

            asyncio.create_task(trigger_cancel())

            with pytest.raises(asyncio.CancelledError):
                await tool.call({"command": "sleep 5"}, context)

        asyncio.run(run_test())


class ErrorReportingTool(BaseTool):
    """Minimal tool used to verify QueryEngine propagates tool error flags."""

    name = "Explode"
    description = "Synthetic failing tool"
    input_schema = ToolInputSchema()
    aliases = []

    async def call(self, input, context) -> str:
        return "synthetic failure"

    def is_error_result(self, result: str, input=None) -> bool:
        return result == "synthetic failure"


class TestToolInputSchema:
    """Test tool input schema"""

    def test_schema_creation(self):
        """Test creating input schema"""
        schema = ToolInputSchema(
            properties={
                "file_path": {
                    "type": "string",
                    "description": "Path to file",
                },
            },
            required=["file_path"],
        )
        assert schema.type == "object"
        assert "file_path" in schema.properties
        assert "file_path" in schema.required

    def test_schema_to_dict(self):
        """Test schema to dict conversion"""
        schema = ToolInputSchema(
            properties={"path": {"type": "string"}},
            required=["path"],
        )
        d = schema.to_dict()
        assert d["type"] == "object"
        assert "properties" in d
        assert "required" in d


def test_query_engine_streams_tool_preview_before_large_write_finishes(tmp_path):
    """Large streamed tool inputs should surface a preview before the full tool JSON completes."""

    async def run_test():
        registry = ToolRegistry()
        registry.register(WriteTool())

        output_path = tmp_path / "demo.txt"
        output_path_json = str(output_path).replace("\\", "\\\\")
        chunks = [
            {
                "choices": [
                    {
                        "delta": {"content": "I am "},
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "tool-1",
                                    "type": "function",
                                    "function": {
                                        "name": "Write",
                                        "arguments": (
                                            f'{{"file_path":"{output_path_json}","content":"'
                                        ),
                                    },
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {"content": "writing the file"},
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": 'hello world"}'},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        ]

        engine = QueryEngine(
            OpenAIClientConfig(
                api_url="http://localhost/v1",
                api_key="test-key",
                model_name="test-model",
            ),
            registry,
            QueryConfig(max_turns=1, stream=True, working_directory=str(tmp_path)),
        )
        engine._client = FakeStreamingClient(chunks)
        engine._is_initialized = True

        events = [event async for event in engine.submit_message("write a file")]
        return events, output_path

    events, output_path = asyncio.run(run_test())

    text_events = [event for event in events if isinstance(event, TextEvent)]
    assert [event.text for event in text_events] == ["I am ", "writing the file"]

    tool_use_event = next(event for event in events if isinstance(event, ToolUseEvent))
    assistant_message_event = next(
        event
        for event in events
        if isinstance(event, MessageCompleteEvent)
        and event.message
        and event.message.type == MessageRole.ASSISTANT
    )
    turn_event = next(event for event in events if isinstance(event, TurnCompleteEvent))

    assert events.index(tool_use_event) < events.index(assistant_message_event)
    assert tool_use_event.input == {"file_path": str(output_path)}
    assert assistant_message_event.message.get_text() == "I am writing the file"
    assert assistant_message_event.message.get_tool_uses()[0].input == {
        "file_path": str(output_path),
        "content": "hello world",
    }
    assert turn_event.turn == 1
    assert output_path.read_text() == "hello world"


def test_query_engine_streams_thinking_before_text():
    """Test that reasoning_content is parsed and emitted as ThinkingEvent."""

    async def run_test():
        registry = ToolRegistry()

        chunks = [
            {
                "choices": [
                    {
                        "delta": {"reasoning_content": "Let me think..."},
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {"reasoning_content": " step by step."},
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {"content": "The answer is 42."},
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ]
            },
        ]

        import tempfile

        with tempfile.TemporaryDirectory() as tmp_path:
            engine = QueryEngine(
                OpenAIClientConfig(
                    api_url="http://localhost/v1",
                    api_key="test-key",
                    model_name="test-model",
                ),
                registry,
                QueryConfig(max_turns=1, stream=True, working_directory=tmp_path),
            )
            engine._client = FakeStreamingClient(chunks)
            engine._is_initialized = True

            events = [event async for event in engine.submit_message("question")]
            return events

    events = asyncio.run(run_test())

    thinking_events = [event for event in events if isinstance(event, ThinkingEvent)]
    text_events = [event for event in events if isinstance(event, TextEvent)]

    assert len(thinking_events) == 2
    assert thinking_events[0].thinking == "Let me think..."
    assert thinking_events[1].thinking == " step by step."

    assert len(text_events) == 1
    assert text_events[0].text == "The answer is 42."

    assistant_message_event = next(
        event
        for event in events
        if isinstance(event, MessageCompleteEvent)
        and event.message
        and event.message.type == MessageRole.ASSISTANT
    )

    thinking_blocks = [
        block
        for block in assistant_message_event.message.content
        if isinstance(block, ThinkingContent)
    ]
    text_blocks = [
        block
        for block in assistant_message_event.message.content
        if isinstance(block, TextContent)
    ]

    assert len(thinking_blocks) == 1
    assert thinking_blocks[0].thinking == "Let me think... step by step."
    assert len(text_blocks) == 1
    assert text_blocks[0].text == "The answer is 42."


def test_query_engine_marks_tool_results_as_errors_when_tool_reports_failure():
    """ToolResultEvent and stored tool messages should preserve tool-level failures."""

    async def run_test():
        registry = ToolRegistry()
        registry.register(ErrorReportingTool())

        chunks = [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "tool-1",
                                    "type": "function",
                                    "function": {
                                        "name": "Explode",
                                        "arguments": "{}",
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        ]

        engine = QueryEngine(
            OpenAIClientConfig(
                api_url="http://localhost/v1",
                api_key="test-key",
                model_name="test-model",
            ),
            registry,
            QueryConfig(max_turns=1, stream=True),
        )
        engine._client = FakeStreamingClient(chunks)
        engine._is_initialized = True
        return [event async for event in engine.submit_message("run it")]

    events = asyncio.run(run_test())

    tool_result_event = next(event for event in events if isinstance(event, ToolResultEvent))
    assert tool_result_event.result == "synthetic failure"
    assert tool_result_event.is_error is True

    tool_message_event = next(
        event
        for event in events
        if isinstance(event, MessageCompleteEvent)
        and event.message
        and event.message.type == MessageRole.TOOL
    )
    tool_result_block = tool_message_event.message.content[0]
    assert isinstance(tool_result_block, ToolResultContent)
    assert tool_result_block.is_error is True


def test_query_engine_snapshot_rolls_back_partial_assistant_turn():
    """Rollback should preserve the submitted user message while dropping partial assistant/tool state."""
    engine = QueryEngine(
        OpenAIClientConfig(
            api_url="http://localhost/v1",
            api_key="test-key",
            model_name="test-model",
        ),
        ToolRegistry(),
        QueryConfig(max_turns=1, stream=True),
    )

    previous_message = Message.user_message("previous")
    current_user_message = Message.user_message("current")
    partial_assistant = Message.assistant_message(
        [
            ThinkingContent(thinking="plan"),
            ToolUseContent(
                id="tool-1",
                name="Bash",
                input={"command": "sleep 5"},
            ),
        ]
    )

    engine.state.add_message(previous_message)
    snapshot = engine.create_state_snapshot()
    engine.state.add_message(current_user_message)
    engine.state.add_message(partial_assistant)

    engine.rollback_to_snapshot(
        snapshot,
        message_count=snapshot.message_count + 1,
    )

    assert engine.get_messages() == [previous_message, current_user_message]


def test_query_engine_rollback_restores_file_overwritten_by_write_tool(tmp_path: Path):
    """Rollback should restore the previous file bytes for completed Write tool calls."""
    file_path = tmp_path / "demo.txt"
    file_path.write_text("before", encoding="utf-8")

    engine = QueryEngine(
        OpenAIClientConfig(
            api_url="http://localhost/v1",
            api_key="test-key",
            model_name="test-model",
        ),
        ToolRegistry(),
        QueryConfig(max_turns=1, stream=True),
    )

    snapshot = engine.create_state_snapshot()

    asyncio.run(
        WriteTool().call(
            {"file_path": str(file_path), "content": "after"},
            engine._get_tool_context(),
        )
    )

    assert file_path.read_text(encoding="utf-8") == "after"

    engine.rollback_to_snapshot(snapshot)

    assert file_path.read_text(encoding="utf-8") == "before"


def test_query_engine_rollback_deletes_new_file_created_by_write_tool(tmp_path: Path):
    """Rollback should remove files that only exist because of the current Write tool call."""
    file_path = tmp_path / "created.txt"

    engine = QueryEngine(
        OpenAIClientConfig(
            api_url="http://localhost/v1",
            api_key="test-key",
            model_name="test-model",
        ),
        ToolRegistry(),
        QueryConfig(max_turns=1, stream=True),
    )

    snapshot = engine.create_state_snapshot()

    asyncio.run(
        WriteTool().call(
            {"file_path": str(file_path), "content": "hello"},
            engine._get_tool_context(),
        )
    )

    assert file_path.read_text(encoding="utf-8") == "hello"

    engine.rollback_to_snapshot(snapshot)

    assert not file_path.exists()


def test_query_engine_rollback_restores_file_modified_by_edit_tool(tmp_path: Path):
    """Rollback should restore the previous file contents for completed Edit tool calls."""
    file_path = tmp_path / "demo.py"
    file_path.write_text("value = 1\n", encoding="utf-8")

    engine = QueryEngine(
        OpenAIClientConfig(
            api_url="http://localhost/v1",
            api_key="test-key",
            model_name="test-model",
        ),
        ToolRegistry(),
        QueryConfig(max_turns=1, stream=True),
    )

    snapshot = engine.create_state_snapshot()

    asyncio.run(
        EditTool().call(
            {
                "file_path": str(file_path),
                "old_string": "value = 1",
                "new_string": "value = 2",
            },
            engine._get_tool_context(),
        )
    )

    assert file_path.read_text(encoding="utf-8") == "value = 2\n"

    engine.rollback_to_snapshot(snapshot)

    assert file_path.read_text(encoding="utf-8") == "value = 1\n"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

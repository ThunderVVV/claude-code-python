"""Tests for core functionality"""

import pytest
from claude_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ToolUseContent,
    ToolResultContent,
    generate_uuid,
)
from claude_code.core.tools import (
    ToolRegistry,
    ToolContext,
    ToolInputSchema,
)
from claude_code.tools.file_tools import (
    ReadTool,
    WriteTool,
    EditTool,
    GlobTool,
    GrepTool,
)
from claude_code.tools.bash_tool import BashTool


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
            ToolUseContent(id="tool-1", name="Read", input={"file_path": "/tmp/test.txt"}),
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

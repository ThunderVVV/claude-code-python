
"""Tool system base classes and interfaces - aligned with TypeScript version"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, TypeVar, Generic, runtime_checkable


@dataclass
class ToolInputSchema:
    """JSON Schema for tool input validation"""
    type: str = "object"
    properties: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    additional_properties: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
        }


@dataclass
class PermissionResult:
    """Result of a permission check"""
    behavior: str = "allow"  # allow, deny, ask
    message: Optional[str] = None
    updated_input: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of input validation"""
    result: bool = True
    message: Optional[str] = None
    error_code: int = 0


@dataclass
class ToolContext:
    """Context passed to tools during execution"""
    working_directory: str
    project_root: str
    session_id: str
    permissions: Dict[str, bool] = field(default_factory=dict)

    def get_cwd(self) -> str:
        """Get current working directory"""
        return self.working_directory


@runtime_checkable
class ToolProtocol(Protocol):
    """Protocol defining the interface all tools must implement"""
    name: str
    description: str
    input_schema: ToolInputSchema

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        """Execute the tool with given input and context"""
        ...

    def is_enabled(self) -> bool:
        """Check if tool is enabled"""
        ...


T = TypeVar('T')


class BaseTool(ABC):
    """Abstract base class for tools - aligned with TypeScript Tool interface"""

    name: str
    description: str
    input_schema: ToolInputSchema
    aliases: List[str] = field(default_factory=list)
    max_result_size_chars: int = 100_000

    def __init__(self):
        if not hasattr(self, "name"):
            raise NotImplementedError("Tool must have a 'name' attribute")
        if not hasattr(self, "description"):
            raise NotImplementedError("Tool must have a 'description' attribute")
        if not hasattr(self, "input_schema"):
            self.input_schema = ToolInputSchema()

    @abstractmethod
    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        """Execute the tool"""
        pass

    def is_enabled(self) -> bool:
        """Check if tool is enabled (default: True)"""
        return True

    def is_read_only(self, input: Dict[str, Any]) -> bool:
        """Check if this tool use is read-only"""
        return False

    def is_concurrency_safe(self, input: Dict[str, Any]) -> bool:
        """Check if this tool can run concurrently with other tools"""
        return False

    def is_destructive(self, input: Dict[str, Any]) -> bool:
        """Check if this tool performs irreversible operations"""
        return False

    async def check_permissions(
        self,
        input: Dict[str, Any],
        context: ToolContext,
    ) -> PermissionResult:
        """Check if this tool use is allowed"""
        return PermissionResult(behavior="allow", updated_input=input)

    async def validate_input(
        self,
        input: Dict[str, Any],
        context: ToolContext,
    ) -> ValidationResult:
        """Validate tool input"""
        return ValidationResult(result=True)

    def get_path(self, input: Dict[str, Any]) -> Optional[str]:
        """Get file path if this tool operates on a file"""
        return None

    def user_facing_name(self, input: Optional[Dict[str, Any]] = None) -> str:
        """Get human-readable name for the tool"""
        return self.name

    def get_tool_use_summary(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get a short summary of this tool use for display"""
        return None

    def get_activity_description(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get present-tense activity description for spinner"""
        return None

    def to_openai_tool(self) -> Dict[str, Any]:
        """Convert to OpenAI tool format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema.to_dict(),
            },
        }


class ToolRegistry:
    """Registry for managing available tools"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool"""
        self._tools[tool.name] = tool
        # Also register aliases
        for alias in getattr(tool, 'aliases', []):
            self._tools[alias] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool"""
        if name in self._tools:
            del self._tools[name]

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name or alias"""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """List all registered tools"""
        # Return unique tools only (not aliases)
        seen = set()
        result = []
        for tool in self._tools.values():
            if tool.name not in seen:
                seen.add(tool.name)
                result.append(tool)
        return result

    def list_enabled_tools(self) -> List[BaseTool]:
        """List all enabled tools"""
        return [tool for tool in self.list_tools() if tool.is_enabled()]

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for OpenAI API"""
        return [tool.to_openai_tool() for tool in self.list_enabled_tools()]

    def tool_matches_name(self, tool: BaseTool, name: str) -> bool:
        """Check if tool matches name (including aliases)"""
        if tool.name == name:
            return True
        return name in getattr(tool, 'aliases', [])

    def find_tool_by_name(self, name: str) -> Optional[BaseTool]:
        """Find a tool by name or alias"""
        return self.get(name)


def tool_matches_name(tool: BaseTool, name: str) -> bool:
    """Check if tool matches name (including aliases)"""
    return tool.name == name or name in getattr(tool, 'aliases', [])


def find_tool_by_name(tools: List[BaseTool], name: str) -> Optional[BaseTool]:
    """Find a tool by name from a list"""
    for tool in tools:
        if tool_matches_name(tool, name):
            return tool
    return None


# Global registry instance
registry = ToolRegistry()

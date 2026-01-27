"""Tool module registry for Om Apex MCP Server."""

from dataclasses import dataclass, field
from typing import Callable, Awaitable, Optional

from mcp.types import Tool, TextContent


@dataclass
class ToolModule:
    """A module of related MCP tools."""
    tools: list[Tool]
    handler: Callable[[str, dict], Awaitable[Optional[list[TextContent]]]]
    reading_tools: list[str] = field(default_factory=list)
    writing_tools: list[str] = field(default_factory=list)

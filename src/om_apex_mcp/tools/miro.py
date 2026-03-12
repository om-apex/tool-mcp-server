"""Miro board management tools: create, list, and delete boards.

Provides MCP tools for Miro board lifecycle operations via the REST API v2.
Complements the official @llmindset/mcp-miro plugin which handles content
creation (diagrams, tables, docs) but lacks board management.
"""

import json

from mcp.types import Tool, TextContent

from . import ToolModule
from ..miro_client import is_miro_available, create_board, list_boards, delete_board


READING = ["list_boards"]
WRITING = ["create_board", "delete_board"]


def _json_response(data) -> list[TextContent]:
    """Return data as formatted JSON TextContent."""
    return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


def register() -> ToolModule:
    tools = [
        Tool(
            name="create_board",
            description="Create a new Miro board. Returns the board ID, name, and URL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name for the new board"},
                    "description": {"type": "string", "description": "Optional board description"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="list_boards",
            description="List Miro boards accessible to the authenticated user. Supports search and pagination.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Optional search query to filter boards by name"},
                    "limit": {"type": "integer", "description": "Max boards to return (default 50)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="delete_board",
            description="Delete a Miro board by its ID. Returns confirmation of deletion.",
            inputSchema={
                "type": "object",
                "properties": {
                    "board_id": {"type": "string", "description": "The ID of the board to delete"},
                },
                "required": ["board_id"],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "create_board":
            return await _handle_create_board(arguments)
        elif name == "list_boards":
            return await _handle_list_boards(arguments)
        elif name == "delete_board":
            return await _handle_delete_board(arguments)
        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )


# =============================================================================
# Handler implementations
# =============================================================================

async def _handle_create_board(arguments: dict) -> list[TextContent]:
    if not is_miro_available():
        return [TextContent(type="text", text="Miro is not configured. Set MIRO_OAUTH_TOKEN in environment or config/.env.miro.")]

    try:
        result = await create_board(
            name=arguments["name"],
            description=arguments.get("description", ""),
        )
        return _json_response(result)
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating board: {e}")]


async def _handle_list_boards(arguments: dict) -> list[TextContent]:
    if not is_miro_available():
        return [TextContent(type="text", text="Miro is not configured. Set MIRO_OAUTH_TOKEN in environment or config/.env.miro.")]

    try:
        result = await list_boards(
            query=arguments.get("query", ""),
            limit=arguments.get("limit", 50),
        )
        return _json_response(result)
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing boards: {e}")]


async def _handle_delete_board(arguments: dict) -> list[TextContent]:
    if not is_miro_available():
        return [TextContent(type="text", text="Miro is not configured. Set MIRO_OAUTH_TOKEN in environment or config/.env.miro.")]

    try:
        success = await delete_board(board_id=arguments["board_id"])
        if success:
            return [TextContent(type="text", text=json.dumps({"deleted": True, "board_id": arguments["board_id"]}, indent=2))]
        else:
            return [TextContent(type="text", text=json.dumps({"deleted": False, "board_id": arguments["board_id"], "note": "Unexpected response status"}, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error deleting board: {e}")]

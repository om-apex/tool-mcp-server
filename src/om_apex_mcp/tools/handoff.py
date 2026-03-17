"""Session handoff tools: save, history.

Saves session handoffs to history and retrieves them per project.
Local handoff.md files are the primary handoff mechanism; this is the archive.
"""

import json
import logging
import traceback

from mcp.types import Tool, TextContent

from . import ToolModule
from ..supabase_client import (
    is_supabase_available,
    save_session_handoff as sb_save_handoff,
    get_handoff_history as sb_get_history,
)

logger = logging.getLogger("om-apex-mcp")

READING = ["get_handoff_history"]
WRITING = ["save_session_handoff"]


def register() -> ToolModule:
    tools = [
        Tool(
            name="get_handoff_history",
            description=(
                "Get previous session handoffs from history for a project. "
                "Optionally filter by created_by to retrieve entries from a specific "
                "instance or person (e.g., 'Nishad-2'). "
                "Useful for instance-aware context when multiple Claude instances are running."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_code": {
                        "type": "string",
                        "description": "Project code to filter by (e.g., 'ai-quorum', 'mcp-server')",
                    },
                    "created_by": {
                        "type": "string",
                        "description": "Filter to only return handoffs by this instance/person (e.g., 'Nishad-2')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of records to return (default: 5)",
                    },
                },
                "required": ["project_code"],
            },
        ),
        Tool(
            name="save_session_handoff",
            description=(
                "Save a session handoff to history. Inserts directly into history table. "
                "Include: current state, deployment status, last session summary, active work by person, "
                "blockers, key constants, recent decisions, git status, and system improvements."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "person": {
                        "type": "string",
                        "description": "Who is writing this handoff: Nishad or Sumedha",
                    },
                    "interface": {
                        "type": "string",
                        "description": "Which Claude interface: code, code-app, chat, or cowork",
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Full markdown handoff content. Should include sections: "
                            "Current State, Deployment Status, Last Session Summary, "
                            "Active Work by Person, Blockers, Key Constants, "
                            "Recent Decisions, Git Status, System Improvements (if any)"
                        ),
                    },
                    "project_code": {
                        "type": "string",
                        "description": "Project code for this handoff (e.g., 'ai-quorum', 'mcp-server')",
                    },
                },
                "required": ["person", "interface", "content", "project_code"],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "get_handoff_history":
            try:
                if not is_supabase_available():
                    return [TextContent(
                        type="text",
                        text="Handoff history unavailable (Supabase offline).",
                    )]

                project_code = arguments["project_code"]
                limit = arguments.get("limit", 5)
                created_by = arguments.get("created_by")
                records = sb_get_history(project_code=project_code, limit=limit, created_by=created_by)

                if not records:
                    filter_note = f" for '{created_by}'" if created_by else ""
                    return [TextContent(
                        type="text",
                        text=f"No handoff history found for project '{project_code}'{filter_note}.",
                    )]

                lines = []
                filter_note = f" (filtered by: {created_by})" if created_by else ""
                lines.append(f"Handoff history for '{project_code}' — {len(records)} record(s){filter_note}:\n")
                for i, record in enumerate(records, 1):
                    meta = (
                        f"[{i}] Created: {record.get('created_at', 'unknown')} | "
                        f"By: {record.get('created_by', 'unknown')} | "
                        f"Via: {record.get('interface', 'unknown')}"
                    )
                    content = record.get("content", "").strip()
                    lines.append(f"{meta}\n{content}\n")

                return [TextContent(type="text", text="\n".join(lines))]
            except Exception as e:
                logger.error(f"Error in get_handoff_history: {e}")
                logger.error(f"Traceback:\n{traceback.format_exc()}")
                return [TextContent(type="text", text=f"Error fetching handoff history: {e}")]

        elif name == "save_session_handoff":
            try:
                person = arguments.get("person", "Unknown")
                interface = arguments.get("interface", "unknown")
                content = arguments.get("content", "")
                project_code = arguments["project_code"]

                if not content:
                    return [TextContent(type="text", text="Error: content is required")]

                if not is_supabase_available():
                    return [TextContent(
                        type="text",
                        text="Cannot save handoff (Supabase offline). "
                             "Save content to .pending-sync.md in git and sync later.",
                    )]

                result = sb_save_handoff(content, person, interface, project_code)
                return [TextContent(
                    type="text",
                    text=f"Session handoff saved to history.\n"
                         f"- Project: {project_code}\n"
                         f"- By: {person}\n"
                         f"- Via: {interface}",
                )]
            except Exception as e:
                logger.error(f"Error in save_session_handoff: {e}")
                logger.error(f"Traceback:\n{traceback.format_exc()}")
                return [TextContent(type="text", text=f"Error saving handoff: {e}")]

        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )

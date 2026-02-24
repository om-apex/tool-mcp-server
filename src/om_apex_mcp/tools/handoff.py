"""Session handoff tools: get, save.

Provides instant cross-laptop session context sync via Supabase.
Both Nishad (Mac) and Sumedha (Windows) read/write the same handoff record.
"""

import json
import logging
import traceback

from mcp.types import Tool, TextContent

from . import ToolModule
from ..supabase_client import (
    is_supabase_available,
    get_session_handoff as sb_get_handoff,
    save_session_handoff as sb_save_handoff,
    get_handoff_history as sb_get_history,
)

logger = logging.getLogger("om-apex-mcp")

READING = ["get_session_handoff", "get_handoff_history"]
WRITING = ["save_session_handoff"]


def register() -> ToolModule:
    tools = [
        Tool(
            name="get_session_handoff",
            description=(
                "Get the current session handoff — the primary context file for session start. "
                "Returns current state, deployment status, active work by person, blockers, "
                "key constants, and next steps. Call this FIRST at every session start."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_handoff_history",
            description=(
                "Get previous session handoffs from history. "
                "Optionally filter by created_by to retrieve entries from a specific "
                "instance or person (e.g., 'Nishad-2'). "
                "Useful for instance-aware context when multiple Claude instances are running."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "created_by": {
                        "type": "string",
                        "description": "Filter to only return handoffs by this instance/person (e.g., 'Nishad-2')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of records to return (default: 5)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="save_session_handoff",
            description=(
                "Save the session handoff at session end. Archives the previous handoff to history. "
                "Include: current state, deployment status, last session summary, active work by person, "
                "blockers, key constants, recent decisions, git status, and system improvements. "
                "Use checkpoint=true for lightweight mid-session saves (skips history archive)."
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
                    "checkpoint": {
                        "type": "boolean",
                        "description": (
                            "If true, save as a mid-session checkpoint (no history archive). "
                            "Use for context compaction protection. Default: false."
                        ),
                    },
                },
                "required": ["person", "interface", "content"],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "get_session_handoff":
            try:
                if not is_supabase_available():
                    return [TextContent(
                        type="text",
                        text="Session handoff unavailable (Supabase offline). "
                             "Falling back: call get_full_context + get_daily_progress instead.",
                    )]

                handoff = sb_get_handoff()
                if handoff:
                    content = handoff.get("content", "")
                    meta = (
                        f"Last updated: {handoff.get('updated_at', 'unknown')} | "
                        f"By: {handoff.get('created_by', 'unknown')} | "
                        f"Via: {handoff.get('interface', 'unknown')}"
                    )
                    return [TextContent(type="text", text=f"{meta}\n\n{content}")]
                else:
                    return [TextContent(
                        type="text",
                        text="No session handoff found. This is the first session with the new system. "
                             "Fall back to get_full_context + get_daily_progress for context. "
                             "Write a handoff at session end using save_session_handoff.",
                    )]
            except Exception as e:
                logger.error(f"Error in get_session_handoff: {e}")
                logger.error(f"Traceback:\n{traceback.format_exc()}")
                return [TextContent(type="text", text=f"Error getting handoff: {e}")]

        elif name == "get_handoff_history":
            try:
                if not is_supabase_available():
                    return [TextContent(
                        type="text",
                        text="Handoff history unavailable (Supabase offline).",
                    )]

                limit = arguments.get("limit", 5)
                created_by = arguments.get("created_by")
                records = sb_get_history(limit=limit, created_by=created_by)

                if not records:
                    filter_note = f" for '{created_by}'" if created_by else ""
                    return [TextContent(
                        type="text",
                        text=f"No handoff history found{filter_note}.",
                    )]

                lines = []
                filter_note = f" (filtered by: {created_by})" if created_by else ""
                lines.append(f"Handoff history — {len(records)} record(s){filter_note}:\n")
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
                checkpoint = arguments.get("checkpoint", False)

                if not content:
                    return [TextContent(type="text", text="Error: content is required")]

                if not is_supabase_available():
                    return [TextContent(
                        type="text",
                        text="Cannot save handoff (Supabase offline). "
                             "Save content to .pending-sync.md in git and sync later.",
                    )]

                result = sb_save_handoff(content, person, interface, checkpoint=checkpoint)
                if checkpoint:
                    return [TextContent(
                        type="text",
                        text=f"Checkpoint handoff saved (no history archive).\n"
                             f"- By: {person}\n"
                             f"- Via: {interface}\n"
                             f"- Purpose: context compaction protection.",
                    )]
                return [TextContent(
                    type="text",
                    text=f"Session handoff saved successfully.\n"
                         f"- By: {person}\n"
                         f"- Via: {interface}\n"
                         f"- Previous handoff archived to history.\n"
                         f"- Next session will load this handoff automatically.",
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

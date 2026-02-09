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

READING = ["get_session_handoff"]
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
            name="save_session_handoff",
            description=(
                "Save the session handoff at session end. Archives the previous handoff to history. "
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

        elif name == "save_session_handoff":
            try:
                person = arguments.get("person", "Unknown")
                interface = arguments.get("interface", "unknown")
                content = arguments.get("content", "")

                if not content:
                    return [TextContent(type="text", text="Error: content is required")]

                if not is_supabase_available():
                    return [TextContent(
                        type="text",
                        text="Cannot save handoff (Supabase offline). "
                             "Save content to .pending-sync.md in git and sync later.",
                    )]

                result = sb_save_handoff(content, person, interface)
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

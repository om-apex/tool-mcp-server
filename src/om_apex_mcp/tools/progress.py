"""Daily progress tools: get, add, search."""

import json
import logging
import re
from datetime import datetime

from mcp.types import Tool, TextContent

from . import ToolModule
from .helpers import get_backend, DAILY_PROGRESS_REL

logger = logging.getLogger("om-apex-mcp")

READING = ["get_daily_progress", "search_daily_progress"]
WRITING = ["add_daily_progress"]


def register() -> ToolModule:
    tools = [
        Tool(
            name="get_daily_progress",
            description="Get the daily progress log for a specific date",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format (e.g., '2026-01-21')"},
                },
                "required": ["date"],
            },
        ),
        Tool(
            name="add_daily_progress",
            description="Add a session entry to the daily progress log. Creates file if it doesn't exist for today. Uses structured data to build consistent markdown formatting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Who is logging this session: Nishad or Sumedha"},
                    "interface": {"type": "string", "description": "Which Claude interface: code, cowork, chat, or code-app"},
                    "title": {"type": "string", "description": "Brief title for this session (e.g., 'MCP Server Setup')"},
                    "completed": {"type": "array", "items": {"type": "string"}, "description": "List of items completed during the session"},
                    "decisions": {"type": "array", "items": {"type": "string"}, "description": "List of decisions recorded (format: 'ID: Description')"},
                    "tasks_completed": {"type": "array", "items": {"type": "string"}, "description": "List of tasks marked complete (format: 'ID: Description')"},
                    "tasks_created": {"type": "array", "items": {"type": "string"}, "description": "List of new tasks created (format: 'ID: Description')"},
                    "files_modified": {"type": "array", "items": {"type": "string"}, "description": "List of files created/modified (format: 'path - description')"},
                    "notes": {"type": "array", "items": {"type": "string"}, "description": "Additional notes for future reference"},
                },
                "required": ["person", "interface", "title"],
            },
        ),
        Tool(
            name="search_daily_progress",
            description="Search through all daily progress logs for relevant content. Returns matching file contents for Claude to analyze semantically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_text": {"type": "string", "description": "Text to search for in daily progress logs"},
                    "limit": {"type": "integer", "description": "Maximum number of files to return (default: 10)"},
                },
                "required": ["search_text"],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        backend = get_backend()

        if name == "get_daily_progress":
            date = arguments["date"]

            # Try exact match
            exact_path = f"{DAILY_PROGRESS_REL}/{date}.md"
            content = backend.read_text(exact_path)
            if content is not None:
                return [TextContent(type="text", text=content)]

            # Try fuzzy match via listing
            files = backend.list_files(DAILY_PROGRESS_REL, f"{date}*.md")
            if files:
                content = backend.read_text(files[0])
                if content is not None:
                    filename = files[0].rsplit("/", 1)[-1]
                    return [TextContent(type="text", text=f"File: {filename}\n\n{content}")]

            return [TextContent(type="text", text=f"No daily progress log found for {date}")]

        elif name == "add_daily_progress":
            person = arguments["person"]
            interface = arguments["interface"].lower()
            title = arguments["title"]

            today = datetime.now().strftime("%Y-%m-%d")
            timestamp = datetime.now().strftime("%I:%M %p EST").lstrip("0")

            filepath = f"{DAILY_PROGRESS_REL}/{today}.md"

            session_num = 1
            existing_content = backend.read_text(filepath)

            if existing_content:
                session_matches = re.findall(r"## Session (\d+)", existing_content)
                if session_matches:
                    session_num = max(int(n) for n in session_matches) + 1

            session_parts = []
            session_parts.append(f"\n---\n")
            session_parts.append(f"\n## Session {session_num} ({interface}) (by {person}) ({timestamp}) - {title}\n")

            completed = arguments.get("completed", [])
            if completed:
                session_parts.append("\n### Completed\n")
                for item in completed:
                    session_parts.append(f"- {item}\n")

            decisions = arguments.get("decisions", [])
            if decisions:
                session_parts.append("\n### Decisions Recorded\n")
                for item in decisions:
                    if ":" in item:
                        parts = item.split(":", 1)
                        session_parts.append(f"- **{parts[0]}**: {parts[1].strip()}\n")
                    else:
                        session_parts.append(f"- **{item}**\n")

            tasks_completed = arguments.get("tasks_completed", [])
            if tasks_completed:
                session_parts.append("\n### Tasks Completed\n")
                for item in tasks_completed:
                    if ":" in item:
                        parts = item.split(":", 1)
                        session_parts.append(f"- **{parts[0]}**: {parts[1].strip()}\n")
                    else:
                        session_parts.append(f"- **{item}**\n")

            tasks_created = arguments.get("tasks_created", [])
            if tasks_created:
                session_parts.append("\n### Tasks Created\n")
                for item in tasks_created:
                    if ":" in item:
                        parts = item.split(":", 1)
                        session_parts.append(f"- **{parts[0]}**: {parts[1].strip()}\n")
                    else:
                        session_parts.append(f"- **{item}**\n")

            files_modified = arguments.get("files_modified", [])
            if files_modified:
                session_parts.append("\n### Files Created/Modified\n")
                for item in files_modified:
                    session_parts.append(f"- {item}\n")

            notes = arguments.get("notes", [])
            if notes:
                session_parts.append("\n### Notes\n")
                for item in notes:
                    session_parts.append(f"- {item}\n")

            session_entry = "".join(session_parts)

            if existing_content:
                backend.append_text(filepath, session_entry)
            else:
                file_header = f"# Daily Progress - {today}\n"
                backend.write_text(filepath, file_header + session_entry)

            filename = filepath.rsplit("/", 1)[-1]
            return [TextContent(type="text", text=f"Daily progress logged successfully:\n- File: {filename}\n- Session: {session_num}\n- Person: {person}\n- Interface: {interface}\n- Title: {title}")]

        elif name == "search_daily_progress":
            search_text = arguments["search_text"].lower()
            limit = arguments.get("limit", 10)

            md_files = backend.list_files(DAILY_PROGRESS_REL, "*.md")

            if not md_files:
                return [TextContent(type="text", text=f"No daily progress logs found")]

            results = []
            for filepath in md_files[:limit * 2]:
                try:
                    content = backend.read_text(filepath)
                    if content is None:
                        continue

                    if search_text in content.lower():
                        filename = filepath.rsplit("/", 1)[-1]
                        stem = filename.rsplit(".", 1)[0]
                        results.append({
                            "file": filename,
                            "date": stem.split("_")[0] if "_" in stem else stem,
                            "content": content
                        })

                        if len(results) >= limit:
                            break
                except Exception as e:
                    logger.error(f"Error reading {filepath}: {e}")
                    continue

            if not results:
                results = []
                for filepath in md_files[:limit]:
                    try:
                        content = backend.read_text(filepath)
                        if content is None:
                            continue
                        filename = filepath.rsplit("/", 1)[-1]
                        stem = filename.rsplit(".", 1)[0]
                        results.append({
                            "file": filename,
                            "date": stem.split("_")[0] if "_" in stem else stem,
                            "content": content
                        })
                    except Exception:
                        continue

                return [TextContent(type="text", text=f"No exact matches for '{search_text}'. Returning {len(results)} recent logs for semantic analysis:\n\n" + json.dumps(results, indent=2))]

            return [TextContent(type="text", text=f"Found {len(results)} matching logs:\n\n" + json.dumps(results, indent=2))]

        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )

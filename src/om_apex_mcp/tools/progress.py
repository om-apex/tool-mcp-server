"""Daily progress tools: get, add, search."""

import json
import logging
import re
from datetime import datetime

from mcp.types import Tool, TextContent

from . import ToolModule
from .helpers import DAILY_PROGRESS_DIR

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
        if name == "get_daily_progress":
            date = arguments["date"]

            if not DAILY_PROGRESS_DIR.exists():
                return [TextContent(type="text", text=f"Daily Progress directory not found: {DAILY_PROGRESS_DIR}")]

            exact_file = DAILY_PROGRESS_DIR / f"{date}.md"
            if exact_file.exists():
                with open(exact_file, "r", encoding="utf-8") as f:
                    content = f.read()
                return [TextContent(type="text", text=content)]

            matching_files = list(DAILY_PROGRESS_DIR.glob(f"{date}*.md"))
            if matching_files:
                with open(matching_files[0], "r", encoding="utf-8") as f:
                    content = f.read()
                return [TextContent(type="text", text=f"File: {matching_files[0].name}\n\n{content}")]

            return [TextContent(type="text", text=f"No daily progress log found for {date}")]

        elif name == "add_daily_progress":
            person = arguments["person"]
            interface = arguments["interface"].lower()
            title = arguments["title"]

            DAILY_PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

            today = datetime.now().strftime("%Y-%m-%d")
            timestamp = datetime.now().strftime("%I:%M %p EST").lstrip("0")

            filepath = DAILY_PROGRESS_DIR / f"{today}.md"

            session_num = 1
            existing_content = ""

            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    existing_content = f.read()
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
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(session_entry)
            else:
                file_header = f"# Daily Progress - {today}\n"
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(file_header + session_entry)

            return [TextContent(type="text", text=f"Daily progress logged successfully:\n- File: {filepath.name}\n- Session: {session_num}\n- Person: {person}\n- Interface: {interface}\n- Title: {title}")]

        elif name == "search_daily_progress":
            search_text = arguments["search_text"].lower()
            limit = arguments.get("limit", 10)

            if not DAILY_PROGRESS_DIR.exists():
                return [TextContent(type="text", text=f"Daily Progress directory not found: {DAILY_PROGRESS_DIR}")]

            md_files = sorted(DAILY_PROGRESS_DIR.glob("*.md"), reverse=True)

            results = []
            for filepath in md_files[:limit * 2]:
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    if search_text in content.lower():
                        results.append({
                            "file": filepath.name,
                            "date": filepath.stem.split("_")[0] if "_" in filepath.stem else filepath.stem,
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
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                        results.append({
                            "file": filepath.name,
                            "date": filepath.stem.split("_")[0] if "_" in filepath.stem else filepath.stem,
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

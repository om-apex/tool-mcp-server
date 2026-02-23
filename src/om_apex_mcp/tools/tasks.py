"""Task management tools: get, add, complete, update_status, update.

NOTE: As of Feb 2026, all task operations use Supabase as the single source of truth.
The JSON fallback has been removed. If Supabase is not available, operations will fail
with a clear error message.
"""

import json
import re
from datetime import datetime

from mcp.types import Tool, TextContent

from . import ToolModule
from ..supabase_client import (
    is_supabase_available,
    get_tasks as sb_get_tasks,
    get_task_queue as sb_get_task_queue,
    add_task as sb_add_task,
    update_task as sb_update_task,
    get_next_task_id,
)


READING = ["get_pending_tasks", "get_task_queue"]
WRITING = ["add_task", "complete_task", "update_task_status", "update_task"]


def _require_supabase() -> None:
    """Ensure Supabase is available. Raises RuntimeError if not."""
    if not is_supabase_available():
        raise RuntimeError(
            "Supabase is not available. Task operations require Supabase. "
            "Check that .env.supabase.omapex-dashboard exists at ~/om-apex/config/ "
            "and contains SUPABASE_URL and SUPABASE_SERVICE_KEY."
        )


def register() -> ToolModule:
    tools = [
        Tool(
            name="get_pending_tasks",
            description="Get all pending tasks across Om Apex Holdings companies",
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Filter by company name (optional)"},
                    "category": {"type": "string", "description": "Filter by category (optional)"},
                    "status": {"type": "string", "description": "Filter by status: pending, in_progress, completed (optional)"},
                    "owner": {"type": "string", "description": "Filter by owner name (e.g., Nishad, Sumedha, Both, Claude, Scroggin, etc.)"},
                    "task_type": {"type": "string", "description": "Filter by task type: issue, dev, manual (optional)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_task_queue",
            description="Get a compact task listing: id, truncated description (80 chars), priority, status, owner, company. Sorted by priority (High→Medium→Low) then age (oldest first). Default limit 10.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max tasks to return (default 10)"},
                    "owner": {"type": "string", "description": "Filter by owner name (optional)"},
                    "priority": {"type": "string", "description": "Filter by priority: High, Medium, Low (optional)"},
                    "status": {"type": "string", "description": "Filter by status: pending, in_progress (optional, defaults to both)"},
                    "company": {"type": "string", "description": "Filter by company name (optional)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="add_task",
            description="Add a new task to the pending tasks list. Owner can be specified in parentheses at end of description, e.g. 'Build website (Sumedha)' or 'Call attorney (Scroggin)'",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Description of the task. Include owner in parentheses at end, e.g. 'Build website (Sumedha)' or 'Follow up on quote (Scroggin)'"},
                    "category": {"type": "string", "description": "Category: Technical, Marketing, Legal, Operations, Administrative, Content"},
                    "company": {"type": "string", "description": "Company: Om Apex Holdings, Om Luxe Properties, Om AI Solutions, Om Supply Chain"},
                    "priority": {"type": "string", "description": "Priority: High, Medium, Low"},
                    "notes": {"type": "string", "description": "Additional notes (optional)"},
                    "task_type": {"type": "string", "description": "Task type: issue (from GitHub issue), dev (development work), manual (default). Default: manual", "enum": ["issue", "dev", "manual"]},
                    "commit_refs": {"type": "array", "items": {"type": "string"}, "description": "Git commit SHAs associated with this task (optional)"},
                    "issue_ref": {"type": "string", "description": "GitHub issue reference, e.g. 'om-apex/repo#123' (optional)"},
                },
                "required": ["description", "category", "company", "priority"],
            },
        ),
        Tool(
            name="complete_task",
            description="Mark a task as completed with optional completion notes",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The task ID (e.g., TASK-001)"},
                    "notes": {"type": "string", "description": "Completion notes - what was done, outcome, follow-up needed (optional)"},
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="update_task_status",
            description="Update the status of a task",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The task ID (e.g., TASK-001)"},
                    "status": {"type": "string", "description": "New status: pending, in_progress, completed"},
                },
                "required": ["task_id", "status"],
            },
        ),
        Tool(
            name="update_task",
            description="Update any field of an existing task (description, notes, priority, category, company, owner)",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The task ID (e.g., TASK-001)"},
                    "description": {"type": "string", "description": "New description for the task (optional)"},
                    "notes": {"type": "string", "description": "New or updated notes (optional)"},
                    "priority": {"type": "string", "description": "New priority: High, Medium, Low (optional)"},
                    "category": {"type": "string", "description": "New category: Technical, Marketing, Legal, Operations, Administrative, Content (optional)"},
                    "company": {"type": "string", "description": "New company: Om Apex Holdings, Om Luxe Properties, Om AI Solutions, Om Supply Chain (optional)"},
                    "owner": {"type": "string", "description": "New owner name (optional)"},
                },
                "required": ["task_id"],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "get_pending_tasks":
            _require_supabase()
            tasks = sb_get_tasks(
                company=arguments.get("company"),
                category=arguments.get("category"),
                status=arguments.get("status"),
                owner=arguments.get("owner"),
                task_type=arguments.get("task_type"),
            )
            return [TextContent(type="text", text=json.dumps(tasks, indent=2))]

        elif name == "get_task_queue":
            _require_supabase()
            tasks = sb_get_task_queue(
                limit=arguments.get("limit", 10),
                owner=arguments.get("owner"),
                priority=arguments.get("priority"),
                status=arguments.get("status"),
                company=arguments.get("company"),
            )
            if not tasks:
                return [TextContent(type="text", text="Task Queue: No tasks found.")]
            lines = [f"Task Queue ({len(tasks)} tasks):"]
            for t in tasks:
                owner_str = f" @{t['owner']}" if t.get("owner") else ""
                company_str = f" [{t['company']}]" if t.get("company") else ""
                lines.append(
                    f"{t['id']} [{t.get('priority', '?')}] ({t.get('status', '?')}) "
                    f"{t.get('description', '')}{owner_str}{company_str}"
                )
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "add_task":
            _require_supabase()
            description = arguments["description"]
            owner = None
            owner_match = re.search(r'\(([A-Za-z]+)\)\s*$', description)
            if owner_match:
                owner = owner_match.group(1).capitalize()
                description = re.sub(r'\s*\([A-Za-z]+\)\s*$', '', description)

            new_id = get_next_task_id()
            new_task = {
                "id": new_id,
                "description": description,
                "category": arguments["category"],
                "company": arguments["company"],
                "priority": arguments["priority"],
                "status": "pending",
                "created_at": datetime.now().isoformat(),
            }
            if owner:
                new_task["owner"] = owner
            if arguments.get("notes"):
                new_task["notes"] = arguments["notes"]
            if arguments.get("task_type"):
                new_task["task_type"] = arguments["task_type"]
            if arguments.get("commit_refs"):
                new_task["commit_refs"] = arguments["commit_refs"]
            if arguments.get("issue_ref"):
                new_task["issue_ref"] = arguments["issue_ref"]

            result = sb_add_task(new_task)
            return [TextContent(type="text", text=f"Task created successfully:\n{json.dumps(result, indent=2)}")]

        elif name == "complete_task":
            _require_supabase()
            task_id = arguments["task_id"]
            completion_notes = arguments.get("notes")

            # First get the existing task to merge notes
            existing_tasks = sb_get_tasks()
            existing_task = next((t for t in existing_tasks if t.get("id") == task_id), None)

            if not existing_task:
                return [TextContent(type="text", text=f"Task {task_id} not found")]

            updates = {
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            if completion_notes:
                existing_notes = existing_task.get("notes", "") or ""
                if existing_notes:
                    updates["completion_notes"] = completion_notes
                    updates["notes"] = f"{existing_notes}\n\n[Completed] {completion_notes}"
                else:
                    updates["completion_notes"] = completion_notes
                    updates["notes"] = f"[Completed] {completion_notes}"

            result = sb_update_task(task_id, updates)
            if result:
                return [TextContent(type="text", text=f"Task {task_id} marked as completed:\n{json.dumps(result, indent=2)}")]
            return [TextContent(type="text", text=f"Task {task_id} not found")]

        elif name == "update_task_status":
            _require_supabase()
            task_id = arguments["task_id"]
            new_status = arguments["status"]

            if new_status not in ["pending", "in_progress", "completed"]:
                return [TextContent(type="text", text=f"Invalid status: {new_status}. Must be pending, in_progress, or completed")]

            updates = {
                "status": new_status,
                "updated_at": datetime.now().isoformat(),
            }
            if new_status == "completed":
                updates["completed_at"] = datetime.now().isoformat()

            result = sb_update_task(task_id, updates)
            if result:
                return [TextContent(type="text", text=f"Task {task_id} status updated to {new_status}:\n{json.dumps(result, indent=2)}")]
            return [TextContent(type="text", text=f"Task {task_id} not found")]

        elif name == "update_task":
            _require_supabase()
            task_id = arguments["task_id"]

            updates = {}
            updated_fields = []

            if arguments.get("description"):
                updates["description"] = arguments["description"]
                updated_fields.append("description")
            if arguments.get("notes"):
                updates["notes"] = arguments["notes"]
                updated_fields.append("notes")
            if arguments.get("priority"):
                if arguments["priority"] not in ["High", "Medium", "Low"]:
                    return [TextContent(type="text", text=f"Invalid priority: {arguments['priority']}. Must be High, Medium, or Low")]
                updates["priority"] = arguments["priority"]
                updated_fields.append("priority")
            if arguments.get("category"):
                updates["category"] = arguments["category"]
                updated_fields.append("category")
            if arguments.get("company"):
                updates["company"] = arguments["company"]
                updated_fields.append("company")
            if arguments.get("owner"):
                updates["owner"] = arguments["owner"]
                updated_fields.append("owner")

            if not updates:
                return [TextContent(type="text", text=f"No updates provided for task {task_id}")]

            updates["updated_at"] = datetime.now().isoformat()
            result = sb_update_task(task_id, updates)

            if result:
                return [TextContent(type="text", text=f"Task {task_id} updated successfully.\nUpdated fields: {', '.join(updated_fields)}\n\n{json.dumps(result, indent=2)}")]
            return [TextContent(type="text", text=f"Task {task_id} not found")]

        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )

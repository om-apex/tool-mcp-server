"""Task management tools: get, add, complete, update_status, update, force_complete.

NOTE: As of Feb 2026, all task operations use Supabase as the single source of truth.
The JSON fallback has been removed. If Supabase is not available, operations will fail
with a clear error message.

Updated Mar 2026: 12-status lifecycle (added assigned-to-claude, notes-prd-unclear),
source tracking, planning artifact paths, approval tracking, force_complete tool.
"""

import json
import re
from datetime import datetime

from mcp.types import Tool, TextContent

from . import ToolModule
from ..supabase_client import (
    is_supabase_available,
    get_tasks as sb_get_tasks,
    get_task_by_id as sb_get_task_by_id,
    get_task_queue as sb_get_task_queue,
    add_task as sb_add_task,
    update_task as sb_update_task,
    get_next_task_id,
    resolve_project_code,
)


VALID_STATUSES = [
    "created", "assigned-to-claude", "notes-prd-unclear",
    "approved-for-prd", "prd-to-review", "ready-to-plan",
    "planning-in-progress", "plan-to-review", "ready-to-code",
    "coding-in-progress", "ready-for-manual-review", "complete",
]

VALID_SOURCES = ["nishad", "user-report", "claude-code", "sentry", "posthog"]

READING = ["get_pending_tasks", "get_task_queue"]
WRITING = ["add_task", "complete_task", "update_task_status", "update_task", "force_complete"]


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
            description="Get tasks with filters. At least one filter is required. Excludes complete tasks by default. Default limit 10, max 50.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Filter by company name (optional)"},
                    "category": {"type": "string", "description": "Filter by category (optional)"},
                    "status": {"type": "string", "description": "Filter by status: created, assigned-to-claude, notes-prd-unclear, approved-for-prd, prd-to-review, ready-to-plan, planning-in-progress, plan-to-review, ready-to-code, coding-in-progress, ready-for-manual-review, complete (optional, defaults to all non-complete)"},
                    "owner": {"type": "string", "description": "Filter by owner name (e.g., Nishad, Sumedha, Both, Claude, Scroggin, etc.)"},
                    "task_type": {"type": "string", "description": "Filter by task type: issue, dev, manual, enhancement, feature-request (optional)"},
                    "source": {"type": "string", "description": "Filter by source: nishad, user-report, claude-code, sentry, posthog (optional)"},
                    "search": {"type": "string", "description": "Text search across description and notes fields (optional)"},
                    "task_id": {"type": "string", "description": "Fetch a single task by exact ID, e.g. TASK-382 (bypasses other filters)"},
                    "limit": {"type": "integer", "description": "Max results to return (default 10, max 50)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_task_queue",
            description="Get a compact task listing grouped by project (top 2 per project, most recently updated first). Excludes 'manual' tasks by default. Returns: id, description (80 chars), priority, status, owner, project_code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max total tasks to return across all projects (default 10)"},
                    "owner": {"type": "string", "description": "Filter by owner name (optional)"},
                    "priority": {"type": "string", "description": "Filter by priority: High, Medium, Low (optional)"},
                    "status": {"type": "string", "description": "Filter by status: created, assigned-to-claude, notes-prd-unclear, approved-for-prd, prd-to-review, ready-to-plan, planning-in-progress, plan-to-review, ready-to-code, coding-in-progress, ready-for-manual-review, complete (optional, defaults to all non-complete)"},
                    "company": {"type": "string", "description": "Filter by company name (optional)"},
                    "source": {"type": "string", "description": "Filter by source: nishad, user-report, claude-code, sentry, posthog (optional)"},
                    "task_type": {"type": "string", "description": "Filter by task type: issue, dev, manual, enhancement, feature-request (optional). When omitted, 'manual' tasks are excluded by default."},
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
                    "task_type": {"type": "string", "description": "Task type: issue, dev, manual, enhancement, feature-request (default: manual)", "enum": ["issue", "dev", "manual", "enhancement", "feature-request"]},
                    "source": {"type": "string", "description": "Task source: nishad (default), user-report, claude-code, sentry, posthog"},
                    "prd_path": {"type": "string", "description": "Relative path to PRD file, e.g. 'docs/plans/TASK-nnn/PRD-nnn.md' (optional)"},
                    "commit_refs": {"type": "array", "items": {"type": "string"}, "description": "Git commit SHAs associated with this task (optional)"},
                    "issue_ref": {"type": "string", "description": "GitHub issue reference, e.g. 'om-apex/repo#123' (optional)"},
                    "project_code": {"type": "string", "description": "Project code (e.g., mcp-server, portal, ai-quorum, root). Required."},
                },
                "required": ["description", "category", "company", "priority", "project_code"],
            },
        ),
        Tool(
            name="complete_task",
            description="Mark a task as completed with optional completion notes. Task must be at 'ready-for-manual-review' status. Use force_complete for manual override.",
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
                    "status": {"type": "string", "description": "New status: created, assigned-to-claude, notes-prd-unclear, approved-for-prd, prd-to-review, ready-to-plan, planning-in-progress, plan-to-review, ready-to-code, coding-in-progress, ready-for-manual-review, complete"},
                },
                "required": ["task_id", "status"],
            },
        ),
        Tool(
            name="update_task",
            description="Update any field of an existing task (description, notes, priority, category, company, owner, prd_path, plan_folder, approved_by, approved_at)",
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
                    "prd_path": {"type": "string", "description": "Relative path to PRD file (optional)"},
                    "plan_folder": {"type": "string", "description": "Relative path to plan folder (optional)"},
                    "approved_by": {"type": "string", "description": "Name of approver (optional)"},
                    "approved_at": {"type": "string", "description": "Approval timestamp in ISO format (optional)"},
                    "project_code": {"type": "string", "description": "Project code to associate with task (e.g., mcp-server, portal, ai-quorum, root). Optional."},
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="force_complete",
            description="Force-complete any task regardless of current status. Bypasses prerequisite checks. For Owner Portal manual overrides only \u2014 Claude Code should use complete_task instead.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The task ID (e.g., TASK-001)"},
                    "notes": {"type": "string", "description": "Reason for force completion (optional)"},
                },
                "required": ["task_id"],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "get_pending_tasks":
            _require_supabase()

            # Enforce at least one filter
            filter_keys = ["company", "category", "status", "owner", "task_type", "source", "search", "task_id"]
            has_filter = any(arguments.get(k) for k in filter_keys)
            if not has_filter:
                return [TextContent(type="text", text=(
                    "Error: get_pending_tasks requires at least one filter. "
                    "Provide one or more of: status, company, owner, category, task_type, source, search, or task_id."
                ))]

            tasks = sb_get_tasks(
                company=arguments.get("company"),
                category=arguments.get("category"),
                status=arguments.get("status"),
                owner=arguments.get("owner"),
                task_type=arguments.get("task_type"),
                source=arguments.get("source"),
                limit=arguments.get("limit", 10),
                search=arguments.get("search"),
                task_id=arguments.get("task_id"),
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
                source=arguments.get("source"),
                task_type=arguments.get("task_type"),
            )
            if not tasks:
                return [TextContent(type="text", text="Task Queue: No tasks found.")]

            # Group output by project_code for readability
            projects_seen: dict[str, list[str]] = {}
            for t in tasks:
                project = t.get("project_code", "unassigned")
                owner_str = f" @{t['owner']}" if t.get("owner") else ""
                line = (
                    f"  {t['id']} [{t.get('priority', '?')}] ({t.get('status', '?')}) "
                    f"{t.get('description', '')}{owner_str}"
                )
                if project not in projects_seen:
                    projects_seen[project] = []
                projects_seen[project].append(line)

            # Build grouped output
            project_count = len(projects_seen)
            lines = [f"Task Queue ({len(tasks)} tasks across {project_count} projects):"]
            for project, task_lines in projects_seen.items():
                lines.append(f"[{project}]")
                lines.extend(task_lines)
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "add_task":
            _require_supabase()

            # Resolve project_code to UUID
            project_code = arguments["project_code"]
            try:
                project_id = resolve_project_code(project_code)
            except ValueError as e:
                return [TextContent(type="text", text=f"Error: {e}")]

            description = arguments["description"]
            owner = None
            owner_match = re.search(r'\(([A-Za-z]+)\)\s*$', description)
            if owner_match:
                owner = owner_match.group(1).capitalize()
                description = re.sub(r'\s*\([A-Za-z]+\)\s*$', '', description)

            task_type = arguments.get("task_type", "enhancement")
            new_id = get_next_task_id(task_type)
            new_task = {
                "id": new_id,
                "description": description,
                "category": arguments["category"],
                "company": arguments["company"],
                "priority": arguments["priority"],
                "status": "created",
                "created_at": datetime.now().isoformat(),
                "project_id": project_id,
            }
            if owner:
                new_task["owner"] = owner
            if arguments.get("notes"):
                new_task["notes"] = arguments["notes"]
            if task_type:
                new_task["task_type"] = task_type
            if arguments.get("source"):
                new_task["source"] = arguments["source"]
            if arguments.get("prd_path"):
                new_task["prd_path"] = arguments["prd_path"]
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

            # Get the existing task to check prerequisite and merge notes
            existing_task = sb_get_task_by_id(task_id)

            if not existing_task:
                return [TextContent(type="text", text=f"Task {task_id} not found")]

            # Enforce prerequisite: must be at ready-for-manual-review
            if existing_task.get("status") != "ready-for-manual-review":
                return [TextContent(type="text", text=(
                    f"Task {task_id} cannot be completed: status is '{existing_task.get('status')}', "
                    f"must be 'ready-for-manual-review'. Use force_complete for manual override."
                ))]

            updates = {
                "status": "complete",
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
                return [TextContent(type="text", text=f"Task {task_id} marked as complete:\n{json.dumps(result, indent=2)}")]
            return [TextContent(type="text", text=f"Task {task_id} not found")]

        elif name == "update_task_status":
            _require_supabase()
            task_id = arguments["task_id"]
            new_status = arguments["status"]

            if new_status not in VALID_STATUSES:
                return [TextContent(type="text", text=(
                    f"Invalid status: {new_status}. "
                    f"Must be one of: {', '.join(VALID_STATUSES)}"
                ))]

            updates = {
                "status": new_status,
                "updated_at": datetime.now().isoformat(),
            }
            if new_status == "complete":
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
            if arguments.get("prd_path"):
                updates["prd_path"] = arguments["prd_path"]
                updated_fields.append("prd_path")
            if arguments.get("plan_folder"):
                updates["plan_folder"] = arguments["plan_folder"]
                updated_fields.append("plan_folder")
            if arguments.get("approved_by"):
                updates["approved_by"] = arguments["approved_by"]
                updated_fields.append("approved_by")
            if arguments.get("approved_at"):
                updates["approved_at"] = arguments["approved_at"]
                updated_fields.append("approved_at")
            if arguments.get("project_code"):
                try:
                    project_uuid = resolve_project_code(arguments["project_code"])
                    updates["project_id"] = project_uuid
                    updated_fields.append("project_id")
                except ValueError as e:
                    return [TextContent(type="text", text=f"Error: {e}")]

            if not updates:
                return [TextContent(type="text", text=f"No updates provided for task {task_id}")]

            updates["updated_at"] = datetime.now().isoformat()
            result = sb_update_task(task_id, updates)

            if result:
                return [TextContent(type="text", text=f"Task {task_id} updated successfully.\nUpdated fields: {', '.join(updated_fields)}\n\n{json.dumps(result, indent=2)}")]
            return [TextContent(type="text", text=f"Task {task_id} not found")]

        elif name == "force_complete":
            _require_supabase()
            task_id = arguments["task_id"]
            force_notes = arguments.get("notes", "")

            existing_task = sb_get_task_by_id(task_id)

            if not existing_task:
                return [TextContent(type="text", text=f"Task {task_id} not found")]

            timestamp = datetime.now().isoformat()
            override_note = f"[Force Complete at {timestamp}]"
            if force_notes:
                override_note += f" {force_notes}"

            existing_notes = existing_task.get("notes", "") or ""
            new_notes = f"{existing_notes}\n\n{override_note}".strip() if existing_notes else override_note

            updates = {
                "status": "complete",
                "completed_at": timestamp,
                "updated_at": timestamp,
                "notes": new_notes,
                "completion_notes": force_notes or "Force completed via Owner Portal",
            }

            result = sb_update_task(task_id, updates)
            if result:
                return [TextContent(type="text", text=f"Task {task_id} force-completed:\n{json.dumps(result, indent=2)}")]
            return [TextContent(type="text", text=f"Task {task_id} not found")]

        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )

"""Task management tools: get, add, complete, update_status, update, force_complete,
advance_task, get_task_history, get_schedule.

NOTE: As of Feb 2026, all task operations use Supabase as the single source of truth.

Updated Mar 2026: 13-status lifecycle (added assigned-to-claude, notes-prd-unclear,
user-testing), source tracking, planning artifact paths, approval tracking,
force_complete, advance_task with history, get_schedule.
"""

import json
import re
from datetime import datetime

from mcp.types import Tool, TextContent

from . import ToolModule
from ..supabase_client import (
    is_supabase_available,
    get_supabase_client,
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
    "coding-in-progress", "ready-for-manual-review",
    "user-testing", "complete",
]

VALID_PRIORITIES = ["Critical", "High", "Medium", "Low"]

VALID_SOURCES = ["nishad", "user-report", "claude-code", "sentry", "posthog"]

# Status transition map: current_status -> list of (next_status, who_can_set)
STATUS_TRANSITIONS = {
    "created": [
        ("assigned-to-claude", "nishad"),
        ("approved-for-prd", "nishad"),
        ("planning-in-progress", "claude"),  # Source 2/4/6: issue-fixing takes over
    ],
    "assigned-to-claude": [
        ("coding-in-progress", "claude"),
        ("notes-prd-unclear", "claude"),
    ],
    "notes-prd-unclear": [
        ("assigned-to-claude", "nishad"),
        ("approved-for-prd", "nishad"),
    ],
    "approved-for-prd": [
        ("prd-to-review", "claude"),
    ],
    "prd-to-review": [
        ("ready-to-plan", "nishad"),
    ],
    "ready-to-plan": [
        ("planning-in-progress", "claude"),
    ],
    "planning-in-progress": [
        ("plan-to-review", "claude"),
    ],
    "plan-to-review": [
        ("ready-to-code", "nishad"),
    ],
    "ready-to-code": [
        ("coding-in-progress", "claude"),
    ],
    "coding-in-progress": [
        ("ready-for-manual-review", "claude"),
    ],
    "ready-for-manual-review": [
        ("user-testing", "nishad"),
        ("complete", "nishad"),
    ],
    "user-testing": [
        ("coding-in-progress", "claude"),  # Findings reported
        ("complete", "nishad"),            # Tests pass
    ],
}

READING = ["get_pending_tasks", "get_task_queue", "get_task_history", "get_schedule"]
WRITING = ["add_task", "complete_task", "update_task_status", "update_task",
           "force_complete", "advance_task"]


def _require_supabase() -> None:
    """Ensure Supabase is available. Raises RuntimeError if not."""
    if not is_supabase_available():
        raise RuntimeError(
            "Supabase is not available. Task operations require Supabase. "
            "Check that .env.supabase.omapex-dashboard exists at ~/om-apex/config/ "
            "and contains SUPABASE_URL and SUPABASE_SERVICE_KEY."
        )


def _record_status_change(task_id: str, from_status: str | None,
                          to_status: str, changed_by: str,
                          notes: str | None = None) -> dict | None:
    """Record a status change in task_status_history table."""
    client = get_supabase_client()
    if not client:
        return None

    record = {
        "task_id": task_id,
        "from_status": from_status,
        "to_status": to_status,
        "changed_by": changed_by,
        "notes": notes,
        "created_at": datetime.now().isoformat(),
    }

    # Calculate duration in previous status if we have history
    try:
        prev = (client.table("task_status_history")
                .select("created_at")
                .eq("task_id", task_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute())
        if prev.data:
            prev_time = datetime.fromisoformat(prev.data[0]["created_at"].replace("Z", "+00:00"))
            now = datetime.now().astimezone()
            duration = int((now - prev_time).total_seconds() / 60)
            record["duration_minutes"] = duration
    except Exception:
        pass  # Duration is optional

    try:
        result = client.table("task_status_history").insert(record).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None  # History recording is best-effort


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
                    "status": {"type": "string", "description": f"Filter by status: {', '.join(VALID_STATUSES)} (optional, defaults to all non-complete)"},
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
                    "priority": {"type": "string", "description": f"Filter by priority: {', '.join(VALID_PRIORITIES)} (optional)"},
                    "status": {"type": "string", "description": f"Filter by status: {', '.join(VALID_STATUSES)} (optional, defaults to all non-complete)"},
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
                    "priority": {"type": "string", "description": f"Priority: {', '.join(VALID_PRIORITIES)}"},
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
            description="Mark a task as completed with optional completion notes. Task must be at 'ready-for-manual-review' or 'user-testing' status. Use force_complete for manual override.",
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
                    "status": {"type": "string", "description": f"New status: {', '.join(VALID_STATUSES)}"},
                },
                "required": ["task_id", "status"],
            },
        ),
        Tool(
            name="update_task",
            description="Update any field of an existing task (description, notes, priority, category, company, owner, due, duration_days, prd_path, plan_folder, approved_by, approved_at)",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The task ID (e.g., TASK-001)"},
                    "description": {"type": "string", "description": "New description for the task (optional)"},
                    "notes": {"type": "string", "description": "New or updated notes (optional)"},
                    "priority": {"type": "string", "description": f"New priority: {', '.join(VALID_PRIORITIES)} (optional)"},
                    "category": {"type": "string", "description": "New category: Technical, Marketing, Legal, Operations, Administrative, Content (optional)"},
                    "company": {"type": "string", "description": "New company: Om Apex Holdings, Om Luxe Properties, Om AI Solutions, Om Supply Chain (optional)"},
                    "owner": {"type": "string", "description": "New owner name (optional)"},
                    "due": {"type": "string", "description": "Due date in YYYY-MM-DD format (optional)"},
                    "duration_days": {"type": "integer", "description": "Estimated duration in days (optional)"},
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
            description="Force-complete any task regardless of current status. Bypasses prerequisite checks. For Owner Portal manual overrides only — Claude Code should use complete_task instead.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The task ID (e.g., TASK-001)"},
                    "notes": {"type": "string", "description": "Reason for force completion (optional)"},
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="advance_task",
            description="Move a task to its next valid status based on workflow rules. Records status change history. Enforces approval gates and SDLC requirements.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The task ID (e.g., DEV-531)"},
                    "notes": {"type": "string", "description": "What was completed at this stage"},
                    "changed_by": {"type": "string", "description": "Who is advancing: 'claude' or 'nishad'", "enum": ["claude", "nishad"]},
                    "target_status": {"type": "string", "description": "Target status (optional — if omitted, auto-determines the next status). Required when multiple transitions are valid."},
                    "review_passed": {"type": "boolean", "description": "Required when advancing to ready-for-manual-review: confirms review skill was run"},
                    "docs_passed": {"type": "boolean", "description": "Required when advancing to ready-for-manual-review: confirms project-documentation skill was run"},
                },
                "required": ["task_id", "changed_by"],
            },
        ),
        Tool(
            name="get_task_history",
            description="Get the full status change history for a task, showing every transition with who changed it, when, and notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The task ID (e.g., DEV-531)"},
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="get_schedule",
            description="Get tasks with due dates for the next N days, grouped by date. Shows what's due today, tomorrow, this week.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_code": {"type": "string", "description": "Filter by project code (optional — omit for all projects)"},
                    "days": {"type": "integer", "description": "Number of days to look ahead (default 7, max 30)"},
                },
                "required": [],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "get_pending_tasks":
            _require_supabase()

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

            project_count = len(projects_seen)
            lines = [f"Task Queue ({len(tasks)} tasks across {project_count} projects):"]
            for project, task_lines in projects_seen.items():
                lines.append(f"[{project}]")
                lines.extend(task_lines)
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "add_task":
            _require_supabase()

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

            # Record initial status in history
            _record_status_change(new_id, None, "created", "system",
                                  f"Task created: {description[:80]}")

            return [TextContent(type="text", text=f"Task created successfully:\n{json.dumps(result, indent=2)}")]

        elif name == "complete_task":
            _require_supabase()
            task_id = arguments["task_id"]
            completion_notes = arguments.get("notes")

            existing_task = sb_get_task_by_id(task_id)
            if not existing_task:
                return [TextContent(type="text", text=f"Task {task_id} not found")]

            current_status = existing_task.get("status")
            if current_status not in ("ready-for-manual-review", "user-testing"):
                return [TextContent(type="text", text=(
                    f"Task {task_id} cannot be completed: status is '{current_status}', "
                    f"must be 'ready-for-manual-review' or 'user-testing'. Use force_complete for manual override."
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
                _record_status_change(task_id, current_status, "complete",
                                      "nishad", completion_notes)
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

            # Get current status for history
            existing = sb_get_task_by_id(task_id)
            old_status = existing.get("status") if existing else None

            updates = {
                "status": new_status,
                "updated_at": datetime.now().isoformat(),
            }
            if new_status == "complete":
                updates["completed_at"] = datetime.now().isoformat()

            result = sb_update_task(task_id, updates)
            if result:
                _record_status_change(task_id, old_status, new_status, "manual")
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
                if arguments["priority"] not in VALID_PRIORITIES:
                    return [TextContent(type="text", text=f"Invalid priority: {arguments['priority']}. Must be one of: {', '.join(VALID_PRIORITIES)}")]
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
            if arguments.get("due"):
                updates["due"] = arguments["due"]
                updated_fields.append("due")
            if arguments.get("duration_days") is not None:
                updates["duration_days"] = arguments["duration_days"]
                updated_fields.append("duration_days")
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

            old_status = existing_task.get("status")
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
                _record_status_change(task_id, old_status, "complete",
                                      "nishad", f"Force complete: {force_notes}")
                return [TextContent(type="text", text=f"Task {task_id} force-completed:\n{json.dumps(result, indent=2)}")]
            return [TextContent(type="text", text=f"Task {task_id} not found")]

        elif name == "advance_task":
            _require_supabase()
            task_id = arguments["task_id"]
            changed_by = arguments["changed_by"]
            notes = arguments.get("notes", "")
            target_status = arguments.get("target_status")
            review_passed = arguments.get("review_passed", False)
            docs_passed = arguments.get("docs_passed", False)

            existing = sb_get_task_by_id(task_id)
            if not existing:
                return [TextContent(type="text", text=f"Task {task_id} not found")]

            current_status = existing.get("status")
            transitions = STATUS_TRANSITIONS.get(current_status, [])

            if not transitions:
                return [TextContent(type="text", text=(
                    f"Task {task_id} at '{current_status}' has no valid next status. "
                    f"It may already be complete."
                ))]

            # Filter to transitions this actor can make
            valid = [(s, who) for s, who in transitions if who == changed_by]

            if not valid:
                # Show who CAN advance
                needed_by = set(who for _, who in transitions)
                return [TextContent(type="text", text=(
                    f"Task {task_id} at '{current_status}' cannot be advanced by {changed_by}. "
                    f"This transition requires: {', '.join(needed_by)}. "
                    f"Valid next statuses: {', '.join(s for s, _ in transitions)}"
                ))]

            # Determine target
            if target_status:
                match = [(s, who) for s, who in valid if s == target_status]
                if not match:
                    return [TextContent(type="text", text=(
                        f"Invalid target '{target_status}' for {changed_by}. "
                        f"Valid options from '{current_status}': {', '.join(s for s, _ in valid)}"
                    ))]
                next_status = target_status
            elif len(valid) == 1:
                next_status = valid[0][0]
            else:
                options = ", ".join(f"'{s}'" for s, _ in valid)
                return [TextContent(type="text", text=(
                    f"Task {task_id} at '{current_status}' has multiple valid next statuses for {changed_by}: {options}. "
                    f"Specify target_status to choose."
                ))]

            # SDLC gate enforcement for ready-for-manual-review
            if next_status == "ready-for-manual-review":
                if not review_passed:
                    return [TextContent(type="text", text=(
                        f"Cannot advance {task_id} to ready-for-manual-review: "
                        f"review_passed=true is required. Run review/SKILL.md first."
                    ))]
                if not docs_passed:
                    return [TextContent(type="text", text=(
                        f"Cannot advance {task_id} to ready-for-manual-review: "
                        f"docs_passed=true is required. Run project-documentation/SKILL.md first."
                    ))]

            # Execute the transition
            updates = {
                "status": next_status,
                "updated_at": datetime.now().isoformat(),
            }
            if next_status == "complete":
                updates["completed_at"] = datetime.now().isoformat()

            result = sb_update_task(task_id, updates)
            if result:
                _record_status_change(task_id, current_status, next_status,
                                      changed_by, notes)
                return [TextContent(type="text", text=(
                    f"Task {task_id} advanced: {current_status} -> {next_status}\n"
                    f"Changed by: {changed_by}\n"
                    f"Notes: {notes or '(none)'}\n\n"
                    f"{json.dumps(result, indent=2)}"
                ))]
            return [TextContent(type="text", text=f"Task {task_id} not found")]

        elif name == "get_task_history":
            _require_supabase()
            task_id = arguments["task_id"]

            client = get_supabase_client()
            if not client:
                return [TextContent(type="text", text="Supabase not available")]

            try:
                result = (client.table("task_status_history")
                          .select("*")
                          .eq("task_id", task_id)
                          .order("created_at")
                          .execute())

                if not result.data:
                    return [TextContent(type="text", text=f"No history found for {task_id}")]

                lines = [f"Status History for {task_id} ({len(result.data)} transitions):\n"]
                for h in result.data:
                    from_s = h.get("from_status") or "(created)"
                    to_s = h.get("to_status")
                    by = h.get("changed_by", "?")
                    at = h.get("created_at", "?")[:19]
                    dur = h.get("duration_minutes")
                    dur_str = f" ({dur}min in prev status)" if dur else ""
                    note = h.get("notes", "")
                    note_str = f"\n    Notes: {note}" if note else ""
                    lines.append(f"  {at} | {from_s} -> {to_s} | by {by}{dur_str}{note_str}")

                return [TextContent(type="text", text="\n".join(lines))]
            except Exception as e:
                return [TextContent(type="text", text=f"Error fetching history: {e}")]

        elif name == "get_schedule":
            _require_supabase()
            days = min(arguments.get("days", 7), 30)
            project_code = arguments.get("project_code")

            client = get_supabase_client()
            if not client:
                return [TextContent(type="text", text="Supabase not available")]

            try:
                from datetime import timedelta
                today = datetime.now().date()
                end_date = today + timedelta(days=days)

                query = (client.table("tasks")
                         .select("id, description, priority, status, due, owner, project_id")
                         .neq("status", "complete")
                         .not_.is_("due", "null")
                         .lte("due", end_date.isoformat())
                         .order("due"))

                result = query.execute()
                tasks = result.data or []

                # Filter by project if specified
                if project_code and tasks:
                    try:
                        project_uuid = resolve_project_code(project_code)
                        tasks = [t for t in tasks if t.get("project_id") == project_uuid]
                    except ValueError:
                        pass

                if not tasks:
                    return [TextContent(type="text", text=f"No tasks with due dates in the next {days} days.")]

                # Group by date
                from collections import defaultdict
                by_date: dict[str, list] = defaultdict(list)
                overdue = []

                for t in tasks:
                    due = t.get("due", "")
                    if due and due < today.isoformat():
                        overdue.append(t)
                    else:
                        by_date[due].append(t)

                lines = [f"Schedule — next {days} days ({len(tasks)} tasks):\n"]

                if overdue:
                    lines.append("OVERDUE:")
                    for t in overdue:
                        lines.append(f"  {t['id']} [{t.get('priority','?')}] ({t.get('status','?')}) due {t['due']} — {t.get('description','')[:60]}")
                    lines.append("")

                for date_str in sorted(by_date.keys()):
                    label = date_str
                    if date_str == today.isoformat():
                        label = f"{date_str} (TODAY)"
                    elif date_str == (today + timedelta(days=1)).isoformat():
                        label = f"{date_str} (TOMORROW)"
                    lines.append(f"{label}:")
                    for t in by_date[date_str]:
                        lines.append(f"  {t['id']} [{t.get('priority','?')}] ({t.get('status','?')}) — {t.get('description','')[:60]}")
                    lines.append("")

                return [TextContent(type="text", text="\n".join(lines))]
            except Exception as e:
                return [TextContent(type="text", text=f"Error fetching schedule: {e}")]

        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )

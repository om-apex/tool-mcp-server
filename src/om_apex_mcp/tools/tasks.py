"""Task management tools: get, add, complete, update_status, update."""

import json
import re
from datetime import datetime

from mcp.types import Tool, TextContent

from . import ToolModule
from .helpers import load_json, save_json


READING = ["get_pending_tasks"]
WRITING = ["add_task", "complete_task", "update_task_status", "update_task"]


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
            data = load_json("pending_tasks.json")
            tasks = data.get("tasks", [])

            company = arguments.get("company")
            category = arguments.get("category")
            status = arguments.get("status")
            owner = arguments.get("owner")

            if company:
                tasks = [t for t in tasks if t.get("company", "").lower() == company.lower()]
            if category:
                tasks = [t for t in tasks if t.get("category", "").lower() == category.lower()]
            if status:
                tasks = [t for t in tasks if t.get("status", "").lower() == status.lower()]
            if owner:
                tasks = [t for t in tasks if t.get("owner", "").lower() == owner.lower()]

            return [TextContent(type="text", text=json.dumps(tasks, indent=2))]

        elif name == "add_task":
            data = load_json("pending_tasks.json")
            tasks = data.get("tasks", [])

            existing_ids = [t.get("id", "") for t in tasks]
            max_num = 0
            for tid in existing_ids:
                if tid.startswith("TASK-"):
                    try:
                        max_num = max(max_num, int(tid.split("-")[1]))
                    except ValueError:
                        pass
            new_id = f"TASK-{max_num + 1:03d}"

            description = arguments["description"]
            owner = None
            owner_match = re.search(r'\(([A-Za-z]+)\)\s*$', description)
            if owner_match:
                owner = owner_match.group(1).capitalize()
                description = re.sub(r'\s*\([A-Za-z]+\)\s*$', '', description)

            new_task = {
                "id": new_id,
                "description": description,
                "category": arguments["category"],
                "company": arguments["company"],
                "priority": arguments["priority"],
                "status": "pending",
                "created": datetime.now().isoformat()
            }
            if owner:
                new_task["owner"] = owner
            if arguments.get("notes"):
                new_task["notes"] = arguments["notes"]

            tasks.append(new_task)
            data["tasks"] = tasks
            data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            save_json("pending_tasks.json", data)

            return [TextContent(type="text", text=f"Task created successfully:\n{json.dumps(new_task, indent=2)}")]

        elif name == "complete_task":
            data = load_json("pending_tasks.json")
            tasks = data.get("tasks", [])
            task_id = arguments["task_id"]
            completion_notes = arguments.get("notes")

            for task in tasks:
                if task.get("id") == task_id:
                    task["status"] = "completed"
                    task["completed_at"] = datetime.now().isoformat()
                    if completion_notes:
                        # Append to existing notes or create new
                        existing_notes = task.get("notes", "")
                        if existing_notes:
                            task["notes"] = f"{existing_notes}\n\n[Completed] {completion_notes}"
                        else:
                            task["notes"] = f"[Completed] {completion_notes}"
                    data["tasks"] = tasks
                    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
                    save_json("pending_tasks.json", data)
                    return [TextContent(type="text", text=f"Task {task_id} marked as completed:\n{json.dumps(task, indent=2)}")]

            return [TextContent(type="text", text=f"Task {task_id} not found")]

        elif name == "update_task_status":
            data = load_json("pending_tasks.json")
            tasks = data.get("tasks", [])
            task_id = arguments["task_id"]
            new_status = arguments["status"]

            if new_status not in ["pending", "in_progress", "completed"]:
                return [TextContent(type="text", text=f"Invalid status: {new_status}. Must be pending, in_progress, or completed")]

            for task in tasks:
                if task.get("id") == task_id:
                    task["status"] = new_status
                    if new_status == "completed":
                        task["completed_at"] = datetime.now().isoformat()
                    data["tasks"] = tasks
                    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
                    save_json("pending_tasks.json", data)
                    return [TextContent(type="text", text=f"Task {task_id} status updated to {new_status}:\n{json.dumps(task, indent=2)}")]

            return [TextContent(type="text", text=f"Task {task_id} not found")]

        elif name == "update_task":
            data = load_json("pending_tasks.json")
            tasks = data.get("tasks", [])
            task_id = arguments["task_id"]

            for task in tasks:
                if task.get("id") == task_id:
                    updates = []

                    if arguments.get("description"):
                        task["description"] = arguments["description"]
                        updates.append("description")
                    if arguments.get("notes"):
                        task["notes"] = arguments["notes"]
                        updates.append("notes")
                    if arguments.get("priority"):
                        if arguments["priority"] not in ["High", "Medium", "Low"]:
                            return [TextContent(type="text", text=f"Invalid priority: {arguments['priority']}. Must be High, Medium, or Low")]
                        task["priority"] = arguments["priority"]
                        updates.append("priority")
                    if arguments.get("category"):
                        task["category"] = arguments["category"]
                        updates.append("category")
                    if arguments.get("company"):
                        task["company"] = arguments["company"]
                        updates.append("company")
                    if arguments.get("owner"):
                        task["owner"] = arguments["owner"]
                        updates.append("owner")

                    if not updates:
                        return [TextContent(type="text", text=f"No updates provided for task {task_id}")]

                    task["updated_at"] = datetime.now().isoformat()
                    data["tasks"] = tasks
                    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
                    save_json("pending_tasks.json", data)

                    return [TextContent(type="text", text=f"Task {task_id} updated successfully.\nUpdated fields: {', '.join(updates)}\n\n{json.dumps(task, indent=2)}")]

            return [TextContent(type="text", text=f"Task {task_id} not found")]

        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )

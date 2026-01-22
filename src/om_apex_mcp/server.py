"""
Om Apex MCP Server

A Model Context Protocol server providing persistent memory for Om Apex Holdings
across all Claude interfaces (Chat, Cowork, Claude Code).

Author: Nishad Tambe
Started: January 19, 2026
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("om-apex-mcp")

# Initialize MCP server
server = Server("om-apex-mcp")

# Data directory - uses Google Shared Drive for sync between Nishad (Mac) and Sumedha (Windows)
# Can be overridden via OM_APEX_DATA_DIR environment variable
import platform

def get_default_data_dir() -> Path:
    """Get the default data directory based on platform."""
    if platform.system() == "Darwin":  # macOS
        # Mac path for Google Shared Drive
        return Path.home() / "Library/CloudStorage/GoogleDrive-nishad@omapex.com/Shared drives/om-apex/mcp-data"
    elif platform.system() == "Windows":
        # Windows path for Google Shared Drive (Sumedha's laptop uses H:)
        return Path("H:/Shared drives/om-apex/mcp-data")
    else:
        # Fallback to local path for other systems
        return Path(__file__).parent.parent.parent / "data" / "context"

DEFAULT_DATA_DIR = get_default_data_dir()
DATA_DIR = Path(os.environ.get("OM_APEX_DATA_DIR", DEFAULT_DATA_DIR)).expanduser()

# Daily Progress directory - derived from shared drive root
DAILY_PROGRESS_DIR = DATA_DIR.parent / "business-plan" / "06 HR and Admin" / "Daily Progress"

logger.info(f"Using data directory: {DATA_DIR}")
logger.info(f"Using daily progress directory: {DAILY_PROGRESS_DIR}")


def load_json(filename: str) -> dict:
    """Load a JSON file from the data/context directory."""
    filepath = DATA_DIR / filename
    if filepath.exists():
        with open(filepath, "r") as f:
            return json.load(f)
    return {}


def save_json(filename: str, data: dict) -> None:
    """Save data to a JSON file in the data/context directory."""
    filepath = DATA_DIR / filename
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


# =============================================================================
# Tool Categorization (for get_full_context response)
# When adding a new tool, add it to the appropriate category below
# =============================================================================

READING_TOOLS = [
    "get_full_context",
    "get_company_context",
    "get_technology_decisions",
    "get_decisions_history",
    "get_domain_inventory",
    "get_pending_tasks",
    "get_daily_progress",
    "search_daily_progress",
]

WRITING_TOOLS = [
    "add_task",
    "complete_task",
    "update_task_status",
    "update_task",
    "add_decision",
    "add_daily_progress",
]


# =============================================================================
# Tool Definitions
# =============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools."""
    return [
        Tool(
            name="get_company_context",
            description="Get Om Apex Holdings company structure including subsidiaries, ownership, and products",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_technology_decisions",
            description="Get all technology stack decisions for Om AI Solutions (frontend, backend, database, AI framework)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_domain_inventory",
            description="Get the complete domain inventory with tiers and renewal strategy",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_pending_tasks",
            description="Get all pending tasks across Om Apex Holdings companies",
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Filter by company name (optional)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status: pending, in_progress, completed (optional)"
                    },
                    "owner": {
                        "type": "string",
                        "description": "Filter by owner name (e.g., Nishad, Sumedha, Both, Claude, Scroggin, etc.)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="add_task",
            description="Add a new task to the pending tasks list. Owner can be specified in parentheses at end of description, e.g. 'Build website (Sumedha)' or 'Call attorney (Scroggin)'",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Description of the task. Include owner in parentheses at end, e.g. 'Build website (Sumedha)' or 'Follow up on quote (Scroggin)'"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category: Technical, Marketing, Legal, Operations, Administrative, Content"
                    },
                    "company": {
                        "type": "string",
                        "description": "Company: Om Apex Holdings, Om Luxe Properties, Om AI Solutions, Om Supply Chain"
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority: High, Medium, Low"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional notes (optional)"
                    }
                },
                "required": ["description", "category", "company", "priority"]
            }
        ),
        Tool(
            name="complete_task",
            description="Mark a task as completed",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID (e.g., TASK-001)"
                    }
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="update_task_status",
            description="Update the status of a task",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID (e.g., TASK-001)"
                    },
                    "status": {
                        "type": "string",
                        "description": "New status: pending, in_progress, completed"
                    }
                },
                "required": ["task_id", "status"]
            }
        ),
        Tool(
            name="update_task",
            description="Update any field of an existing task (description, notes, priority, category, company, owner)",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID (e.g., TASK-001)"
                    },
                    "description": {
                        "type": "string",
                        "description": "New description for the task (optional)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "New or updated notes (optional)"
                    },
                    "priority": {
                        "type": "string",
                        "description": "New priority: High, Medium, Low (optional)"
                    },
                    "category": {
                        "type": "string",
                        "description": "New category: Technical, Marketing, Legal, Operations, Administrative, Content (optional)"
                    },
                    "company": {
                        "type": "string",
                        "description": "New company: Om Apex Holdings, Om Luxe Properties, Om AI Solutions, Om Supply Chain (optional)"
                    },
                    "owner": {
                        "type": "string",
                        "description": "New owner name (optional)"
                    }
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="get_full_context",
            description="Get a comprehensive summary of all Om Apex Holdings context (company, decisions, tasks) - useful for starting a new conversation",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="add_decision",
            description="Record a new technology or business decision with reasoning. Use this to persist important decisions made during conversations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "description": "Area of decision (e.g., 'Frontend Framework', 'Authentication', 'Hosting')"
                    },
                    "decision": {
                        "type": "string",
                        "description": "The decision made (e.g., 'Use NextAuth.js for authentication')"
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Why this decision was made - the reasoning and factors considered"
                    },
                    "alternatives_considered": {
                        "type": "string",
                        "description": "Other options that were considered (optional)"
                    },
                    "confidence": {
                        "type": "string",
                        "description": "Confidence level: High, Medium, Low (default: Medium)"
                    },
                    "company": {
                        "type": "string",
                        "description": "Which company this applies to: Om Apex Holdings, Om Luxe Properties, Om AI Solutions"
                    }
                },
                "required": ["area", "decision", "rationale", "company"]
            }
        ),
        Tool(
            name="get_decisions_history",
            description="Get all recorded decisions with their rationale, optionally filtered by area or company",
            inputSchema={
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "description": "Filter by area (optional)"
                    },
                    "company": {
                        "type": "string",
                        "description": "Filter by company (optional)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_daily_progress",
            description="Get the daily progress log for a specific date",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (e.g., '2026-01-21')"
                    }
                },
                "required": ["date"]
            }
        ),
        Tool(
            name="add_daily_progress",
            description="Add a session entry to the daily progress log. Creates file if it doesn't exist for today. Uses structured data to build consistent markdown formatting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "person": {
                        "type": "string",
                        "description": "Who is logging this session: Nishad or Sumedha"
                    },
                    "interface": {
                        "type": "string",
                        "description": "Which Claude interface: code, cowork, chat, or code-app"
                    },
                    "title": {
                        "type": "string",
                        "description": "Brief title for this session (e.g., 'MCP Server Setup')"
                    },
                    "completed": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of items completed during the session"
                    },
                    "decisions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of decisions recorded (format: 'ID: Description')"
                    },
                    "tasks_completed": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tasks marked complete (format: 'ID: Description')"
                    },
                    "tasks_created": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of new tasks created (format: 'ID: Description')"
                    },
                    "files_modified": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of files created/modified (format: 'path - description')"
                    },
                    "notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional notes for future reference"
                    }
                },
                "required": ["person", "interface", "title"]
            }
        ),
        Tool(
            name="search_daily_progress",
            description="Search through all daily progress logs for relevant content. Returns matching file contents for Claude to analyze semantically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_text": {
                        "type": "string",
                        "description": "Text to search for in daily progress logs"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of files to return (default: 10)"
                    }
                },
                "required": ["search_text"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "get_company_context":
        data = load_json("company_structure.json")
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    elif name == "get_technology_decisions":
        data = load_json("technology_decisions.json")
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    elif name == "get_domain_inventory":
        data = load_json("domain_inventory.json")
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    elif name == "get_pending_tasks":
        data = load_json("pending_tasks.json")
        tasks = data.get("tasks", [])

        # Apply filters if provided
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

        # Generate next task ID
        existing_ids = [t.get("id", "") for t in tasks]
        max_num = 0
        for tid in existing_ids:
            if tid.startswith("TASK-"):
                try:
                    num = int(tid.split("-")[1])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        new_id = f"TASK-{max_num + 1:03d}"

        # Parse owner from description if present
        # Supports: "(Name)" at end, or "Name to do X" pattern
        description = arguments["description"]
        owner = None

        # Pattern 1: (Name) at end of description - accepts any single word as owner
        owner_match = re.search(r'\(([A-Za-z]+)\)\s*$', description)
        if owner_match:
            owner = owner_match.group(1).capitalize()
            # Remove owner from description for cleaner storage
            description = re.sub(r'\s*\([A-Za-z]+\)\s*$', '', description)

        # Create new task
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

        for task in tasks:
            if task.get("id") == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
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
                # Track what was updated
                updates = []

                # Update fields if provided
                if "description" in arguments and arguments["description"]:
                    task["description"] = arguments["description"]
                    updates.append("description")

                if "notes" in arguments and arguments["notes"]:
                    task["notes"] = arguments["notes"]
                    updates.append("notes")

                if "priority" in arguments and arguments["priority"]:
                    if arguments["priority"] not in ["High", "Medium", "Low"]:
                        return [TextContent(type="text", text=f"Invalid priority: {arguments['priority']}. Must be High, Medium, or Low")]
                    task["priority"] = arguments["priority"]
                    updates.append("priority")

                if "category" in arguments and arguments["category"]:
                    task["category"] = arguments["category"]
                    updates.append("category")

                if "company" in arguments and arguments["company"]:
                    task["company"] = arguments["company"]
                    updates.append("company")

                if "owner" in arguments and arguments["owner"]:
                    task["owner"] = arguments["owner"]
                    updates.append("owner")

                if not updates:
                    return [TextContent(type="text", text=f"No updates provided for task {task_id}")]

                # Save changes
                task["updated_at"] = datetime.now().isoformat()
                data["tasks"] = tasks
                data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
                save_json("pending_tasks.json", data)

                return [TextContent(type="text", text=f"Task {task_id} updated successfully.\nUpdated fields: {', '.join(updates)}\n\n{json.dumps(task, indent=2)}")]

        return [TextContent(type="text", text=f"Task {task_id} not found")]

    elif name == "get_full_context":
        company = load_json("company_structure.json")
        decisions = load_json("technology_decisions.json")
        tasks = load_json("pending_tasks.json")
        domains = load_json("domain_inventory.json")

        # Build a comprehensive summary
        pending_tasks = [t for t in tasks.get("tasks", []) if t.get("status") != "completed"]
        high_priority = [t for t in pending_tasks if t.get("priority") == "High"]

        # Build the exact display text for consistent output across all platforms
        display_text = f"""Full context loaded.

**Quick Summary:** {len(pending_tasks)} pending tasks ({len(high_priority)} high priority)

How can I help you today?"""

        summary = {
            "display": {
                "INSTRUCTION": "Output EXACTLY the text in 'output' below - nothing more, nothing less. This ensures consistent greeting across all Claude platforms.",
                "output": display_text
            },
            "session_workflow": {
                "session_end": {
                    "trigger": "When user says 'end session', 'wrap up', 'save our work', or similar",
                    "steps": [
                        "1. Review conversation for: decisions made, tasks completed, new tasks identified",
                        "2. Summarize findings to user and get confirmation",
                        "3. Call add_decision for each decision (area, decision, rationale, company)",
                        "4. Call add_task for each new task",
                        "5. Call complete_task for each completed task",
                        "6. Call add_daily_progress with: person, interface, title, completed, decisions, tasks_completed, tasks_created, files_modified, notes",
                        "7. Confirm everything was saved"
                    ]
                },
                "mcp_server_code_location": "/Users/nishad/om-apex/om-ai/om-apex-mcp/ (main: src/om_apex_mcp/server.py)"
            },
            "available_tools": {
                "reading": READING_TOOLS,
                "writing": WRITING_TOOLS
            },
            "company_overview": {
                "holding_company": company.get("holding_company", {}).get("name"),
                "subsidiaries": [s.get("name") for s in company.get("subsidiaries", [])],
                "owners": list(company.get("holding_company", {}).get("ownership", {}).keys())
            },
            "tech_stack": {
                "frontend": decisions.get("decisions", [{}])[1].get("decision", {}).get("frontend", {}),
                "backend": decisions.get("decisions", [{}])[1].get("decision", {}).get("backend", {}),
                "database": decisions.get("decisions", [{}])[1].get("decision", {}).get("database", {})
            },
            "domains": {
                "total": domains.get("summary", {}).get("total_domains"),
                "active": domains.get("tiers", {}).get("tier1_active_now", {}).get("domains", [])
            },
            "tasks": {
                "total_pending": len(pending_tasks),
                "high_priority": len(high_priority),
                "high_priority_tasks": [{"id": t.get("id"), "description": t.get("description")} for t in high_priority]
            }
        }

        return [TextContent(type="text", text=json.dumps(summary, indent=2))]

    elif name == "add_decision":
        data = load_json("technology_decisions.json")
        decisions = data.get("decisions", [])

        # Generate next decision ID
        existing_ids = [d.get("id", "") for d in decisions]
        max_num = 0
        for did in existing_ids:
            if did.startswith("TECH-"):
                try:
                    num = int(did.split("-")[1])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        new_id = f"TECH-{max_num + 1:03d}"

        # Create new decision
        new_decision = {
            "id": new_id,
            "area": arguments["area"],
            "date_decided": datetime.now().strftime("%Y-%m-%d"),
            "confidence": arguments.get("confidence", "Medium"),
            "decision": arguments["decision"],
            "rationale": arguments["rationale"],
            "company": arguments["company"]
        }
        if arguments.get("alternatives_considered"):
            new_decision["alternatives_considered"] = arguments["alternatives_considered"]

        decisions.append(new_decision)
        data["decisions"] = decisions
        data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        save_json("technology_decisions.json", data)

        return [TextContent(type="text", text=f"Decision recorded successfully:\n{json.dumps(new_decision, indent=2)}")]

    elif name == "get_decisions_history":
        data = load_json("technology_decisions.json")
        decisions = data.get("decisions", [])

        # Apply filters if provided
        area = arguments.get("area")
        company = arguments.get("company")

        if area:
            decisions = [d for d in decisions if area.lower() in d.get("area", "").lower()]
        if company:
            decisions = [d for d in decisions if d.get("company", "").lower() == company.lower()]

        return [TextContent(type="text", text=json.dumps(decisions, indent=2))]

    elif name == "get_daily_progress":
        date = arguments["date"]

        # Look for file matching the date pattern
        if not DAILY_PROGRESS_DIR.exists():
            return [TextContent(type="text", text=f"Daily Progress directory not found: {DAILY_PROGRESS_DIR}")]

        # Try exact match first (YYYY-MM-DD.md)
        exact_file = DAILY_PROGRESS_DIR / f"{date}.md"
        if exact_file.exists():
            with open(exact_file, "r", encoding="utf-8") as f:
                content = f.read()
            return [TextContent(type="text", text=content)]

        # Try pattern match (files starting with the date)
        matching_files = list(DAILY_PROGRESS_DIR.glob(f"{date}*.md"))
        if matching_files:
            # Read the first matching file
            with open(matching_files[0], "r", encoding="utf-8") as f:
                content = f.read()
            return [TextContent(type="text", text=f"File: {matching_files[0].name}\n\n{content}")]

        return [TextContent(type="text", text=f"No daily progress log found for {date}")]

    elif name == "add_daily_progress":
        person = arguments["person"]
        interface = arguments["interface"].lower()
        title = arguments["title"]

        # Ensure directory exists
        DAILY_PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

        # Get today's date and timestamp
        today = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%I:%M %p EST").lstrip("0")

        # File path for today
        filepath = DAILY_PROGRESS_DIR / f"{today}.md"

        # Determine session number
        session_num = 1
        existing_content = ""

        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                existing_content = f.read()
            # Count existing sessions using regex to find max (handles gaps)
            session_matches = re.findall(r"## Session (\d+)", existing_content)
            if session_matches:
                session_num = max(int(n) for n in session_matches) + 1

        # Build the session entry from structured data
        session_parts = []
        session_parts.append(f"\n---\n")
        session_parts.append(f"\n## Session {session_num} ({interface}) (by {person}) ({timestamp}) - {title}\n")

        # Add completed items
        completed = arguments.get("completed", [])
        if completed:
            session_parts.append("\n### Completed\n")
            for item in completed:
                session_parts.append(f"- {item}\n")

        # Add decisions
        decisions = arguments.get("decisions", [])
        if decisions:
            session_parts.append("\n### Decisions Recorded\n")
            for item in decisions:
                if ":" in item:
                    parts = item.split(":", 1)
                    session_parts.append(f"- **{parts[0]}**: {parts[1].strip()}\n")
                else:
                    session_parts.append(f"- **{item}**\n")

        # Add tasks completed
        tasks_completed = arguments.get("tasks_completed", [])
        if tasks_completed:
            session_parts.append("\n### Tasks Completed\n")
            for item in tasks_completed:
                if ":" in item:
                    parts = item.split(":", 1)
                    session_parts.append(f"- **{parts[0]}**: {parts[1].strip()}\n")
                else:
                    session_parts.append(f"- **{item}**\n")

        # Add tasks created
        tasks_created = arguments.get("tasks_created", [])
        if tasks_created:
            session_parts.append("\n### Tasks Created\n")
            for item in tasks_created:
                if ":" in item:
                    parts = item.split(":", 1)
                    session_parts.append(f"- **{parts[0]}**: {parts[1].strip()}\n")
                else:
                    session_parts.append(f"- **{item}**\n")

        # Add files modified
        files_modified = arguments.get("files_modified", [])
        if files_modified:
            session_parts.append("\n### Files Created/Modified\n")
            for item in files_modified:
                session_parts.append(f"- {item}\n")

        # Add notes
        notes = arguments.get("notes", [])
        if notes:
            session_parts.append("\n### Notes\n")
            for item in notes:
                session_parts.append(f"- {item}\n")

        session_entry = "".join(session_parts)

        # Write to file
        if existing_content:
            # Append to existing file
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(session_entry)
        else:
            # Create new file with header
            file_header = f"# Daily Progress - {today}\n"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(file_header + session_entry)

        return [TextContent(type="text", text=f"Daily progress logged successfully:\n- File: {filepath.name}\n- Session: {session_num}\n- Person: {person}\n- Interface: {interface}\n- Title: {title}")]

    elif name == "search_daily_progress":
        search_text = arguments["search_text"].lower()
        limit = arguments.get("limit", 10)

        if not DAILY_PROGRESS_DIR.exists():
            return [TextContent(type="text", text=f"Daily Progress directory not found: {DAILY_PROGRESS_DIR}")]

        # Get all markdown files, sorted by date (newest first)
        md_files = sorted(DAILY_PROGRESS_DIR.glob("*.md"), reverse=True)

        results = []
        for filepath in md_files[:limit * 2]:  # Check more files than limit in case some don't match
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Simple text search (Claude will do semantic analysis)
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
            # If no exact matches, return recent files for Claude to analyze
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
                except Exception as e:
                    continue

            return [TextContent(type="text", text=f"No exact matches for '{search_text}'. Returning {len(results)} recent logs for semantic analysis:\n\n" + json.dumps(results, indent=2))]

        return [TextContent(type="text", text=f"Found {len(results)} matching logs:\n\n" + json.dumps(results, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# =============================================================================
# Main Entry Point
# =============================================================================

async def run():
    """Run the MCP server."""
    logger.info("Starting Om Apex MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Main entry point."""
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()

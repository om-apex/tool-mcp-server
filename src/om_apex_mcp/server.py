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
        # Windows path for Google Shared Drive
        return Path("G:/Shared drives/om-apex/mcp-data")
    else:
        # Fallback to local path for other systems
        return Path(__file__).parent.parent.parent / "data" / "context"

DEFAULT_DATA_DIR = get_default_data_dir()
DATA_DIR = Path(os.environ.get("OM_APEX_DATA_DIR", DEFAULT_DATA_DIR)).expanduser()

logger.info(f"Using data directory: {DATA_DIR}")


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

    elif name == "get_full_context":
        company = load_json("company_structure.json")
        decisions = load_json("technology_decisions.json")
        tasks = load_json("pending_tasks.json")
        domains = load_json("domain_inventory.json")

        # Build a comprehensive summary
        pending_tasks = [t for t in tasks.get("tasks", []) if t.get("status") != "completed"]
        high_priority = [t for t in pending_tasks if t.get("priority") == "High"]

        summary = {
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

"""
Om Apex MCP Server

A Model Context Protocol server providing persistent memory for Om Apex Holdings
across all Claude interfaces (Chat, Cowork, Claude Code).

Author: Nishad Tambe
Started: January 19, 2026
"""

import json
import logging
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

# Data directory - relative to this file's location
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "context"


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
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="add_task",
            description="Add a new task to the pending tasks list",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Description of the task"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category: Technical, Marketing, Legal, Operations, Administrative"
                    },
                    "company": {
                        "type": "string",
                        "description": "Company: Om Apex Holdings, Om Luxe Properties, Om AI Solutions"
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

        if company:
            tasks = [t for t in tasks if t.get("company", "").lower() == company.lower()]
        if category:
            tasks = [t for t in tasks if t.get("category", "").lower() == category.lower()]
        if status:
            tasks = [t for t in tasks if t.get("status", "").lower() == status.lower()]

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

        # Create new task
        new_task = {
            "id": new_id,
            "description": arguments["description"],
            "category": arguments["category"],
            "company": arguments["company"],
            "priority": arguments["priority"],
            "status": "pending",
            "created": datetime.now().isoformat()
        }
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

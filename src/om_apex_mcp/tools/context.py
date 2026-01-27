"""Context tools: company, tech, domains, decisions, instructions, full_context."""

import json
from datetime import datetime

from mcp.types import Tool, TextContent

from . import ToolModule
from .helpers import load_json, save_json, get_claude_instructions_data


READING = [
    "get_full_context",
    "get_claude_instructions",
    "get_company_context",
    "get_technology_decisions",
    "get_decisions_history",
    "get_domain_inventory",
]

WRITING = [
    "add_decision",
]


def register(all_reading_tools: list[str], all_writing_tools: list[str]) -> ToolModule:
    """Register context tools. Receives the global reading/writing lists for get_full_context."""

    tools = [
        Tool(
            name="get_company_context",
            description="Get Om Apex Holdings company structure including subsidiaries, ownership, and products",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_technology_decisions",
            description="Get all technology stack decisions for Om AI Solutions (frontend, backend, database, AI framework)",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_domain_inventory",
            description="Get the complete domain inventory with tiers and renewal strategy",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_full_context",
            description="Get a comprehensive summary of all Om Apex Holdings context (company, decisions, tasks) - useful for starting a new conversation",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_claude_instructions",
            description="Get behavioral instructions for Claude across all platforms (Chat, Cowork, Code). Defines how to greet users, end sessions, and format responses consistently.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="add_decision",
            description="Record a new technology or business decision with reasoning. Use this to persist important decisions made during conversations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "area": {"type": "string", "description": "Area of decision (e.g., 'Frontend Framework', 'Authentication', 'Hosting')"},
                    "decision": {"type": "string", "description": "The decision made (e.g., 'Use NextAuth.js for authentication')"},
                    "rationale": {"type": "string", "description": "Why this decision was made - the reasoning and factors considered"},
                    "alternatives_considered": {"type": "string", "description": "Other options that were considered (optional)"},
                    "confidence": {"type": "string", "description": "Confidence level: High, Medium, Low (default: Medium)"},
                    "company": {"type": "string", "description": "Which company this applies to: Om Apex Holdings, Om Luxe Properties, Om AI Solutions"},
                },
                "required": ["area", "decision", "rationale", "company"],
            },
        ),
        Tool(
            name="get_decisions_history",
            description="Get all recorded decisions with their rationale, optionally filtered by area or company",
            inputSchema={
                "type": "object",
                "properties": {
                    "area": {"type": "string", "description": "Filter by area (optional)"},
                    "company": {"type": "string", "description": "Filter by company (optional)"},
                },
                "required": [],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "get_company_context":
            data = load_json("company_structure.json")
            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        elif name == "get_technology_decisions":
            data = load_json("technology_decisions.json")
            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        elif name == "get_domain_inventory":
            data = load_json("domain_inventory.json")
            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        elif name == "get_claude_instructions":
            instructions = get_claude_instructions_data()
            return [TextContent(type="text", text=json.dumps(instructions, indent=2))]

        elif name == "get_full_context":
            company = load_json("company_structure.json")
            decisions = load_json("technology_decisions.json")
            tasks = load_json("pending_tasks.json")
            domains = load_json("domain_inventory.json")

            pending_tasks = [t for t in tasks.get("tasks", []) if t.get("status") != "completed"]
            high_priority = [t for t in pending_tasks if t.get("priority") == "High"]

            display_text = f"""Full context loaded.

**Quick Summary:** {len(pending_tasks)} pending tasks ({len(high_priority)} high priority)

How can I help you today?"""

            instructions = get_claude_instructions_data()

            summary = {
                "CRITICAL_INSTRUCTION": {
                    "action": "OUTPUT ONLY THE TEXT BELOW - NOTHING ELSE",
                    "output": display_text,
                    "rules": [
                        "Do NOT list tasks, decisions, tech stack, domains, or any other details",
                        "Do NOT explain what was loaded or summarize the context",
                        "Do NOT add any additional greeting or pleasantries",
                        "Just output the 3 lines shown in 'output' above, exactly as written"
                    ]
                },
                "behavioral_instructions": instructions,
                "available_tools": {
                    "reading": all_reading_tools,
                    "writing": all_writing_tools
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

            existing_ids = [d.get("id", "") for d in decisions]
            max_num = 0
            for did in existing_ids:
                if did.startswith("TECH-"):
                    try:
                        max_num = max(max_num, int(did.split("-")[1]))
                    except ValueError:
                        pass
            new_id = f"TECH-{max_num + 1:03d}"

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

            area = arguments.get("area")
            company = arguments.get("company")
            if area:
                decisions = [d for d in decisions if area.lower() in d.get("area", "").lower()]
            if company:
                decisions = [d for d in decisions if d.get("company", "").lower() == company.lower()]

            return [TextContent(type="text", text=json.dumps(decisions, indent=2))]

        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )

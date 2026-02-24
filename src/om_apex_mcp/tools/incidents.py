"""Production incident tools: create and list incidents in Om Cortex prodsupport_incidents.

Allows Claude Code to file bugs directly as production incidents during sessions,
bridging the gap between conversational bug reports and the Cortex incident system.
"""

import json
import random
import string
from datetime import datetime, timezone

from mcp.types import Tool, TextContent

from . import ToolModule
from ..cortex_supabase import is_cortex_available, get_cortex_client, reset_cortex_client, \
    create_incident, create_incident_event, list_incidents


READING = [
    "incident_list",
]
WRITING = [
    "incident_create",
]


def _require_cortex() -> None:
    """Ensure Om Cortex Supabase is available. Resets cached client on 401 errors."""
    if not is_cortex_available():
        raise RuntimeError(
            "Om Cortex Supabase is not available. "
            "Check that CORTEX_SUPABASE_URL and CORTEX_SUPABASE_SERVICE_KEY are set, "
            "or that ~/om-apex/config/.env.cortex exists."
        )
    # Verify the cached client still works
    client = get_cortex_client()
    try:
        client.table("prodsupport_incidents").select("id").limit(1).execute()
    except Exception as e:
        if "401" in str(e) or "Invalid API key" in str(e):
            reset_cortex_client()
            if not is_cortex_available():
                raise RuntimeError("Om Cortex Supabase: key reset failed. Check .env.cortex.")
        else:
            raise


def _json_response(data) -> list[TextContent]:
    """Return data as formatted JSON TextContent."""
    return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


def register() -> ToolModule:
    tools = [
        Tool(
            name="incident_create",
            description=(
                "Create a production incident in Om Cortex prodsupport_incidents table. "
                "Use this to file bugs discovered during Claude Code sessions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short descriptive title",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["SEV-1", "SEV-2", "SEV-3"],
                        "description": "Severity level: SEV-1 (critical), SEV-2 (major), SEV-3 (minor)",
                    },
                    "project": {
                        "type": "string",
                        "description": "Which product is affected (default: ai-quorum)",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["frontend_error", "backend_error", "performance", "ux_anomaly"],
                        "description": "Error category (default: backend_error)",
                    },
                    "component": {
                        "type": "string",
                        "description": "Affected component (e.g., auth, api, admin-ui, orchestrator)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description / diagnosis of the issue",
                    },
                    "steps_to_reproduce": {
                        "type": "string",
                        "description": "Steps to reproduce the issue",
                    },
                    "expected_behavior": {
                        "type": "string",
                        "description": "What should happen",
                    },
                    "actual_behavior": {
                        "type": "string",
                        "description": "What actually happens",
                    },
                    "reported_by": {
                        "type": "string",
                        "description": "Who filed it (default: claude-code)",
                    },
                },
                "required": ["title", "severity"],
            },
        ),
        Tool(
            name="incident_list",
            description=(
                "List production incidents from Om Cortex prodsupport_incidents table. "
                "Check what incidents are open without needing the Cortex agent."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: open, investigating, fix_in_progress, deployed, resolved, ignored",
                    },
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity: SEV-1, SEV-2, SEV-3",
                    },
                    "project": {
                        "type": "string",
                        "description": "Filter by project name",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max incidents to return (default 10)",
                    },
                },
                "required": [],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "incident_create":
            return _handle_incident_create(arguments)
        elif name == "incident_list":
            return _handle_incident_list(arguments)
        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )


# =============================================================================
# Handler implementations
# =============================================================================

def _handle_incident_create(args: dict) -> list[TextContent]:
    _require_cortex()

    title = args["title"]
    severity = args["severity"]
    project = args.get("project", "ai-quorum")
    category = args.get("category", "backend_error")
    component = args.get("component")
    description = args.get("description")
    steps_to_reproduce = args.get("steps_to_reproduce")
    expected_behavior = args.get("expected_behavior")
    actual_behavior = args.get("actual_behavior")
    reported_by = args.get("reported_by", "claude-code")

    # Build metadata from optional fields
    metadata = {}
    if steps_to_reproduce:
        metadata["steps_to_reproduce"] = steps_to_reproduce
    if expected_behavior:
        metadata["expected_behavior"] = expected_behavior
    if actual_behavior:
        metadata["actual_behavior"] = actual_behavior

    # Generate fingerprint: manual:{timestamp}-{random6}
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d%H%M%S")
    rand6 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    fingerprint = f"manual:{ts}-{rand6}"

    # Build incident row
    incident = {
        "fingerprint": fingerprint,
        "title": title,
        "project": project,
        "source": "manual",
        "severity": severity,
        "category": category,
        "status": "open",
        "assigned_to": "cortex",
        "metadata": metadata,
    }
    if component:
        incident["component"] = component
    if description:
        incident["diagnosis"] = description

    # Insert incident
    created = create_incident(incident)

    # Insert audit event
    try:
        create_incident_event({
            "incident_id": created["id"],
            "event_type": "created",
            "actor": reported_by,
            "details": {
                "source": "manual",
                "severity": severity,
                "filed_via": "mcp-server",
            },
        })
    except Exception:
        # Don't fail the whole operation if the audit event fails
        pass

    return [TextContent(
        type="text",
        text=(
            f"Incident created successfully.\n\n"
            f"**ID:** {created['id']}\n"
            f"**Title:** {title}\n"
            f"**Severity:** {severity}\n"
            f"**Project:** {project}\n"
            f"**Status:** open\n"
            f"**Fingerprint:** {fingerprint}\n"
            f"**Assigned to:** cortex"
        ),
    )]


def _handle_incident_list(args: dict) -> list[TextContent]:
    _require_cortex()

    rows = list_incidents(
        status=args.get("status"),
        severity=args.get("severity"),
        project=args.get("project"),
        limit=args.get("limit", 10),
    )

    if not rows:
        filters = []
        if args.get("status"):
            filters.append(f"status={args['status']}")
        if args.get("severity"):
            filters.append(f"severity={args['severity']}")
        if args.get("project"):
            filters.append(f"project={args['project']}")
        filter_str = f" (filters: {', '.join(filters)})" if filters else ""
        return [TextContent(type="text", text=f"No incidents found{filter_str}.")]

    return _json_response(rows)

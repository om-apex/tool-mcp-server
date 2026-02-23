"""AI Quorum orchestration tools: status, sessions, turns, logs, performance, costs, config.

Provides MCP tools for monitoring and managing the AI Quorum product.
All data comes from the AI Quorum Supabase project (separate from the Owner Portal).
"""

import json
from datetime import datetime, timedelta, timezone

from mcp.types import Tool, TextContent

from . import ToolModule
from ..quorum_supabase import is_quorum_available, get_quorum_client, reset_quorum_client


READING = [
    "get_quorum_status",
    "list_quorum_sessions",
    "get_quorum_turn_detail",
    "get_quorum_turn_trace",
    "get_quorum_logs",
    "get_quorum_model_performance",
    "get_quorum_cost_summary",
    "get_quorum_stage_config",
    "get_quorum_user_detail",
]
WRITING = [
    "update_quorum_stage_config",
]


def _require_quorum() -> None:
    """Ensure AI Quorum Supabase is available. Resets cached client on 401 errors."""
    if not is_quorum_available():
        raise RuntimeError(
            "AI Quorum Supabase is not available. "
            "Check that QUORUM_SUPABASE_URL and QUORUM_SUPABASE_SERVICE_KEY are set, "
            "or that ~/om-apex/config/.env.supabase exists with SUPABASE_URL and SUPABASE_SERVICE_KEY."
        )
    # Verify the cached client still works (catches stale keys in long-running processes)
    client = get_quorum_client()
    try:
        client.table("orch_sessions").select("id").limit(1).execute()
    except Exception as e:
        if "401" in str(e) or "Invalid API key" in str(e):
            reset_quorum_client()
            # Retry with fresh client
            if not is_quorum_available():
                raise RuntimeError("AI Quorum Supabase: key reset failed. Check .env.supabase.")
        else:
            raise


def _json_response(data) -> list[TextContent]:
    """Return data as formatted JSON TextContent."""
    return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


def register() -> ToolModule:
    tools = [
        Tool(
            name="get_quorum_status",
            description="Get AI Quorum system status: active config version, available models, recent session count",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_quorum_sessions",
            description="List AI Quorum orchestration sessions with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Filter by user ID (optional)"},
                    "status": {"type": "string", "description": "Filter by status (optional)"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_quorum_turn_detail",
            description="Get detailed info for a specific turn: metadata, stages, and model calls per stage",
            inputSchema={
                "type": "object",
                "properties": {
                    "turn_id": {"type": "string", "description": "The turn ID (UUID)"},
                },
                "required": ["turn_id"],
            },
        ),
        Tool(
            name="get_quorum_turn_trace",
            description="Get human-readable chronological trace of a turn: stages, model calls with prompt/response summaries, timing, and cost",
            inputSchema={
                "type": "object",
                "properties": {
                    "turn_id": {"type": "string", "description": "The turn ID (UUID)"},
                },
                "required": ["turn_id"],
            },
        ),
        Tool(
            name="get_quorum_logs",
            description="Get orchestration log entries with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Filter by session ID (optional)"},
                    "turn_id": {"type": "string", "description": "Filter by turn ID (optional)"},
                    "severity": {"type": "string", "description": "Filter by severity (optional)"},
                    "limit": {"type": "integer", "description": "Max results (default 50)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_quorum_model_performance",
            description="Get model performance metrics from the v_model_performance view or run_metrics table",
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Filter by model name (optional)"},
                    "category": {"type": "string", "description": "Filter by category (optional)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_quorum_cost_summary",
            description="Get token usage and cost summary, optionally filtered by user/session/date range",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Filter by user ID (optional)"},
                    "session_id": {"type": "string", "description": "Filter by session ID (optional)"},
                    "date_from": {"type": "string", "description": "Start date YYYY-MM-DD (optional)"},
                    "date_to": {"type": "string", "description": "End date YYYY-MM-DD (optional)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_quorum_stage_config",
            description="Get stage configuration for a config version (defaults to active version)",
            inputSchema={
                "type": "object",
                "properties": {
                    "version_number": {"type": "integer", "description": "Config version number (optional, defaults to active)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="update_quorum_stage_config",
            description="Update a stage's configuration (only allowed on draft versions). Can update timeout_ms, prompt_template, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stage_id": {"type": "string", "description": "The stage ID (UUID)"},
                    "updates": {
                        "type": "object",
                        "description": "Fields to update: timeout_ms, prompt_template, polling_mode, stage_name, etc.",
                    },
                },
                "required": ["stage_id", "updates"],
            },
        ),
        Tool(
            name="get_quorum_user_detail",
            description="Get user preferences, recent sessions, and total token/cost usage for a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The user ID (UUID)"},
                },
                "required": ["user_id"],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "get_quorum_status":
            return _handle_get_status()

        elif name == "list_quorum_sessions":
            return _handle_list_sessions(arguments)

        elif name == "get_quorum_turn_detail":
            return _handle_turn_detail(arguments)

        elif name == "get_quorum_turn_trace":
            return _handle_turn_trace(arguments)

        elif name == "get_quorum_logs":
            return _handle_get_logs(arguments)

        elif name == "get_quorum_model_performance":
            return _handle_model_performance(arguments)

        elif name == "get_quorum_cost_summary":
            return _handle_cost_summary(arguments)

        elif name == "get_quorum_stage_config":
            return _handle_stage_config(arguments)

        elif name == "update_quorum_stage_config":
            return _handle_update_stage_config(arguments)

        elif name == "get_quorum_user_detail":
            return _handle_user_detail(arguments)

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

def _handle_get_status():
    _require_quorum()
    client = get_quorum_client()

    # Active config version
    active_config = None
    try:
        resp = client.table("orch_config_versions").select("*").eq("status", "active").limit(1).execute()
        if resp.data:
            active_config = resp.data[0]
    except Exception as e:
        active_config = {"error": f"Could not fetch config: {e}"}

    # Available models count
    model_count = 0
    try:
        resp = client.table("llm_master").select("id").eq("is_available", True).execute()
        model_count = len(resp.data) if resp.data else 0
    except Exception as e:
        model_count = f"error: {e}"

    # Recent sessions (last 24h)
    recent_sessions = 0
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        resp = client.table("orch_sessions").select("id").gte("created_at", cutoff).execute()
        recent_sessions = len(resp.data) if resp.data else 0
    except Exception as e:
        recent_sessions = f"error: {e}"

    return _json_response({
        "active_config_version": active_config,
        "available_models": model_count,
        "sessions_last_24h": recent_sessions,
    })


def _handle_list_sessions(arguments: dict):
    _require_quorum()
    client = get_quorum_client()
    limit = arguments.get("limit", 20)

    query = client.table("orch_sessions").select("*")

    if arguments.get("user_id"):
        query = query.eq("user_id", arguments["user_id"])
    if arguments.get("status"):
        query = query.eq("status", arguments["status"])

    resp = query.order("created_at", desc=True).limit(limit).execute()
    sessions = resp.data or []

    # Get turn counts for each session
    for session in sessions:
        try:
            turns_resp = client.table("orch_turns").select("id").eq("session_id", session["id"]).execute()
            session["turn_count"] = len(turns_resp.data) if turns_resp.data else 0
        except Exception:
            session["turn_count"] = None

    return _json_response(sessions)


def _handle_turn_detail(arguments: dict):
    _require_quorum()
    client = get_quorum_client()
    turn_id = arguments["turn_id"]

    # Get turn metadata
    turn_resp = client.table("orch_turns").select("*").eq("id", turn_id).execute()
    if not turn_resp.data:
        return [TextContent(type="text", text=f"Turn {turn_id} not found")]
    turn = turn_resp.data[0]

    # Get stages
    stages_resp = client.table("orch_turn_stages").select("*").eq("turn_id", turn_id).order("stage_number").execute()
    stages = stages_resp.data or []

    # Get model calls for each stage
    for stage in stages:
        try:
            calls_resp = (
                client.table("orch_turn_model_calls")
                .select("*")
                .eq("turn_stage_id", stage["id"])
                .order("started_at")
                .execute()
            )
            stage["model_calls"] = calls_resp.data or []
        except Exception:
            stage["model_calls"] = []

    return _json_response({
        "turn": turn,
        "stages": stages,
    })


def _handle_turn_trace(arguments: dict):
    _require_quorum()
    client = get_quorum_client()
    turn_id = arguments["turn_id"]

    # Get turn metadata
    turn_resp = client.table("orch_turns").select("*").eq("id", turn_id).execute()
    if not turn_resp.data:
        return [TextContent(type="text", text=f"Turn {turn_id} not found")]
    turn = turn_resp.data[0]

    # Get stages ordered by stage_number
    stages_resp = client.table("orch_turn_stages").select("*").eq("turn_id", turn_id).order("stage_number").execute()
    stages = stages_resp.data or []

    total_cost = 0.0
    total_tokens = 0
    trace_stages = []

    for stage in stages:
        # Get model calls for this stage
        calls_resp = (
            client.table("orch_turn_model_calls")
            .select("*")
            .eq("turn_stage_id", stage["id"])
            .order("started_at")
            .execute()
        )
        calls = calls_resp.data or []

        trace_calls = []
        for call in calls:
            prompt_full = call.get("prompt_rendered") or ""
            response_full = call.get("raw_response") or ""
            cost = float(call.get("estimated_cost_usd") or 0)
            tokens = int(call.get("total_tokens") or 0)
            total_cost += cost
            total_tokens += tokens

            trace_calls.append({
                "model_code": call.get("model_code"),
                "model_name": call.get("model_name"),
                "status": call.get("status"),
                "started_at": call.get("started_at"),
                "completed_at": call.get("completed_at"),
                "latency_ms": call.get("latency_ms"),
                "input_tokens": call.get("input_tokens"),
                "output_tokens": call.get("output_tokens"),
                "total_tokens": tokens,
                "estimated_cost_usd": cost,
                "prompt_summary": prompt_full[:500] if prompt_full else None,
                "response_summary": response_full[:500] if response_full else None,
                "prompt_full": prompt_full,
                "response_full": response_full,
            })

        trace_stages.append({
            "stage_number": stage.get("stage_number"),
            "stage_code": stage.get("stage_code"),
            "status": stage.get("status"),
            "started_at": stage.get("started_at"),
            "completed_at": stage.get("completed_at"),
            "duration_ms": stage.get("duration_ms"),
            "models_called": stage.get("models_called"),
            "models_succeeded": stage.get("models_succeeded"),
            "model_calls": trace_calls,
        })

    return _json_response({
        "turn": {
            "id": turn.get("id"),
            "session_id": turn.get("session_id"),
            "turn_number": turn.get("turn_number"),
            "aim_input": turn.get("aim_input"),
            "route_type": turn.get("route_type"),
            "classified_topic_path": turn.get("classified_topic_path"),
            "status": turn.get("status"),
            "created_at": turn.get("created_at"),
            "completed_at": turn.get("completed_at"),
            "deliberation_models": turn.get("deliberation_models"),
            "synthesis_model": turn.get("synthesis_model"),
        },
        "stages": trace_stages,
        "cost_summary": {
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
        },
    })


def _handle_get_logs(arguments: dict):
    _require_quorum()
    client = get_quorum_client()
    limit = arguments.get("limit", 50)

    query = client.table("orch_log").select("*")

    if arguments.get("session_id"):
        query = query.eq("session_id", arguments["session_id"])
    if arguments.get("turn_id"):
        query = query.eq("turn_id", arguments["turn_id"])
    if arguments.get("severity"):
        query = query.eq("severity", arguments["severity"])

    resp = query.order("timestamp", desc=True).limit(limit).execute()
    return _json_response(resp.data or [])


def _handle_model_performance(arguments: dict):
    _require_quorum()
    client = get_quorum_client()

    # Try materialized view first
    data = None
    try:
        query = client.table("v_model_performance").select("*")
        if arguments.get("model"):
            query = query.eq("model", arguments["model"])
        if arguments.get("category"):
            query = query.eq("category", arguments["category"])
        resp = query.execute()
        if resp.data:
            data = resp.data
    except Exception as view_err:
        data = None

    # Fall back to run_metrics if view is empty or missing
    if not data:
        try:
            query = client.table("run_metrics").select("*")
            if arguments.get("model"):
                query = query.eq("model", arguments["model"])
            if arguments.get("category"):
                query = query.eq("category", arguments["category"])
            resp = query.limit(100).execute()
            data = resp.data or []
            if data:
                data = {"source": "run_metrics", "note": "v_model_performance view unavailable or empty", "rows": data}
            else:
                data = {"source": "none", "note": "No performance data found in v_model_performance or run_metrics"}
        except Exception as metrics_err:
            data = {"error": f"Could not query performance data: view error={view_err}, metrics error={metrics_err}"}

    return _json_response(data)


def _handle_cost_summary(arguments: dict):
    _require_quorum()
    client = get_quorum_client()

    # Build the query — we need to join through stages → turns → sessions for filtering
    # Since Supabase REST API doesn't support complex aggregations, we fetch and compute in Python

    # Start from model_calls and work backwards
    # If session_id or user_id is provided, we need to filter through joins
    if arguments.get("session_id") or arguments.get("user_id"):
        # Get relevant turn IDs first
        turns_query = client.table("orch_turns").select("id, session_id")

        if arguments.get("session_id"):
            turns_query = turns_query.eq("session_id", arguments["session_id"])

        if arguments.get("user_id"):
            # Get sessions for this user first
            sessions_resp = client.table("orch_sessions").select("id").eq("user_id", arguments["user_id"]).execute()
            session_ids = [s["id"] for s in (sessions_resp.data or [])]
            if not session_ids:
                return _json_response({"total_tokens": 0, "total_cost_usd": 0, "per_model": {}, "note": "No sessions found for user"})
            turns_query = turns_query.in_("session_id", session_ids)

        turns_resp = turns_query.execute()
        turn_ids = [t["id"] for t in (turns_resp.data or [])]
        if not turn_ids:
            return _json_response({"total_tokens": 0, "total_cost_usd": 0, "per_model": {}, "note": "No turns found"})

        # Get stages for those turns
        stages_resp = client.table("orch_turn_stages").select("id").in_("turn_id", turn_ids).execute()
        stage_ids = [s["id"] for s in (stages_resp.data or [])]
        if not stage_ids:
            return _json_response({"total_tokens": 0, "total_cost_usd": 0, "per_model": {}, "note": "No stages found"})

        calls_query = client.table("orch_turn_model_calls").select("model_code, model_name, total_tokens, estimated_cost_usd, started_at").in_("turn_stage_id", stage_ids)
    else:
        calls_query = client.table("orch_turn_model_calls").select("model_code, model_name, total_tokens, estimated_cost_usd, started_at")

    # Apply date filters
    if arguments.get("date_from"):
        calls_query = calls_query.gte("started_at", arguments["date_from"])
    if arguments.get("date_to"):
        calls_query = calls_query.lte("started_at", arguments["date_to"] + "T23:59:59Z")

    resp = calls_query.execute()
    calls = resp.data or []

    # Aggregate
    total_tokens = 0
    total_cost = 0.0
    per_model = {}

    for call in calls:
        tokens = int(call.get("total_tokens") or 0)
        cost = float(call.get("estimated_cost_usd") or 0)
        model = call.get("model_code") or call.get("model_name") or "unknown"

        total_tokens += tokens
        total_cost += cost

        if model not in per_model:
            per_model[model] = {"total_tokens": 0, "total_cost_usd": 0.0, "call_count": 0}
        per_model[model]["total_tokens"] += tokens
        per_model[model]["total_cost_usd"] += cost
        per_model[model]["call_count"] += 1

    # Round costs
    for m in per_model.values():
        m["total_cost_usd"] = round(m["total_cost_usd"], 6)

    return _json_response({
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "total_calls": len(calls),
        "per_model": per_model,
    })


def _handle_stage_config(arguments: dict):
    _require_quorum()
    client = get_quorum_client()

    # Get the config version
    if arguments.get("version_number"):
        ver_resp = client.table("orch_config_versions").select("*").eq("version_number", arguments["version_number"]).limit(1).execute()
    else:
        ver_resp = client.table("orch_config_versions").select("*").eq("status", "active").limit(1).execute()

    if not ver_resp.data:
        return [TextContent(type="text", text="No config version found (active or specified)")]
    version = ver_resp.data[0]

    # Get stages for this version
    stages_resp = (
        client.table("orch_stages")
        .select("*")
        .eq("config_version_id", version["id"])
        .order("stage_number")
        .execute()
    )
    stages = stages_resp.data or []

    # Get models for each stage
    for stage in stages:
        try:
            models_resp = (
                client.table("orch_stage_models")
                .select("*")
                .eq("stage_id", stage["id"])
                .order("poll_order")
                .execute()
            )
            stage["models"] = models_resp.data or []
        except Exception:
            stage["models"] = []

    return _json_response({
        "version": version,
        "stages": stages,
    })


def _handle_update_stage_config(arguments: dict):
    _require_quorum()
    client = get_quorum_client()
    stage_id = arguments["stage_id"]
    updates = arguments["updates"]

    # Get the stage to find its config version
    stage_resp = client.table("orch_stages").select("*, config_version_id").eq("id", stage_id).execute()
    if not stage_resp.data:
        return [TextContent(type="text", text=f"Stage {stage_id} not found")]
    stage = stage_resp.data[0]

    # Check that the config version is draft
    ver_resp = client.table("orch_config_versions").select("status").eq("id", stage["config_version_id"]).execute()
    if not ver_resp.data:
        return [TextContent(type="text", text="Config version not found for this stage")]
    if ver_resp.data[0]["status"] != "draft":
        return [TextContent(
            type="text",
            text=f"Cannot update stage: config version status is '{ver_resp.data[0]['status']}'. Only 'draft' versions can be modified."
        )]

    # Apply updates
    resp = client.table("orch_stages").update(updates).eq("id", stage_id).execute()
    if resp.data:
        return _json_response({"message": "Stage updated successfully", "stage": resp.data[0]})
    return [TextContent(type="text", text=f"Update returned no data for stage {stage_id}")]


def _handle_user_detail(arguments: dict):
    _require_quorum()
    client = get_quorum_client()
    user_id = arguments["user_id"]

    # User preferences
    prefs = None
    try:
        prefs_resp = client.table("user_preferences").select("*").eq("user_id", user_id).execute()
        prefs = prefs_resp.data[0] if prefs_resp.data else None
    except Exception as e:
        prefs = {"error": str(e)}

    # Recent sessions (limit 5)
    sessions = []
    try:
        sessions_resp = (
            client.table("orch_sessions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        sessions = sessions_resp.data or []
    except Exception as e:
        sessions = [{"error": str(e)}]

    # Total usage — get all sessions, then turns, then stages, then model calls
    total_tokens = 0
    total_cost = 0.0
    try:
        all_sessions_resp = client.table("orch_sessions").select("id").eq("user_id", user_id).execute()
        session_ids = [s["id"] for s in (all_sessions_resp.data or [])]

        if session_ids:
            turns_resp = client.table("orch_turns").select("id").in_("session_id", session_ids).execute()
            turn_ids = [t["id"] for t in (turns_resp.data or [])]

            if turn_ids:
                stages_resp = client.table("orch_turn_stages").select("id").in_("turn_id", turn_ids).execute()
                stage_ids = [s["id"] for s in (stages_resp.data or [])]

                if stage_ids:
                    calls_resp = (
                        client.table("orch_turn_model_calls")
                        .select("total_tokens, estimated_cost_usd")
                        .in_("turn_stage_id", stage_ids)
                        .execute()
                    )
                    for call in (calls_resp.data or []):
                        total_tokens += int(call.get("total_tokens") or 0)
                        total_cost += float(call.get("estimated_cost_usd") or 0)
    except Exception as e:
        pass  # Usage stats are best-effort

    return _json_response({
        "user_id": user_id,
        "preferences": prefs,
        "recent_sessions": sessions,
        "usage_summary": {
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "total_sessions": len(sessions),
        },
    })

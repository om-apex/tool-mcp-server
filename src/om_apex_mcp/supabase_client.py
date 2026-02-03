"""Supabase client for Om Apex MCP Server.

Provides database access for tasks and decisions, replacing JSON file storage.
Loads credentials from centralized config folder.

Includes resilience features:
- Configurable timeout (default 10s)
- HTTP/1.1 fallback for environments with HTTP/2 issues
"""

import logging
import os
import platform
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger("om-apex-mcp")

# Global client instance
_supabase_client = None

# Timeout for Supabase operations (seconds)
SUPABASE_TIMEOUT = int(os.environ.get("SUPABASE_TIMEOUT", "10"))


def _get_config_path() -> Path:
    """Get path to centralized config folder.

    Uses .env.supabase.omapex-dashboard for Om Apex Holdings internal tools.
    The old .env.supabase file is now used only by AI Quorum.
    """
    if platform.system() == "Darwin":
        return Path.home() / "om-apex/config/.env.supabase.omapex-dashboard"
    elif platform.system() == "Windows":
        return Path("C:/Users/14042/om-apex/config/.env.supabase.omapex-dashboard")
    else:
        # Linux/other - check common locations
        home_config = Path.home() / "om-apex/config/.env.supabase.omapex-dashboard"
        if home_config.exists():
            return home_config
        return Path("/etc/om-apex/.env.supabase.omapex-dashboard")


def get_supabase_client():
    """Get or create the Supabase client.

    Returns:
        Supabase client instance, or None if configuration is missing.
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    # Load config from centralized location
    config_path = _get_config_path()
    if config_path.exists():
        load_dotenv(config_path)
        logger.info(f"Loaded Supabase config from: {config_path}")
    else:
        logger.warning(f"Supabase config not found at: {config_path}")

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

    if not url or not key:
        logger.warning("Supabase credentials not found - falling back to JSON storage")
        return None

    # Strip any whitespace from the key (can happen with copy/paste)
    key = key.strip().replace("\n", "").replace(" ", "")

    try:
        from supabase import create_client
        from supabase.lib.client_options import ClientOptions
        import httpx

        # Configure httpx with timeout and HTTP/1.1 (more reliable than HTTP/2 in some envs)
        # HTTP/2 can cause stream reset errors in containerized environments
        http_client = httpx.Client(
            timeout=httpx.Timeout(SUPABASE_TIMEOUT),
            http2=False,  # Use HTTP/1.1 for reliability
        )

        options = ClientOptions(
            postgrest_client_timeout=SUPABASE_TIMEOUT,
        )

        _supabase_client = create_client(url, key, options=options)

        # Replace the internal httpx client with our configured one
        # This ensures timeout and HTTP/1.1 settings are applied
        if hasattr(_supabase_client, 'postgrest') and hasattr(_supabase_client.postgrest, '_client'):
            _supabase_client.postgrest._client = http_client

        logger.info(f"Supabase client initialized (timeout={SUPABASE_TIMEOUT}s, http2=False)")
        return _supabase_client
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None


def is_supabase_available() -> bool:
    """Check if Supabase is configured and available."""
    return get_supabase_client() is not None


# =============================================================================
# Task Operations
# =============================================================================

def get_tasks(
    company: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    owner: Optional[str] = None,
) -> list[dict]:
    """Get tasks from Supabase with optional filters.

    Returns:
        List of task dictionaries.
    """
    client = get_supabase_client()
    if not client:
        return []

    query = client.table("tasks").select("*")

    if company:
        query = query.ilike("company", company)
    if category:
        query = query.ilike("category", category)
    if status:
        query = query.ilike("status", status)
    if owner:
        query = query.ilike("owner", owner)

    response = query.order("created_at", desc=True).execute()
    return response.data or []


def add_task(task: dict) -> dict:
    """Add a new task to Supabase.

    Args:
        task: Task dictionary with id, description, category, etc.

    Returns:
        The created task.
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase not available")

    response = client.table("tasks").insert(task).execute()
    return response.data[0] if response.data else task


def update_task(task_id: str, updates: dict) -> Optional[dict]:
    """Update a task in Supabase.

    Args:
        task_id: The task ID (e.g., TASK-001)
        updates: Dictionary of fields to update

    Returns:
        The updated task, or None if not found.
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase not available")

    response = client.table("tasks").update(updates).eq("id", task_id).execute()
    return response.data[0] if response.data else None


def get_next_task_id() -> str:
    """Get the next available task ID."""
    client = get_supabase_client()
    if not client:
        return "TASK-001"

    response = (
        client.table("tasks")
        .select("id")
        .like("id", "TASK-%")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if response.data:
        last_id = response.data[0]["id"]
        try:
            num = int(last_id.split("-")[1])
            return f"TASK-{num + 1:03d}"
        except (ValueError, IndexError):
            pass

    return "TASK-001"


# =============================================================================
# Decision Operations
# =============================================================================

def get_decisions(
    area: Optional[str] = None,
    company: Optional[str] = None,
) -> list[dict]:
    """Get decisions from Supabase with optional filters.

    Returns:
        List of decision dictionaries.
    """
    client = get_supabase_client()
    if not client:
        return []

    query = client.table("decisions").select("*")

    if area:
        query = query.ilike("area", f"%{area}%")
    if company:
        query = query.ilike("company", company)

    response = query.order("date_decided", desc=True).execute()
    return response.data or []


def add_decision(decision: dict) -> dict:
    """Add a new decision to Supabase.

    Args:
        decision: Decision dictionary with id, area, decision, rationale, etc.

    Returns:
        The created decision.
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase not available")

    response = client.table("decisions").insert(decision).execute()
    return response.data[0] if response.data else decision


def get_next_decision_id() -> str:
    """Get the next available decision ID."""
    client = get_supabase_client()
    if not client:
        return "TECH-001"

    response = (
        client.table("decisions")
        .select("id")
        .like("id", "TECH-%")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if response.data:
        last_id = response.data[0]["id"]
        try:
            num = int(last_id.split("-")[1])
            return f"TECH-{num + 1:03d}"
        except (ValueError, IndexError):
            pass

    return "TECH-001"


def get_task_count() -> dict:
    """Get task counts by status.

    Returns:
        Dictionary with total, pending, in_progress, completed, high_priority counts.
    """
    client = get_supabase_client()
    if not client:
        return {"total": 0, "pending": 0, "in_progress": 0, "completed": 0, "high_priority": 0}

    all_tasks = client.table("tasks").select("status, priority").execute()
    tasks = all_tasks.data or []

    pending = [t for t in tasks if t.get("status") == "pending"]
    in_progress = [t for t in tasks if t.get("status") == "in_progress"]
    completed = [t for t in tasks if t.get("status") == "completed"]
    high_priority = [t for t in tasks if t.get("priority") == "High" and t.get("status") != "completed"]

    return {
        "total": len(tasks),
        "pending": len(pending),
        "in_progress": len(in_progress),
        "completed": len(completed),
        "high_priority": len(high_priority),
    }

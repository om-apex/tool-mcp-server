"""Supabase client for Om Apex MCP Server.

Provides database access for tasks and decisions, replacing JSON file storage.
Loads credentials from centralized config folder.

Includes resilience features:
- Configurable timeout (default 10s)
- HTTP/1.1 fallback for environments with HTTP/2 issues
- Comprehensive error handling to prevent crashes
- Graceful fallback to None when Supabase is unavailable
"""

import logging
import os
import platform
import sys
import traceback
from pathlib import Path
from typing import Optional

logger = logging.getLogger("om-apex-mcp")

# Try to import dotenv, but don't fail if it's not available
try:
    from dotenv import load_dotenv
except ImportError:
    logger.warning("python-dotenv not installed, will use environment variables only")
    def load_dotenv(path):
        """Stub for load_dotenv when dotenv is not installed."""
        pass

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

    This function is called during server startup and during tool execution.
    It must never raise an exception - always returns None on failure.

    Returns:
        Supabase client instance, or None if configuration is missing or creation fails.
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    try:
        # Load config from centralized location
        config_path = _get_config_path()
        try:
            if config_path.exists():
                load_dotenv(config_path)
                logger.info(f"Loaded Supabase config from: {config_path}")
            else:
                logger.warning(f"Supabase config not found at: {config_path}")
        except Exception as env_err:
            logger.warning(f"Error loading .env file: {env_err}")

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

        if not url:
            logger.warning("SUPABASE_URL not set - Supabase disabled")
            return None
        if not key:
            logger.warning("SUPABASE_SERVICE_KEY/SUPABASE_ANON_KEY not set - Supabase disabled")
            return None

        # Strip any whitespace from the key (can happen with copy/paste)
        key = key.strip().replace("\n", "").replace(" ", "")

        # Import supabase library
        try:
            from supabase import create_client
        except ImportError as import_err:
            logger.warning(f"Supabase library not installed: {import_err}")
            logger.warning("Install with: pip install supabase")
            return None

        # Create client with default settings first
        logger.info(f"Creating Supabase client for URL: {url[:30]}...")
        _supabase_client = create_client(url, key)

        # Try to configure httpx for HTTP/1.1 and timeout (more reliable in containers)
        # This is a best-effort optimization - client works without it
        try:
            import httpx

            http_client = httpx.Client(
                timeout=httpx.Timeout(SUPABASE_TIMEOUT),
                http2=False,  # HTTP/1.1 avoids stream reset errors
            )

            # Apply to postgrest client if accessible
            if hasattr(_supabase_client, 'postgrest'):
                postgrest = _supabase_client.postgrest
                if hasattr(postgrest, '_client'):
                    postgrest._client = http_client
                    logger.info(f"Supabase client configured (timeout={SUPABASE_TIMEOUT}s, http2=False)")
                else:
                    logger.info("Supabase client initialized (default httpx settings)")
            else:
                logger.info("Supabase client initialized (default settings)")
        except ImportError:
            logger.info("httpx not available for custom configuration")
        except Exception as config_err:
            # httpx configuration failed but client still works
            logger.warning(f"Could not configure httpx: {config_err}")
            logger.info("Supabase client initialized (default settings)")

        # Test connection with a simple query
        try:
            _supabase_client.table("tasks").select("id").limit(1).execute()
            logger.info("Supabase connection verified")
        except Exception as conn_err:
            logger.warning(f"Supabase connection test failed (may still work): {conn_err}")

        return _supabase_client

    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
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
    task_type: Optional[str] = None,
) -> list[dict]:
    """Get tasks from Supabase with optional filters.

    Returns:
        List of task dictionaries. Empty list on error.
    """
    try:
        client = get_supabase_client()
        if not client:
            logger.debug("get_tasks: Supabase not available")
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
        if task_type:
            query = query.eq("task_type", task_type)

        response = query.order("created_at", desc=True).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return []


def add_task(task: dict) -> dict:
    """Add a new task to Supabase.

    Args:
        task: Task dictionary with id, description, category, etc.

    Returns:
        The created task.

    Raises:
        RuntimeError: If Supabase is not available or insert fails.
    """
    try:
        client = get_supabase_client()
        if not client:
            raise RuntimeError("Supabase not available - cannot add task")

        response = client.table("tasks").insert(task).execute()
        if response.data:
            logger.info(f"Task created: {task.get('id', 'unknown')}")
            return response.data[0]
        else:
            logger.warning(f"Task insert returned no data: {task}")
            return task
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Error adding task: {e}")
        logger.error(f"Task data: {task}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise RuntimeError(f"Failed to add task: {e}") from e


def update_task(task_id: str, updates: dict) -> Optional[dict]:
    """Update a task in Supabase.

    Args:
        task_id: The task ID (e.g., TASK-001)
        updates: Dictionary of fields to update

    Returns:
        The updated task, or None if not found.

    Raises:
        RuntimeError: If Supabase is not available.
    """
    try:
        client = get_supabase_client()
        if not client:
            raise RuntimeError("Supabase not available - cannot update task")

        response = client.table("tasks").update(updates).eq("id", task_id).execute()
        if response.data:
            logger.info(f"Task updated: {task_id}")
            return response.data[0]
        else:
            logger.warning(f"Task not found for update: {task_id}")
            return None
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {e}")
        logger.error(f"Updates: {updates}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise RuntimeError(f"Failed to update task: {e}") from e


def get_next_task_id() -> str:
    """Get the next available task ID.

    Returns:
        Next task ID (e.g., TASK-042). Returns TASK-001 on error.
    """
    try:
        client = get_supabase_client()
        if not client:
            logger.debug("get_next_task_id: Supabase not available, returning TASK-001")
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
            except (ValueError, IndexError) as parse_err:
                logger.warning(f"Could not parse task ID '{last_id}': {parse_err}")
                pass

        return "TASK-001"
    except Exception as e:
        logger.error(f"Error getting next task ID: {e}")
        return "TASK-001"


def get_task_queue(
    limit: int = 10,
    owner: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    company: Optional[str] = None,
) -> list[dict]:
    """Get a compact task queue sorted by priority then age.

    Returns only essential fields (id, description truncated to 80 chars,
    priority, status, owner, company) for minimal token usage.

    Args:
        limit: Max tasks to return (default 10).
        owner: Filter by owner name (optional).
        priority: Filter by priority: High, Medium, Low (optional).
        status: Filter by status (optional, defaults to pending + in_progress).
        company: Filter by company name (optional).

    Returns:
        List of compact task dicts sorted by priority (High→Medium→Low) then age.
    """
    try:
        client = get_supabase_client()
        if not client:
            logger.debug("get_task_queue: Supabase not available")
            return []

        query = client.table("tasks").select(
            "id, description, priority, status, owner, company, created_at"
        )

        # Status filter: default to pending + in_progress
        if status:
            query = query.ilike("status", status)
        else:
            query = query.or_("status.eq.pending,status.eq.in_progress")

        if owner:
            query = query.ilike("owner", owner)
        if priority:
            query = query.ilike("priority", priority)
        if company:
            query = query.ilike("company", company)

        # Fetch more than needed, sort in Python by priority then age
        response = query.order("created_at", desc=False).limit(limit * 3).execute()
        tasks = response.data or []

        # Sort by priority (High=0, Medium=1, Low=2) then age (oldest first)
        priority_order = {"High": 0, "Medium": 1, "Low": 2}
        tasks.sort(key=lambda t: (
            priority_order.get(t.get("priority", "Low"), 3),
            t.get("created_at", ""),
        ))

        # Truncate descriptions and take top N
        for t in tasks:
            desc = t.get("description", "")
            if len(desc) > 80:
                t["description"] = desc[:77] + "..."

        return tasks[:limit]
    except Exception as e:
        logger.error(f"Error fetching task queue: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return []


# =============================================================================
# Decision Operations
# =============================================================================

def get_decisions(
    area: Optional[str] = None,
    company: Optional[str] = None,
) -> list[dict]:
    """Get decisions from Supabase with optional filters.

    Returns:
        List of decision dictionaries. Empty list on error.
    """
    try:
        client = get_supabase_client()
        if not client:
            logger.debug("get_decisions: Supabase not available")
            return []

        query = client.table("decisions").select("*")

        if area:
            query = query.ilike("area", f"%{area}%")
        if company:
            query = query.ilike("company", company)

        response = query.order("date_decided", desc=True).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Error fetching decisions: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return []


def add_decision(decision: dict) -> dict:
    """Add a new decision to Supabase.

    Args:
        decision: Decision dictionary with id, area, decision, rationale, etc.

    Returns:
        The created decision.

    Raises:
        RuntimeError: If Supabase is not available or insert fails.
    """
    try:
        client = get_supabase_client()
        if not client:
            raise RuntimeError("Supabase not available - cannot add decision")

        response = client.table("decisions").insert(decision).execute()
        if response.data:
            logger.info(f"Decision created: {decision.get('id', 'unknown')}")
            return response.data[0]
        else:
            logger.warning(f"Decision insert returned no data: {decision}")
            return decision
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Error adding decision: {e}")
        logger.error(f"Decision data: {decision}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise RuntimeError(f"Failed to add decision: {e}") from e


def get_next_decision_id() -> str:
    """Get the next available decision ID.

    Returns:
        Next decision ID (e.g., TECH-042). Returns TECH-001 on error.
    """
    try:
        client = get_supabase_client()
        if not client:
            logger.debug("get_next_decision_id: Supabase not available, returning TECH-001")
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
            except (ValueError, IndexError) as parse_err:
                logger.warning(f"Could not parse decision ID '{last_id}': {parse_err}")
                pass

        return "TECH-001"
    except Exception as e:
        logger.error(f"Error getting next decision ID: {e}")
        return "TECH-001"


def get_task_count() -> dict:
    """Get task counts by status.

    Returns:
        Dictionary with total, pending, in_progress, completed, high_priority counts.
        Returns zeros on error.
    """
    default_counts = {"total": 0, "pending": 0, "in_progress": 0, "completed": 0, "high_priority": 0}

    try:
        client = get_supabase_client()
        if not client:
            logger.debug("get_task_count: Supabase not available")
            return default_counts

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
    except Exception as e:
        logger.error(f"Error getting task counts: {e}")
        return default_counts


# =============================================================================
# Document Template Operations
# =============================================================================

def get_document_templates() -> list[dict]:
    """Get all document templates from Supabase.

    Returns:
        List of template dictionaries with id, name, filename, content, variables.
    """
    client = get_supabase_client()
    if not client:
        return []

    try:
        response = client.table("document_templates").select("*").order("name").execute()
        return response.data or []
    except Exception as e:
        logger.warning(f"Could not fetch document_templates: {e}")
        return []


def get_document_template(template_id: str) -> Optional[dict]:
    """Get a single document template by ID.

    Args:
        template_id: Template ID (e.g., 'operating-agreement-template')

    Returns:
        Template dictionary or None if not found.
    """
    client = get_supabase_client()
    if not client:
        return None

    try:
        response = client.table("document_templates").select("*").eq("id", template_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.warning(f"Could not fetch template {template_id}: {e}")
        return None


def upsert_document_template(template: dict) -> dict:
    """Insert or update a document template in Supabase.

    Args:
        template: Template dict with id, name, filename, content, etc.

    Returns:
        The upserted template.
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase not available")

    response = client.table("document_templates").upsert(template).execute()
    return response.data[0] if response.data else template


def has_document_templates_table() -> bool:
    """Check if document_templates table exists and is accessible."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("document_templates").select("id").limit(1).execute()
        return True
    except Exception:
        return False


# =============================================================================
# Company Config Operations
# =============================================================================

def get_company_configs() -> list[dict]:
    """Get all company configs from Supabase.

    Returns:
        List of config dictionaries with id, company_name, short_name, config (JSONB).
    """
    client = get_supabase_client()
    if not client:
        return []

    try:
        response = client.table("company_configs").select("*").order("company_name").execute()
        return response.data or []
    except Exception as e:
        logger.warning(f"Could not fetch company_configs: {e}")
        return []


def get_company_config(company_name: str) -> Optional[dict]:
    """Get a company config by name (case-insensitive partial match).

    Args:
        company_name: Company name to search for

    Returns:
        Config dictionary or None if not found.
    """
    client = get_supabase_client()
    if not client:
        return None

    try:
        # Try exact match first
        response = client.table("company_configs").select("*").ilike("company_name", company_name).execute()
        if response.data:
            return response.data[0]

        # Try short_name match
        response = client.table("company_configs").select("*").ilike("short_name", company_name).execute()
        if response.data:
            return response.data[0]

        # Try partial match
        response = client.table("company_configs").select("*").ilike("company_name", f"%{company_name}%").execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.warning(f"Could not fetch config for {company_name}: {e}")
        return None


def upsert_company_config(config: dict) -> dict:
    """Insert or update a company config in Supabase.

    Args:
        config: Config dict with id, company_name, short_name, config (JSONB).

    Returns:
        The upserted config.
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase not available")

    response = client.table("company_configs").upsert(config).execute()
    return response.data[0] if response.data else config


def has_company_configs_table() -> bool:
    """Check if company_configs table exists and is accessible."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("company_configs").select("id").limit(1).execute()
        return True
    except Exception:
        return False


# =============================================================================
# Session Handoff Operations
# =============================================================================

def get_session_handoff() -> Optional[dict]:
    """Get the current session handoff from Supabase.

    Returns:
        Handoff dictionary with content, created_by, interface, timestamps.
        None if no handoff exists or Supabase unavailable.
    """
    try:
        client = get_supabase_client()
        if not client:
            logger.debug("get_session_handoff: Supabase not available")
            return None

        response = client.table("session_handoff").select("*").eq("id", 1).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching session handoff: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return None


def save_session_handoff(content: str, created_by: str, interface: str, checkpoint: bool = False) -> dict:
    """Save (upsert) the session handoff to Supabase.

    Archives the previous handoff to history before overwriting,
    unless checkpoint=True (lightweight update, no history archive).

    Args:
        content: Full markdown handoff content.
        created_by: Who wrote this ("Nishad" or "Sumedha").
        interface: Which Claude interface ("code", "chat", "cowork", "code-app").
        checkpoint: If True, skip archiving to history (mid-session checkpoint).

    Returns:
        The saved handoff record.

    Raises:
        RuntimeError: If Supabase is not available or save fails.
    """
    try:
        client = get_supabase_client()
        if not client:
            raise RuntimeError("Supabase not available - cannot save handoff")

        # Archive previous handoff to history (skip for checkpoints)
        if not checkpoint:
            try:
                existing = client.table("session_handoff").select("*").eq("id", 1).execute()
                if existing.data:
                    old = existing.data[0]
                    from datetime import datetime
                    client.table("session_handoff_history").insert({
                        "content": old["content"],
                        "created_by": old["created_by"],
                        "interface": old["interface"],
                        "session_date": old.get("updated_at", datetime.now().isoformat())[:10],
                    }).execute()
                    logger.info("Previous handoff archived to history")
            except Exception as archive_err:
                logger.warning(f"Could not archive previous handoff: {archive_err}")

        # Upsert current handoff
        from datetime import datetime
        handoff = {
            "id": 1,
            "content": content,
            "created_by": created_by,
            "interface": interface,
            "updated_at": datetime.now().isoformat(),
        }

        response = client.table("session_handoff").upsert(handoff).execute()
        if response.data:
            mode = "checkpoint" if checkpoint else "full"
            logger.info(f"Session handoff saved ({mode}) by {created_by} via {interface}")
            return response.data[0]
        return handoff
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Error saving session handoff: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise RuntimeError(f"Failed to save handoff: {e}") from e


def get_handoff_history(limit: int = 10) -> list[dict]:
    """Get previous session handoffs from history.

    Args:
        limit: Max number of records to return.

    Returns:
        List of historical handoff records, newest first.
    """
    try:
        client = get_supabase_client()
        if not client:
            return []

        response = (
            client.table("session_handoff_history")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception as e:
        logger.error(f"Error fetching handoff history: {e}")
        return []


def delete_document_template(template_id: str) -> bool:
    """Delete a document template from Supabase.

    Args:
        template_id: Template ID (e.g., 'operating-agreement-template')

    Returns:
        True if deleted, False if not found or error.
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase not available")

    try:
        response = client.table("document_templates").delete().eq("id", template_id).execute()
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Failed to delete template {template_id}: {e}")
        return False

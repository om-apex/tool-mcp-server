"""Supabase client for Om Cortex project (separate from Owner Portal and AI Quorum).

Reads from CORTEX_SUPABASE_URL + CORTEX_SUPABASE_SERVICE_KEY env vars.
Falls back to ~/om-apex/config/.env.cortex if env vars not set.

Includes resilience features:
- Configurable timeout (default 10s)
- HTTP/1.1 fallback for environments with HTTP/2 issues
- Comprehensive error handling to prevent crashes
- Graceful fallback to None when Supabase is unavailable
"""

import logging
import os
import platform
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
_cortex_client = None

# Timeout for Supabase operations (seconds)
CORTEX_SUPABASE_TIMEOUT = int(os.environ.get("CORTEX_SUPABASE_TIMEOUT", "10"))


def _get_cortex_config_path() -> Path:
    """Get path to Om Cortex Supabase config."""
    if platform.system() == "Darwin":
        return Path.home() / "om-apex/config/.env.cortex"
    elif platform.system() == "Windows":
        return Path("C:/Users/14042/om-apex/config/.env.cortex")
    else:
        home_config = Path.home() / "om-apex/config/.env.cortex"
        if home_config.exists():
            return home_config
        return Path("/etc/om-apex/.env.cortex")


def get_cortex_client():
    """Get or create the Supabase client for Om Cortex.

    This function is called during tool execution.
    It must never raise an exception - always returns None on failure.

    Returns:
        Supabase client instance, or None if configuration is missing or creation fails.
    """
    global _cortex_client

    if _cortex_client is not None:
        return _cortex_client

    try:
        # First check for dedicated CORTEX_ env vars
        url = os.environ.get("CORTEX_SUPABASE_URL")
        key = os.environ.get("CORTEX_SUPABASE_SERVICE_KEY")

        # Fall back to config file if env vars not set
        if not url or not key:
            config_path = _get_cortex_config_path()
            try:
                if config_path.exists():
                    load_dotenv(config_path)
                    logger.info(f"Loaded Cortex Supabase config from: {config_path}")
                else:
                    logger.warning(f"Cortex Supabase config not found at: {config_path}")
            except Exception as env_err:
                logger.warning(f"Error loading .env file: {env_err}")

            # Re-check after loading dotenv
            if not url:
                url = os.environ.get("CORTEX_SUPABASE_URL")
            if not key:
                key = os.environ.get("CORTEX_SUPABASE_SERVICE_KEY")

        if not url:
            logger.warning("CORTEX_SUPABASE_URL not set - Cortex Supabase disabled")
            return None
        if not key:
            logger.warning("CORTEX_SUPABASE_SERVICE_KEY not set - Cortex Supabase disabled")
            return None

        # Strip any whitespace from the key
        key = key.strip().replace("\n", "").replace(" ", "")

        # Import supabase library
        try:
            from supabase import create_client
        except ImportError as import_err:
            logger.warning(f"Supabase library not installed: {import_err}")
            return None

        # Create client
        logger.info(f"Creating Cortex Supabase client for URL: {url[:30]}...")
        _cortex_client = create_client(url, key)

        # Try to configure httpx for HTTP/1.1 and timeout
        try:
            import httpx

            http_client = httpx.Client(
                timeout=httpx.Timeout(CORTEX_SUPABASE_TIMEOUT),
                http2=False,
            )

            if hasattr(_cortex_client, 'postgrest'):
                postgrest = _cortex_client.postgrest
                if hasattr(postgrest, '_client'):
                    postgrest._client = http_client
                    logger.info(f"Cortex Supabase client configured (timeout={CORTEX_SUPABASE_TIMEOUT}s, http2=False)")
                else:
                    logger.info("Cortex Supabase client initialized (default httpx settings)")
            else:
                logger.info("Cortex Supabase client initialized (default settings)")
        except ImportError:
            logger.info("httpx not available for custom configuration")
        except Exception as config_err:
            logger.warning(f"Could not configure httpx: {config_err}")
            logger.info("Cortex Supabase client initialized (default settings)")

        # Test connection with prodsupport_incidents table
        try:
            _cortex_client.table("prodsupport_incidents").select("id").limit(1).execute()
            logger.info("Cortex Supabase connection verified (prodsupport_incidents)")
        except Exception as conn_err:
            logger.warning(f"Cortex Supabase connection test failed (may still work): {conn_err}")

        return _cortex_client

    except Exception as e:
        logger.error(f"Failed to create Cortex Supabase client: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return None


def reset_cortex_client() -> None:
    """Clear the cached Cortex Supabase client so it will be recreated on next call."""
    global _cortex_client
    _cortex_client = None
    logger.info("Cortex Supabase client cache cleared")


def is_cortex_available() -> bool:
    """Check if Om Cortex Supabase is configured and available."""
    return get_cortex_client() is not None


# =============================================================================
# DB helpers for prodsupport_incidents / prodsupport_events
# =============================================================================

def create_incident(incident: dict) -> dict:
    """Insert a row into prodsupport_incidents.

    Args:
        incident: Dict matching the prodsupport_incidents columns.

    Returns:
        The created row as a dict.

    Raises:
        RuntimeError: If Cortex Supabase is not available or insert fails.
    """
    client = get_cortex_client()
    if client is None:
        raise RuntimeError("Cortex Supabase is not available")

    resp = client.table("prodsupport_incidents").insert(incident).execute()
    if resp.data:
        return resp.data[0]
    raise RuntimeError(f"Insert returned no data: {resp}")


def create_incident_event(event: dict) -> dict:
    """Insert a row into prodsupport_events (audit trail).

    Args:
        event: Dict matching the prodsupport_events columns.

    Returns:
        The created row as a dict.

    Raises:
        RuntimeError: If Cortex Supabase is not available or insert fails.
    """
    client = get_cortex_client()
    if client is None:
        raise RuntimeError("Cortex Supabase is not available")

    resp = client.table("prodsupport_events").insert(event).execute()
    if resp.data:
        return resp.data[0]
    raise RuntimeError(f"Insert returned no data: {resp}")


def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Query prodsupport_incidents with optional filters.

    Args:
        status: Filter by status (open, investigating, etc.)
        severity: Filter by severity (SEV-1, SEV-2, SEV-3)
        project: Filter by project name
        limit: Max rows to return (default 10)

    Returns:
        List of incident dicts, ordered by created_at DESC.

    Raises:
        RuntimeError: If Cortex Supabase is not available.
    """
    client = get_cortex_client()
    if client is None:
        raise RuntimeError("Cortex Supabase is not available")

    query = client.table("prodsupport_incidents").select(
        "id, fingerprint, title, project, severity, category, component, "
        "status, assigned_to, occurrence_count, first_seen_at, last_seen_at, "
        "created_at, source"
    )

    if status:
        query = query.eq("status", status)
    if severity:
        query = query.eq("severity", severity)
    if project:
        query = query.eq("project", project)

    query = query.order("created_at", desc=True).limit(limit)
    resp = query.execute()
    return resp.data or []

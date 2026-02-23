"""Supabase client for AI Quorum project (separate from Owner Portal).

Reads from QUORUM_SUPABASE_URL + QUORUM_SUPABASE_SERVICE_KEY env vars.
Falls back to ~/om-apex/config/.env.supabase if env vars not set.

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
_quorum_client = None

# Timeout for Supabase operations (seconds)
QUORUM_SUPABASE_TIMEOUT = int(os.environ.get("QUORUM_SUPABASE_TIMEOUT", "10"))


def _get_quorum_config_path() -> Path:
    """Get path to AI Quorum Supabase config.

    Uses .env.supabase (NOT .env.supabase.omapex-dashboard — that's the Owner Portal).
    """
    if platform.system() == "Darwin":
        return Path.home() / "om-apex/config/.env.supabase"
    elif platform.system() == "Windows":
        return Path("C:/Users/14042/om-apex/config/.env.supabase")
    else:
        home_config = Path.home() / "om-apex/config/.env.supabase"
        if home_config.exists():
            return home_config
        return Path("/etc/om-apex/.env.supabase")


def get_quorum_client():
    """Get or create the Supabase client for AI Quorum.

    This function is called during tool execution.
    It must never raise an exception - always returns None on failure.

    Returns:
        Supabase client instance, or None if configuration is missing or creation fails.
    """
    global _quorum_client

    if _quorum_client is not None:
        return _quorum_client

    try:
        # First check for dedicated QUORUM_ env vars
        url = os.environ.get("QUORUM_SUPABASE_URL")
        key = os.environ.get("QUORUM_SUPABASE_SERVICE_KEY")

        # Fall back to config file if env vars not set
        if not url or not key:
            config_path = _get_quorum_config_path()
            try:
                if config_path.exists():
                    load_dotenv(config_path)
                    logger.info(f"Loaded Quorum Supabase config from: {config_path}")
                else:
                    logger.warning(f"Quorum Supabase config not found at: {config_path}")
            except Exception as env_err:
                logger.warning(f"Error loading .env file: {env_err}")

            # Re-check after loading dotenv — these are the standard names in .env.supabase
            if not url:
                url = os.environ.get("QUORUM_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
            if not key:
                key = os.environ.get("QUORUM_SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

        if not url:
            logger.warning("QUORUM_SUPABASE_URL not set - Quorum Supabase disabled")
            return None
        if not key:
            logger.warning("QUORUM_SUPABASE_SERVICE_KEY not set - Quorum Supabase disabled")
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
        logger.info(f"Creating Quorum Supabase client for URL: {url[:30]}...")
        _quorum_client = create_client(url, key)

        # Try to configure httpx for HTTP/1.1 and timeout
        try:
            import httpx

            http_client = httpx.Client(
                timeout=httpx.Timeout(QUORUM_SUPABASE_TIMEOUT),
                http2=False,
            )

            if hasattr(_quorum_client, 'postgrest'):
                postgrest = _quorum_client.postgrest
                if hasattr(postgrest, '_client'):
                    postgrest._client = http_client
                    logger.info(f"Quorum Supabase client configured (timeout={QUORUM_SUPABASE_TIMEOUT}s, http2=False)")
                else:
                    logger.info("Quorum Supabase client initialized (default httpx settings)")
            else:
                logger.info("Quorum Supabase client initialized (default settings)")
        except ImportError:
            logger.info("httpx not available for custom configuration")
        except Exception as config_err:
            logger.warning(f"Could not configure httpx: {config_err}")
            logger.info("Quorum Supabase client initialized (default settings)")

        # Test connection with orch_sessions table
        try:
            _quorum_client.table("orch_sessions").select("id").limit(1).execute()
            logger.info("Quorum Supabase connection verified (orch_sessions)")
        except Exception as conn_err:
            logger.warning(f"Quorum Supabase connection test failed (may still work): {conn_err}")

        return _quorum_client

    except Exception as e:
        logger.error(f"Failed to create Quorum Supabase client: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return None


def reset_quorum_client() -> None:
    """Clear the cached Quorum Supabase client so it will be recreated on next call.

    Use this when encountering 401 errors — the cached client may have a stale key.
    """
    global _quorum_client
    _quorum_client = None
    logger.info("Quorum Supabase client cache cleared")


def is_quorum_available() -> bool:
    """Check if AI Quorum Supabase is configured and available."""
    return get_quorum_client() is not None

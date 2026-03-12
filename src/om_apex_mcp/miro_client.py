"""Miro REST API v2 client for Om Apex Holdings board management.

Reads from MIRO_OAUTH_TOKEN env var.
Falls back to ~/om-apex/config/.env.miro if env var not set.

Follows the cloudflare_client.py singleton pattern.
"""

import logging
import os
import platform
import traceback
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("om-apex-mcp")

# Global config cache
_miro_config: Optional[dict] = None

MIRO_BASE_URL = "https://api.miro.com/v2"
MIRO_TIMEOUT = int(os.environ.get("MIRO_TIMEOUT", "30"))


def _get_miro_config_path() -> Path:
    """Get path to Miro config file."""
    if platform.system() == "Darwin":
        return Path.home() / "om-apex/config/.env.miro"
    elif platform.system() == "Windows":
        return Path("C:/Users/14042/om-apex/config/.env.miro")
    else:
        home_config = Path.home() / "om-apex/config/.env.miro"
        if home_config.exists():
            return home_config
        return Path("/etc/om-apex/.env.miro")


def get_miro_config() -> Optional[dict]:
    """Get Miro API credentials.

    Returns a dict with oauth_token, or None if not configured.
    Never raises — returns None on any failure.
    """
    global _miro_config

    if _miro_config is not None:
        return _miro_config

    try:
        # Check env var first
        oauth_token = os.environ.get("MIRO_OAUTH_TOKEN")

        # Fall back to config file
        if not oauth_token:
            config_path = _get_miro_config_path()
            try:
                if config_path.exists():
                    from dotenv import load_dotenv
                    load_dotenv(config_path)
                    logger.info(f"Loaded Miro config from: {config_path}")
                else:
                    logger.warning(f"Miro config not found at: {config_path}")
            except Exception as env_err:
                logger.warning(f"Error loading .env.miro: {env_err}")
                # Try manual parse as fallback
                try:
                    if config_path.exists():
                        for line in config_path.read_text().splitlines():
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, _, v = line.partition("=")
                                os.environ[k.strip()] = v.strip()
                except Exception:
                    pass

            oauth_token = os.environ.get("MIRO_OAUTH_TOKEN")

        if not oauth_token:
            logger.warning("MIRO_OAUTH_TOKEN not set — Miro disabled")
            return None

        _miro_config = {
            "oauth_token": oauth_token.strip(),
        }
        logger.info("Miro config loaded successfully")
        return _miro_config

    except Exception as e:
        logger.error(f"Failed to load Miro config: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return None


def reset_miro_config() -> None:
    """Clear cached Miro config so it reloads on next call."""
    global _miro_config
    _miro_config = None
    logger.info("Miro config cache cleared")


def is_miro_available() -> bool:
    """Check if Miro is configured and available."""
    return get_miro_config() is not None


def _get_headers() -> dict:
    """Build auth headers for Miro API requests."""
    cfg = get_miro_config()
    if not cfg:
        raise RuntimeError("Miro is not configured")
    return {
        "Authorization": f"Bearer {cfg['oauth_token']}",
        "Content-Type": "application/json",
    }


def _raise_for_miro_error(resp: httpx.Response, context: str = "") -> None:
    """Parse Miro API error responses and raise with clear message."""
    if resp.status_code == 204:
        return
    if resp.status_code == 429:
        raise RuntimeError(
            f"Miro API rate limit exceeded{' (' + context + ')' if context else ''}. "
            "Please wait before retrying."
        )
    if resp.status_code == 401:
        raise RuntimeError(
            f"Miro API authentication failed{' (' + context + ')' if context else ''}. "
            "Check MIRO_OAUTH_TOKEN is valid."
        )
    if resp.status_code == 404:
        raise RuntimeError(
            f"Miro resource not found{' (' + context + ')' if context else ''}."
        )
    if resp.status_code >= 400:
        try:
            data = resp.json()
            message = data.get("message", "") or data.get("error", "")
            code = data.get("code", "") or data.get("status", resp.status_code)
            raise RuntimeError(
                f"Miro API error {code}{' (' + context + ')' if context else ''}: {message}"
            )
        except (ValueError, KeyError):
            resp.raise_for_status()


# =============================================================================
# Async API functions
# =============================================================================

async def create_board(name: str, description: str = "") -> dict:
    """Create a new Miro board.

    Args:
        name: Board name
        description: Optional board description

    Returns:
        Dict with id, name, and viewLink of the created board.
    """
    headers = _get_headers()
    body = {"name": name}
    if description:
        body["description"] = description

    async with httpx.AsyncClient(timeout=MIRO_TIMEOUT) as client:
        resp = await client.post(
            f"{MIRO_BASE_URL}/boards",
            headers=headers,
            json=body,
        )
        _raise_for_miro_error(resp, "create_board")
        data = resp.json()
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "viewLink": data.get("viewLink"),
        }


async def list_boards(query: str = "", limit: int = 50) -> list[dict]:
    """List boards accessible to the authenticated user.

    Handles pagination automatically — loops until all pages are fetched.

    Args:
        query: Optional search query to filter boards
        limit: Max boards to return (default 50)

    Returns:
        List of board dicts with id, name, viewLink, createdAt.
    """
    headers = _get_headers()
    all_boards = []
    offset = ""

    async with httpx.AsyncClient(timeout=MIRO_TIMEOUT) as client:
        while True:
            params = {"limit": min(limit - len(all_boards), 50)}
            if query:
                params["query"] = query
            if offset:
                params["offset"] = offset

            resp = await client.get(
                f"{MIRO_BASE_URL}/boards",
                headers=headers,
                params=params,
            )
            _raise_for_miro_error(resp, "list_boards")
            data = resp.json()

            boards = data.get("data", [])
            for board in boards:
                all_boards.append({
                    "id": board.get("id"),
                    "name": board.get("name"),
                    "viewLink": board.get("viewLink"),
                    "createdAt": board.get("createdAt"),
                })

            if len(all_boards) >= limit:
                break

            # Check for next page cursor
            next_offset = data.get("offset")
            total = data.get("total", 0)
            if not boards or len(all_boards) >= total:
                break
            if next_offset and next_offset != offset:
                offset = next_offset
            else:
                break

    return all_boards[:limit]


async def delete_board(board_id: str) -> bool:
    """Delete a Miro board by ID.

    Args:
        board_id: The ID of the board to delete

    Returns:
        True if deleted successfully (204 response).
    """
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=MIRO_TIMEOUT) as client:
        resp = await client.delete(
            f"{MIRO_BASE_URL}/boards/{board_id}",
            headers=headers,
        )
        _raise_for_miro_error(resp, f"delete_board({board_id})")
        return resp.status_code == 204

"""Authentication middleware for Om Apex MCP HTTP server.

Supports:
- API key authentication via X-API-Key header (full access)
- Demo mode for unauthenticated users (read-only tools, sample data)
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("om-apex-mcp")

# Reading-only tools allowed in demo mode
DEMO_MODE_TOOLS = [
    "get_full_context",
    "get_claude_instructions",
    "get_company_context",
    "get_technology_decisions",
    "get_decisions_history",
    "get_domain_inventory",
    "get_pending_tasks",
    "get_daily_progress",
    "search_daily_progress",
    "list_company_configs",
    "get_session_handoff",
]


@dataclass
class UserInfo:
    name: str
    api_key: str
    full_access: bool = True


def load_api_keys() -> dict[str, UserInfo]:
    """Load API keys from environment variables."""
    keys: dict[str, UserInfo] = {}

    nishad_key = os.environ.get("OM_APEX_API_KEY_NISHAD")
    if nishad_key:
        keys[nishad_key] = UserInfo(name="Nishad", api_key=nishad_key)

    sumedha_key = os.environ.get("OM_APEX_API_KEY_SUMEDHA")
    if sumedha_key:
        keys[sumedha_key] = UserInfo(name="Sumedha", api_key=sumedha_key)

    logger.info(f"Loaded {len(keys)} API key(s)")
    return keys


def is_demo_mode_enabled() -> bool:
    """Check if demo mode is enabled via environment variable."""
    return os.environ.get("OM_APEX_DEMO_MODE", "").lower() in ("true", "1", "yes")


class AuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that validates API keys.

    - Valid API key in X-API-Key header → full access (all tools)
    - No key or invalid key → demo mode if enabled (read-only tools)
    - No key and demo mode disabled → 401 Unauthorized
    """

    def __init__(self, app, valid_keys: Optional[dict[str, UserInfo]] = None):
        super().__init__(app)
        self.valid_keys = valid_keys or load_api_keys()
        self.demo_enabled = is_demo_mode_enabled()

    async def dispatch(self, request: Request, call_next) -> Response:
        # Health check is always public
        if request.url.path == "/health":
            return await call_next(request)

        api_key = request.headers.get("x-api-key", "")

        if api_key and api_key in self.valid_keys:
            user = self.valid_keys[api_key]
            request.state.user = user
            request.state.demo_mode = False
            logger.info(f"Authenticated user: {user.name}")
        elif self.demo_enabled:
            request.state.user = None
            request.state.demo_mode = True
            logger.info("Demo mode access (no API key)")
        else:
            return Response(
                content='{"error": "Authentication required. Provide a valid X-API-Key header."}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)

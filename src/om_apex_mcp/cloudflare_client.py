"""Cloudflare API client for Om Apex Holdings DNS management.

Reads from CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID env vars.
Falls back to ~/om-apex/config/.env.cloudflare if env vars not set.

Follows the cortex_supabase.py singleton pattern.
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
_cf_config: Optional[dict] = None

CLOUDFLARE_BASE_URL = "https://api.cloudflare.com/client/v4"
CF_TIMEOUT = int(os.environ.get("CF_TIMEOUT", "30"))


def _get_cf_config_path() -> Path:
    """Get path to Cloudflare config file."""
    if platform.system() == "Darwin":
        return Path.home() / "om-apex/config/.env.cloudflare"
    elif platform.system() == "Windows":
        return Path("C:/Users/14042/om-apex/config/.env.cloudflare")
    else:
        home_config = Path.home() / "om-apex/config/.env.cloudflare"
        if home_config.exists():
            return home_config
        return Path("/etc/om-apex/.env.cloudflare")


def get_cf_config() -> Optional[dict]:
    """Get Cloudflare API credentials.

    Returns a dict with api_token and account_id, or None if not configured.
    Never raises — returns None on any failure.
    """
    global _cf_config

    if _cf_config is not None:
        return _cf_config

    try:
        # Check env vars first
        api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")

        # Fall back to config file
        if not api_token or not account_id:
            config_path = _get_cf_config_path()
            try:
                if config_path.exists():
                    from dotenv import load_dotenv
                    load_dotenv(config_path)
                    logger.info(f"Loaded Cloudflare config from: {config_path}")
                else:
                    logger.warning(f"Cloudflare config not found at: {config_path}")
            except Exception as env_err:
                logger.warning(f"Error loading .env.cloudflare: {env_err}")
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

            api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
            account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")

        if not api_token:
            logger.warning("CLOUDFLARE_API_TOKEN not set — Cloudflare disabled")
            return None
        if not account_id:
            logger.warning("CLOUDFLARE_ACCOUNT_ID not set — Cloudflare disabled")
            return None

        _cf_config = {
            "api_token": api_token.strip(),
            "account_id": account_id.strip(),
        }
        logger.info("Cloudflare config loaded successfully")
        return _cf_config

    except Exception as e:
        logger.error(f"Failed to load Cloudflare config: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return None


def reset_cf_config() -> None:
    """Clear cached Cloudflare config so it reloads on next call."""
    global _cf_config
    _cf_config = None
    logger.info("Cloudflare config cache cleared")


def is_cloudflare_available() -> bool:
    """Check if Cloudflare is configured and available."""
    return get_cf_config() is not None


def _get_headers() -> dict:
    """Build auth headers for Cloudflare API requests."""
    cfg = get_cf_config()
    if not cfg:
        raise RuntimeError("Cloudflare is not configured")
    return {
        "Authorization": f"Bearer {cfg['api_token']}",
        "Content-Type": "application/json",
    }


def _raise_for_cf_error(resp: httpx.Response, context: str = "") -> dict:
    """Parse Cloudflare response and raise on API-level errors."""
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success", False):
        errors = data.get("errors", [])
        error_msgs = "; ".join(f"{e.get('code', '?')}: {e.get('message', e)}" for e in errors)
        raise RuntimeError(f"Cloudflare API error{' (' + context + ')' if context else ''}: {error_msgs}")
    return data


# =============================================================================
# Async API functions
# =============================================================================

async def list_zones() -> list[dict]:
    """List all zones (domains) in the Cloudflare account.

    Returns:
        List of zone dicts with id, name, status, etc.
    """
    headers = _get_headers()
    cfg = get_cf_config()
    all_zones = []
    page = 1

    async with httpx.AsyncClient(timeout=CF_TIMEOUT) as client:
        while True:
            resp = await client.get(
                f"{CLOUDFLARE_BASE_URL}/zones",
                headers=headers,
                params={
                    "account.id": cfg["account_id"],
                    "per_page": 50,
                    "page": page,
                },
            )
            data = _raise_for_cf_error(resp, "list_zones")
            zones = data.get("result", [])
            all_zones.extend(zones)

            result_info = data.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

    return all_zones


async def get_zone_id(domain: str) -> Optional[str]:
    """Get zone ID for a domain name.

    Args:
        domain: Domain name (e.g., 'omapex.com')

    Returns:
        Zone ID string, or None if domain not found.
    """
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=CF_TIMEOUT) as client:
        resp = await client.get(
            f"{CLOUDFLARE_BASE_URL}/zones",
            headers=headers,
            params={"name": domain},
        )
        data = _raise_for_cf_error(resp, f"get_zone_id({domain})")
        result = data.get("result", [])
        if result:
            return result[0]["id"]
        return None


async def list_dns_records(zone_id: str) -> list[dict]:
    """Get all DNS records for a zone.

    Args:
        zone_id: Cloudflare zone ID

    Returns:
        List of DNS record dicts.
    """
    headers = _get_headers()
    all_records = []
    page = 1

    async with httpx.AsyncClient(timeout=CF_TIMEOUT) as client:
        while True:
            resp = await client.get(
                f"{CLOUDFLARE_BASE_URL}/zones/{zone_id}/dns_records",
                headers=headers,
                params={"per_page": 100, "page": page},
            )
            data = _raise_for_cf_error(resp, f"list_dns_records({zone_id})")
            records = data.get("result", [])
            all_records.extend(records)

            result_info = data.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

    return all_records


async def create_dns_record(zone_id: str, record: dict) -> dict:
    """Create a DNS record in a zone.

    Args:
        zone_id: Cloudflare zone ID
        record: Dict with type, name, content, and optional ttl/priority/proxied

    Returns:
        Created record dict from Cloudflare.
    """
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=CF_TIMEOUT) as client:
        resp = await client.post(
            f"{CLOUDFLARE_BASE_URL}/zones/{zone_id}/dns_records",
            headers=headers,
            json=record,
        )
        data = _raise_for_cf_error(resp, f"create_dns_record in zone {zone_id}")
        return data.get("result", {})


async def update_dns_record(zone_id: str, record_id: str, record: dict) -> dict:
    """Update an existing DNS record.

    Args:
        zone_id: Cloudflare zone ID
        record_id: ID of the record to update
        record: Dict with updated fields

    Returns:
        Updated record dict from Cloudflare.
    """
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=CF_TIMEOUT) as client:
        resp = await client.patch(
            f"{CLOUDFLARE_BASE_URL}/zones/{zone_id}/dns_records/{record_id}",
            headers=headers,
            json=record,
        )
        data = _raise_for_cf_error(resp, f"update_dns_record {record_id}")
        return data.get("result", {})


async def delete_dns_record(zone_id: str, record_id: str) -> bool:
    """Delete a DNS record.

    Args:
        zone_id: Cloudflare zone ID
        record_id: ID of the record to delete

    Returns:
        True if deleted successfully.
    """
    headers = _get_headers()

    async with httpx.AsyncClient(timeout=CF_TIMEOUT) as client:
        resp = await client.delete(
            f"{CLOUDFLARE_BASE_URL}/zones/{zone_id}/dns_records/{record_id}",
            headers=headers,
        )
        data = _raise_for_cf_error(resp, f"delete_dns_record {record_id}")
        return bool(data.get("result", {}).get("id"))

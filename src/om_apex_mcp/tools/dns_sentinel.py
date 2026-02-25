"""DNS Sentinel: Cloudflare DNS audit, auto-heal, and change management tools.

Audits all 22 Om Apex Holdings domains against best-practice policies,
auto-heals safe security records, queues dangerous changes for approval,
and maintains a full audit trail in Owner Portal Supabase.

Source of truth: dns_domain_config + dns_services + dns_policies tables.
Cloudflare API via cloudflare_client.py.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from mcp.types import Tool, TextContent

from . import ToolModule
from ..supabase_client import get_supabase_client, is_supabase_available
from ..cloudflare_client import (
    is_cloudflare_available, get_cf_config,
    list_zones, get_zone_id, list_dns_records,
    create_dns_record, update_dns_record, delete_dns_record,
)

logger = logging.getLogger("om-apex-mcp")

READING = [
    "dns_audit",
    "dns_view_config",
    "dns_view_approvals",
    "dns_view_changes",
    "dns_view_snapshot",
]
WRITING = [
    "dns_snapshot",
    "dns_heal",
    "dns_approve",
    "dns_reject",
    "dns_update_config",
]

# Domains where auto-heal is disabled (Tier 5)
AUDIT_ONLY_DOMAINS = {"theomgroup.ai"}

# Google Workspace email domains
EMAIL_DOMAINS = {"omapex.com", "omaisolutions.com", "omluxeproperties.com", "omsupplychain.com"}


def _require_supabase() -> None:
    if not is_supabase_available():
        raise RuntimeError(
            "Owner Portal Supabase is not available. "
            "Check SUPABASE_URL and SUPABASE_SERVICE_KEY env vars or ~/.env.supabase."
        )


def _require_cloudflare() -> None:
    if not is_cloudflare_available():
        raise RuntimeError(
            "Cloudflare is not configured. "
            "Check CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID env vars "
            "or ~/om-apex/config/.env.cloudflare."
        )


def _json(data) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


def _text(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=msg)]


def _run_id() -> str:
    return f"AUDIT-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"


# =============================================================================
# Register
# =============================================================================

def register() -> ToolModule:
    tools = [
        Tool(
            name="dns_snapshot",
            description=(
                "Pull current DNS records from Cloudflare for all domains (or a specific domain) "
                "and save them to dns_snapshots table. Use this to take an initial or periodic "
                "snapshot of the live DNS state. Also updates cloudflare_zone_id in dns_domain_config."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Specific domain to snapshot. Omit for all 22 domains.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="dns_audit",
            description=(
                "Audit DNS records for all domains (or a specific domain / tier) against "
                "source-of-truth policies. Returns findings with severity (critical/warning/info). "
                "Set fix_safe=true to auto-heal safe findings immediately."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Audit a specific domain only.",
                    },
                    "tier": {
                        "type": "integer",
                        "description": "Audit all domains in a specific tier (1-5).",
                    },
                    "fix_safe": {
                        "type": "boolean",
                        "description": "Auto-heal safe findings during the audit run. Default false.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="dns_view_config",
            description=(
                "View the source-of-truth DNS configuration: domain configs with tier/services/expected records, "
                "or details for a specific domain or service definition."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "View config for a specific domain.",
                    },
                    "service": {
                        "type": "string",
                        "description": "View a specific service definition (e.g., google-workspace).",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="dns_view_approvals",
            description=(
                "View DNS changes that are pending human approval. "
                "These are dangerous changes (A/MX/CNAME edits, deletes) queued by the audit engine."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Filter by domain.",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status: pending, approved, rejected, expired. Default: pending.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="dns_view_changes",
            description="View DNS change history with before/after values and who applied each change.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Filter by domain.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max changes to return. Default 20.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="dns_view_snapshot",
            description="View the latest raw Cloudflare DNS records snapshot for a domain.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to view snapshot for (required).",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="dns_heal",
            description=(
                "Apply auto-healable DNS fixes across all domains (or a specific domain). "
                "Safe changes (add missing DMARC/SPF/CAA) are applied immediately. "
                "Dangerous changes are queued for approval. "
                "Use dry_run=true (default) to preview what would change without applying anything."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Heal a specific domain only.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Preview changes without applying. Default true.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="dns_approve",
            description="Approve a pending DNS change in the approval queue and apply it to Cloudflare.",
            inputSchema={
                "type": "object",
                "properties": {
                    "approval_id": {
                        "type": "string",
                        "description": "UUID of the approval queue entry to approve.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes about the approval decision.",
                    },
                },
                "required": ["approval_id"],
            },
        ),
        Tool(
            name="dns_reject",
            description="Reject a pending DNS change in the approval queue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "approval_id": {
                        "type": "string",
                        "description": "UUID of the approval queue entry to reject.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for rejection.",
                    },
                },
                "required": ["approval_id"],
            },
        ),
        Tool(
            name="dns_update_config",
            description=(
                "Update the source-of-truth configuration for a domain: "
                "add/remove service assignments, add custom records, or update notes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to update.",
                    },
                    "add_services": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Service IDs to add (e.g., ['google-workspace']).",
                    },
                    "remove_services": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Service IDs to remove.",
                    },
                    "add_records": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Custom records to add to this domain's config.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Notes to set (replaces existing notes).",
                    },
                },
                "required": ["domain"],
            },
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "dns_snapshot":
            return await _handle_dns_snapshot(arguments)
        elif name == "dns_audit":
            return await _handle_dns_audit(arguments)
        elif name == "dns_view_config":
            return await _handle_dns_view_config(arguments)
        elif name == "dns_view_approvals":
            return _handle_dns_view_approvals(arguments)
        elif name == "dns_view_changes":
            return _handle_dns_view_changes(arguments)
        elif name == "dns_view_snapshot":
            return _handle_dns_view_snapshot(arguments)
        elif name == "dns_heal":
            return await _handle_dns_heal(arguments)
        elif name == "dns_approve":
            return await _handle_dns_approve(arguments)
        elif name == "dns_reject":
            return _handle_dns_reject(arguments)
        elif name == "dns_update_config":
            return _handle_dns_update_config(arguments)
        return None

    return ToolModule(tools=tools, handler=handler, reading_tools=READING, writing_tools=WRITING)


# =============================================================================
# Internal helpers
# =============================================================================

def _get_all_domain_configs() -> list[dict]:
    """Load all domain configs from dns_domain_config."""
    _require_supabase()
    client = get_supabase_client()
    resp = client.table("dns_domain_config").select("*").order("tier").execute()
    return resp.data or []


def _get_domain_config(domain: str) -> Optional[dict]:
    """Load a single domain config."""
    _require_supabase()
    client = get_supabase_client()
    resp = client.table("dns_domain_config").select("*").eq("domain", domain).execute()
    return resp.data[0] if resp.data else None


def _get_service(service_id: str) -> Optional[dict]:
    """Load a service definition from dns_services."""
    _require_supabase()
    client = get_supabase_client()
    resp = client.table("dns_services").select("*").eq("id", service_id).execute()
    return resp.data[0] if resp.data else None


def _get_policies_for_domain(domain_config: dict) -> list[dict]:
    """Load all enabled policies that apply to this domain."""
    _require_supabase()
    client = get_supabase_client()
    resp = client.table("dns_policies").select("*").eq("enabled", True).execute()
    policies = resp.data or []

    tier = domain_config.get("tier", 0)
    services = set(domain_config.get("services") or [])
    domain = domain_config.get("domain", "")

    result = []
    for policy in policies:
        scope = policy.get("scope", "global")
        if scope == "global":
            result.append(policy)
        elif scope.startswith("tier:"):
            policy_tier = int(scope.split(":")[1])
            if tier == policy_tier:
                result.append(policy)
        elif scope.startswith("service:"):
            svc = scope.split(":", 1)[1]
            if svc in services:
                result.append(policy)
        elif scope.startswith("domain:"):
            policy_domain = scope.split(":", 1)[1]
            if policy_domain == domain:
                result.append(policy)

    return result


def _check_record_policy(policy: dict, live_records: list[dict]) -> Optional[dict]:
    """Check a single policy against live records. Returns a finding dict or None if passing."""
    rule = policy.get("rule", {})
    rule_type = policy.get("rule_type", "")
    policy_id = policy.get("id", "")
    severity = policy.get("severity", "warning")

    def _normalize_content(record: dict) -> str:
        """Normalize TXT record content from Cloudflare.

        Cloudflare returns long TXT records (>255 chars) with literal outer
        quotes and internal quote-separated strings, e.g.:
          '"v=spf1 include:google.com" "include:sendgrid.net ~all"'
        Strip outer/inner quotes and join to get the plain value.
        """
        content = record.get("content", "")
        if record.get("type", "").upper() == "TXT" and content.startswith('"'):
            # Strip surrounding and internal quotes, join segments
            content = content.replace('" "', "").strip('"')
        return content

    def _rec_name_matches_rule(rec_name: str, rule_name: str) -> bool:
        """Match a live record name against a rule name.

        Cloudflare returns full domain names in record name fields:
        - Apex (@): "omapex.com"  (1 dot)
        - _dmarc:   "_dmarc.omapex.com"  (contains rule name)
        - subdomain: "google._domainkey.omapex.com"
        """
        rn = rec_name.lower()
        rn_rule = rule_name.lower()
        if rn_rule == "@":
            # Apex: name is "@" or the bare domain (≤1 dot for .com/.ai)
            return rn == "@" or rn.count(".") <= 1
        return rn_rule in rn

    def matches_record(record: dict, rule: dict) -> bool:
        """Check if a live record matches the rule criteria."""
        if "type" in rule and record.get("type", "").upper() != rule["type"].upper():
            return False
        if "name" in rule:
            if not _rec_name_matches_rule(record.get("name", ""), rule["name"]):
                return False
        content = _normalize_content(record)
        if "content" in rule:
            if content != rule["content"]:
                return False
        if "content_contains" in rule:
            if rule["content_contains"] not in content:
                return False
        if "content_startswith" in rule:
            if not content.startswith(rule["content_startswith"]):
                return False
        if "content_contains_any" in rule:
            if not any(s in content for s in rule["content_contains_any"]):
                return False
        if "proxied" in rule:
            if record.get("proxied") != rule["proxied"]:
                return False
        return True

    if rule_type == "record_required":
        # Policy passes if at least one live record matches
        if any(matches_record(r, rule) for r in live_records):
            return None  # passing
        return {
            "policy_id": policy_id,
            "severity": severity,
            "type": "missing_record",
            "description": f"Required record not found: {rule.get('type', '?')} {rule.get('name', '@')}",
            "expected": rule,
            "actual": None,
            "auto_heal": policy.get("auto_heal", False),
            "heal_action": policy.get("heal_action"),
        }

    elif rule_type == "record_forbidden":
        # Policy passes if NO live record matches
        matching = [r for r in live_records if matches_record(r, rule)]
        if not matching:
            return None  # passing
        return {
            "policy_id": policy_id,
            "severity": severity,
            "type": "forbidden_record_present",
            "description": f"Forbidden record found: {rule.get('type', '?')} {rule.get('name', '@')}",
            "expected": "no record matching this rule",
            "actual": matching[0],
            "auto_heal": False,  # deletes always require approval
            "heal_action": None,
        }

    elif rule_type == "record_value_match":
        # Find the record type+name, then check if value matches.
        # Cloudflare returns apex records with the full domain name (e.g. "omcortex.ai")
        # rather than "@", so we treat "@" as matching any apex record.
        rule_name = rule.get("name", "")
        target_records = [r for r in live_records
                          if r.get("type", "").upper() == rule.get("type", "").upper()
                          and _rec_name_matches_rule(r.get("name", ""), rule_name)]
        if not target_records:
            return {
                "policy_id": policy_id,
                "severity": severity,
                "type": "record_value_mismatch",
                "description": f"Record {rule.get('type')} {rule.get('name')} not found for value check",
                "expected": rule,
                "actual": None,
                "auto_heal": policy.get("auto_heal", False),
                "heal_action": policy.get("heal_action"),
            }
        # Check if any of the target records pass the value check
        if any(matches_record(r, rule) for r in target_records):
            return None  # passing
        return {
            "policy_id": policy_id,
            "severity": severity,
            "type": "record_value_mismatch",
            "description": f"Record {rule.get('type')} {rule.get('name')} value doesn't match policy",
            "expected": rule,
            "actual": target_records[0],
            "auto_heal": policy.get("auto_heal", False),
            "heal_action": policy.get("heal_action"),
        }

    return None  # unknown rule type — skip


def _is_safe_to_auto_heal(finding: dict, domain: str) -> bool:
    """Determine if a finding can be auto-healed without human approval."""
    if domain in AUDIT_ONLY_DOMAINS:
        return False
    if not finding.get("auto_heal"):
        return False
    heal_action = finding.get("heal_action") or {}
    action = heal_action.get("action", "")
    # Only allow "add" or "upsert" of TXT/CAA/CNAME records as auto-heal
    if action in ("add", "upsert", "add_if_missing"):
        record = heal_action.get("record", heal_action.get("records", []))
        if isinstance(record, dict):
            rec_type = record.get("type", "")
            return rec_type in ("TXT", "CAA", "CNAME")
        elif isinstance(record, list):
            return all(r.get("type") in ("TXT", "CAA", "CNAME") for r in record)
    return False


def _save_snapshot(domain: str, zone_id: str, records: list[dict]) -> dict:
    """Save DNS records snapshot to Supabase."""
    _require_supabase()
    client = get_supabase_client()
    row = {
        "domain": domain,
        "records": records,
        "record_count": len(records),
    }
    resp = client.table("dns_snapshots").insert(row).execute()
    # Also update zone_id in dns_domain_config if we have one
    if zone_id:
        client.table("dns_domain_config").update(
            {"cloudflare_zone_id": zone_id}
        ).eq("domain", domain).execute()
    return resp.data[0] if resp.data else {}


def _log_change(change: dict) -> None:
    """Insert a record into dns_change_log."""
    try:
        _require_supabase()
        client = get_supabase_client()
        client.table("dns_change_log").insert(change).execute()
    except Exception as e:
        logger.warning(f"Failed to log DNS change: {e}")


def _queue_approval(item: dict) -> dict:
    """Insert a record into dns_approval_queue."""
    _require_supabase()
    client = get_supabase_client()
    resp = client.table("dns_approval_queue").insert(item).execute()
    return resp.data[0] if resp.data else {}


async def _apply_heal_action(domain: str, zone_id: str, finding: dict, dry_run: bool, run_id: str) -> dict:
    """Apply a heal action for a finding. Returns result dict."""
    heal_action = finding.get("heal_action") or {}
    action = heal_action.get("action", "")
    result = {"domain": domain, "action": action, "finding": finding["policy_id"], "applied": False}

    if action == "description":
        result["note"] = heal_action.get("note", "Manual action required")
        result["applied"] = False
        return result

    records_to_add = []
    if action in ("add", "upsert") and "record" in heal_action:
        records_to_add = [heal_action["record"]]
    elif action == "add_if_missing" and "records" in heal_action:
        records_to_add = heal_action["records"]

    if not records_to_add:
        return result

    for record in records_to_add:
        if dry_run:
            result["would_create"] = record
            result["applied"] = False
        else:
            try:
                # CAA records use data object, not content string
                if record.get("type") == "CAA" and "data" in record:
                    cf_payload = {
                        "type": "CAA",
                        "name": record["name"],
                        "data": record["data"],
                        "ttl": record.get("ttl", 3600),
                    }
                else:
                    cf_payload = {
                        "type": record["type"],
                        "name": record["name"],
                        "content": record.get("content", ""),
                        "ttl": record.get("ttl", 3600),
                        "proxied": record.get("proxied", False),
                    }
                cf_record = await create_dns_record(zone_id, cf_payload)
                _log_change({
                    "domain": domain,
                    "change_type": "auto_heal",
                    "record_type": record["type"],
                    "record_name": record["name"],
                    "action": "create",
                    "before_value": None,
                    "after_value": cf_record,
                    "cloudflare_record_id": cf_record.get("id"),
                    "audit_run_id": run_id,
                    "policy_id": finding["policy_id"],
                    "applied_by": "sentinel",
                })
                result["applied"] = True
                result["cloudflare_record_id"] = cf_record.get("id")
            except Exception as e:
                result["error"] = str(e)
                result["applied"] = False

    return result


# =============================================================================
# Handlers
# =============================================================================

async def _handle_dns_snapshot(args: dict) -> list[TextContent]:
    _require_supabase()
    _require_cloudflare()

    target_domain = args.get("domain")

    # Load domain configs
    if target_domain:
        configs = [_get_domain_config(target_domain)]
        if not configs[0]:
            return _text(f"Domain '{target_domain}' not found in dns_domain_config.")
    else:
        configs = _get_all_domain_configs()

    # Get all zones from Cloudflare once
    try:
        zones = await list_zones()
        zone_map = {z["name"]: z["id"] for z in zones}
        logger.info(f"Cloudflare zones loaded: {len(zones)} zones")
    except Exception as e:
        return _text(f"Failed to list Cloudflare zones: {e}")

    results = []
    for config in configs:
        if not config:
            continue
        domain = config["domain"]
        zone_id = zone_map.get(domain) or config.get("cloudflare_zone_id")

        if not zone_id:
            results.append({
                "domain": domain,
                "status": "error",
                "error": "Zone not found in Cloudflare account",
            })
            continue

        try:
            records = await list_dns_records(zone_id)
            snapshot = _save_snapshot(domain, zone_id, records)
            results.append({
                "domain": domain,
                "status": "ok",
                "record_count": len(records),
                "snapshot_id": snapshot.get("id"),
                "zone_id": zone_id,
            })
            logger.info(f"Snapshot taken: {domain} ({len(records)} records)")
        except Exception as e:
            results.append({
                "domain": domain,
                "status": "error",
                "error": str(e),
            })

    total = len(results)
    success = sum(1 for r in results if r.get("status") == "ok")
    errors = total - success

    lines = [
        f"DNS Snapshot complete: {success}/{total} domains snapshotted",
        f"Errors: {errors}" if errors else "",
        "",
    ]
    for r in results:
        icon = "✓" if r.get("status") == "ok" else "✗"
        if r.get("status") == "ok":
            lines.append(f"  {icon} {r['domain']} — {r['record_count']} records (zone: {r['zone_id']})")
        else:
            lines.append(f"  {icon} {r['domain']} — ERROR: {r.get('error', '?')}")

    return _text("\n".join(l for l in lines if l is not None))


async def _handle_dns_audit(args: dict) -> list[TextContent]:
    _require_supabase()
    _require_cloudflare()

    target_domain = args.get("domain")
    target_tier = args.get("tier")
    fix_safe = args.get("fix_safe", False)
    run_id = _run_id()

    # Load domain configs
    if target_domain:
        configs = [_get_domain_config(target_domain)]
        if not configs[0]:
            return _text(f"Domain '{target_domain}' not found in dns_domain_config.")
    else:
        configs = _get_all_domain_configs()
        if target_tier:
            configs = [c for c in configs if c.get("tier") == target_tier]

    # Get Cloudflare zones
    try:
        zones = await list_zones()
        zone_map = {z["name"]: z["id"] for z in zones}
    except Exception as e:
        return _text(f"Failed to connect to Cloudflare: {e}")

    all_findings = []
    healed = []
    queued = []
    passed = 0
    total_records = 0

    client = get_supabase_client()

    for config in configs:
        if not config:
            continue
        domain = config["domain"]
        zone_id = zone_map.get(domain) or config.get("cloudflare_zone_id")

        if not zone_id:
            all_findings.append({
                "domain": domain,
                "severity": "critical",
                "type": "zone_not_found",
                "description": f"Zone not found in Cloudflare account for {domain}",
                "auto_heal": False,
            })
            continue

        try:
            live_records = await list_dns_records(zone_id)
            total_records += len(live_records)
        except Exception as e:
            all_findings.append({
                "domain": domain,
                "severity": "critical",
                "type": "cloudflare_error",
                "description": f"Failed to fetch records: {e}",
                "auto_heal": False,
            })
            continue

        policies = _get_policies_for_domain(config)
        domain_passed = True

        for policy in policies:
            finding = _check_record_policy(policy, live_records)
            if finding is None:
                continue  # policy passes

            finding["domain"] = domain
            finding["run_id"] = run_id
            domain_passed = False

            if fix_safe and _is_safe_to_auto_heal(finding, domain):
                heal_result = await _apply_heal_action(domain, zone_id, finding, dry_run=False, run_id=run_id)
                if heal_result.get("applied"):
                    finding["healed"] = True
                    healed.append(heal_result)
                    continue
            elif not _is_safe_to_auto_heal(finding, domain) and finding.get("heal_action") and domain not in AUDIT_ONLY_DOMAINS:
                # Queue for approval if there's a proposed action
                heal_action = finding.get("heal_action") or {}
                record = heal_action.get("record")
                if record:
                    _queue_approval({
                        "domain": domain,
                        "record_type": record.get("type"),
                        "record_name": record.get("name"),
                        "action": "create",
                        "current_value": None,
                        "proposed_value": record,
                        "reason": finding["description"],
                        "risk_level": "medium",
                        "audit_run_id": run_id,
                        "policy_id": finding["policy_id"],
                    })
                    finding["queued_for_approval"] = True
                    queued.append(domain)

            all_findings.append(finding)

        if domain_passed:
            passed += 1

        # Update last_audit_at
        status = "pass" if domain_passed else "drift"
        try:
            client.table("dns_domain_config").update({
                "last_audit_at": datetime.now(timezone.utc).isoformat(),
                "last_audit_status": status,
            }).eq("domain", domain).execute()
        except Exception:
            pass

    # Save audit log
    summary = {
        "pass": passed,
        "drift": len(configs) - passed,
        "auto_healed": len(healed),
        "pending_approval": len(queued),
        "total_findings": len(all_findings),
    }
    try:
        client.table("dns_audit_log").insert({
            "run_id": run_id,
            "run_type": "manual",
            "domains_scanned": len(configs),
            "total_records_checked": total_records,
            "findings": all_findings,
            "summary": summary,
            "triggered_by": "claude",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to save audit log: {e}")

    # Format output
    lines = [
        f"DNS Audit Complete — Run ID: {run_id}",
        f"",
        f"Domains: {len(configs)} scanned | {passed} passing | {len(configs) - passed} with findings",
        f"Records checked: {total_records}",
        f"Findings: {len(all_findings)} total",
        f"Auto-healed: {len(healed)} records" if fix_safe else "",
        f"Queued for approval: {len(queued)} changes",
        f"",
    ]

    if all_findings:
        # Group by severity
        critical = [f for f in all_findings if f.get("severity") == "critical"]
        warnings = [f for f in all_findings if f.get("severity") == "warning"]
        info = [f for f in all_findings if f.get("severity") == "info"]

        if critical:
            lines.append(f"CRITICAL ({len(critical)}):")
            for f in critical:
                healed_tag = " [HEALED]" if f.get("healed") else ""
                queued_tag = " [QUEUED]" if f.get("queued_for_approval") else ""
                lines.append(f"  ✗ {f['domain']}: {f['description']}{healed_tag}{queued_tag}")
            lines.append("")

        if warnings:
            lines.append(f"WARNINGS ({len(warnings)}):")
            for f in warnings:
                healed_tag = " [HEALED]" if f.get("healed") else ""
                lines.append(f"  ⚠ {f['domain']}: {f['description']}{healed_tag}")
            lines.append("")

        if info:
            lines.append(f"INFO ({len(info)}):")
            for f in info:
                lines.append(f"  ℹ {f['domain']}: {f['description']}")
            lines.append("")
    else:
        lines.append("✓ All domains passing all policies.")

    return _text("\n".join(l for l in lines if l is not None))


async def _handle_dns_view_config(args: dict) -> list[TextContent]:
    _require_supabase()
    client = get_supabase_client()

    domain = args.get("domain")
    service = args.get("service")

    if service:
        svc = _get_service(service)
        if not svc:
            return _text(f"Service '{service}' not found in dns_services.")
        return _json(svc)

    if domain:
        config = _get_domain_config(domain)
        if not config:
            return _text(f"Domain '{domain}' not found in dns_domain_config.")

        # Expand service details
        services = config.get("services") or []
        service_details = []
        for svc_id in services:
            svc = _get_service(svc_id)
            if svc:
                service_details.append({
                    "id": svc_id,
                    "name": svc["name"],
                    "record_templates": svc["record_templates"],
                })

        return _json({
            "domain": config,
            "expanded_services": service_details,
        })

    # List all domains summary
    configs = _get_all_domain_configs()
    summary = []
    for c in configs:
        summary.append({
            "domain": c["domain"],
            "tier": c.get("tier"),
            "tier_label": c.get("tier_label"),
            "services": c.get("services") or [],
            "redirect_target": c.get("redirect_target"),
            "last_audit_status": c.get("last_audit_status"),
            "cloudflare_zone_id": c.get("cloudflare_zone_id"),
        })
    return _json({"total": len(summary), "domains": summary})


def _handle_dns_view_approvals(args: dict) -> list[TextContent]:
    _require_supabase()
    client = get_supabase_client()

    domain = args.get("domain")
    status = args.get("status", "pending")

    query = client.table("dns_approval_queue").select("*").eq("status", status)
    if domain:
        query = query.eq("domain", domain)
    query = query.order("created_at", desc=True).limit(50)
    resp = query.execute()
    rows = resp.data or []

    if not rows:
        return _text(f"No approval queue entries with status='{status}'" + (f" for {domain}" if domain else "") + ".")

    return _json({"count": len(rows), "items": rows})


def _handle_dns_view_changes(args: dict) -> list[TextContent]:
    _require_supabase()
    client = get_supabase_client()

    domain = args.get("domain")
    limit = args.get("limit", 20)

    query = client.table("dns_change_log").select("*")
    if domain:
        query = query.eq("domain", domain)
    query = query.order("created_at", desc=True).limit(limit)
    resp = query.execute()
    rows = resp.data or []

    if not rows:
        return _text("No DNS changes recorded yet.")

    return _json({"count": len(rows), "changes": rows})


def _handle_dns_view_snapshot(args: dict) -> list[TextContent]:
    _require_supabase()
    client = get_supabase_client()

    domain = args["domain"]

    resp = (
        client.table("dns_snapshots")
        .select("*")
        .eq("domain", domain)
        .order("taken_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return _text(f"No snapshot found for '{domain}'. Run dns_snapshot first.")

    snapshot = rows[0]
    return _json({
        "domain": domain,
        "snapshot_id": snapshot.get("id"),
        "taken_at": snapshot.get("taken_at"),
        "record_count": snapshot.get("record_count"),
        "records": snapshot.get("records", []),
    })


async def _handle_dns_heal(args: dict) -> list[TextContent]:
    _require_supabase()
    _require_cloudflare()

    target_domain = args.get("domain")
    dry_run = args.get("dry_run", True)
    run_id = _run_id()

    if target_domain:
        configs = [_get_domain_config(target_domain)]
        if not configs[0]:
            return _text(f"Domain '{target_domain}' not found.")
    else:
        configs = _get_all_domain_configs()

    try:
        zones = await list_zones()
        zone_map = {z["name"]: z["id"] for z in zones}
    except Exception as e:
        return _text(f"Failed to connect to Cloudflare: {e}")

    healed = []
    skipped_approval = []
    skipped_tier5 = []

    for config in configs:
        if not config:
            continue
        domain = config["domain"]

        if domain in AUDIT_ONLY_DOMAINS:
            skipped_tier5.append(domain)
            continue

        zone_id = zone_map.get(domain) or config.get("cloudflare_zone_id")
        if not zone_id:
            continue

        try:
            live_records = await list_dns_records(zone_id)
        except Exception as e:
            logger.warning(f"Failed to fetch records for {domain}: {e}")
            continue

        policies = _get_policies_for_domain(config)
        # Track (record_type, record_name) pairs healed this domain to avoid
        # redundant policy failures after adding a record mid-loop
        healed_records: set[tuple] = set()

        for policy in policies:
            finding = _check_record_policy(policy, live_records)
            if finding is None:
                continue

            finding["domain"] = domain

            # Skip if we already healed this record type+name this pass
            heal_action = finding.get("heal_action") or {}
            heal_record = heal_action.get("record", {})
            rec_key = (heal_record.get("type", ""), heal_record.get("name", ""))
            if rec_key[0] and rec_key in healed_records:
                continue

            if _is_safe_to_auto_heal(finding, domain):
                result = await _apply_heal_action(domain, zone_id, finding, dry_run=dry_run, run_id=run_id)
                if result.get("applied") or dry_run:
                    healed_records.add(rec_key)
                healed.append({
                    "domain": domain,
                    "policy": policy.get("id"),
                    "description": finding["description"],
                    "dry_run": dry_run,
                    "result": result,
                })
            else:
                skipped_approval.append({
                    "domain": domain,
                    "policy": policy.get("id"),
                    "description": finding["description"],
                    "reason": "requires_approval",
                })

    mode_label = "[DRY RUN — no changes applied]" if dry_run else "[CHANGES APPLIED]"
    lines = [
        f"DNS Heal {mode_label}",
        f"",
        f"Healable findings: {len(healed)}",
        f"Requires approval: {len(skipped_approval)}",
        f"Audit-only (skipped): {len(skipped_tier5)}",
        "",
    ]

    if healed:
        lines.append("Healed / Would heal:")
        for h in healed:
            applied = h["result"].get("applied", False)
            tag = "APPLIED" if applied else ("WOULD APPLY" if dry_run else "FAILED")
            lines.append(f"  [{tag}] {h['domain']} — {h['description']}")
        lines.append("")

    if skipped_approval:
        lines.append("Requires approval (not healed):")
        for s in skipped_approval:
            lines.append(f"  [QUEUED] {s['domain']} — {s['description']}")
        lines.append("")

    if dry_run:
        lines.append("Re-run with dry_run=false to apply healable changes.")

    return _text("\n".join(l for l in lines if l is not None))


async def _handle_dns_approve(args: dict) -> list[TextContent]:
    _require_supabase()
    _require_cloudflare()

    approval_id = args["approval_id"]
    notes = args.get("notes", "")

    client = get_supabase_client()

    # Fetch the approval item
    resp = client.table("dns_approval_queue").select("*").eq("id", approval_id).execute()
    if not resp.data:
        return _text(f"Approval '{approval_id}' not found.")

    item = resp.data[0]
    if item.get("status") != "pending":
        return _text(f"Approval '{approval_id}' is '{item['status']}', not pending.")

    domain = item["domain"]
    proposed = item.get("proposed_value") or {}
    action = item.get("action", "create")

    # Get zone ID
    zone_id = None
    config = _get_domain_config(domain)
    if config:
        zone_id = config.get("cloudflare_zone_id")
    if not zone_id:
        zone_id = await get_zone_id(domain)
    if not zone_id:
        return _text(f"Zone ID not found for {domain}. Cannot apply change.")

    try:
        if action == "create":
            cf_result = await create_dns_record(zone_id, proposed)
        elif action == "update":
            cf_record_id = item.get("cloudflare_record_id") or proposed.get("id")
            if not cf_record_id:
                return _text("Cannot update: no cloudflare_record_id in approval item.")
            cf_result = await update_dns_record(zone_id, cf_record_id, proposed)
        elif action == "delete":
            cf_record_id = item.get("cloudflare_record_id")
            if not cf_record_id:
                return _text("Cannot delete: no cloudflare_record_id in approval item.")
            await delete_dns_record(zone_id, cf_record_id)
            cf_result = {"deleted": True}
        else:
            return _text(f"Unknown action '{action}' in approval item.")

        # Log the change
        _log_change({
            "domain": domain,
            "change_type": "approved",
            "record_type": item.get("record_type"),
            "record_name": item.get("record_name"),
            "action": action,
            "before_value": item.get("current_value"),
            "after_value": cf_result,
            "cloudflare_record_id": cf_result.get("id") if isinstance(cf_result, dict) else None,
            "audit_run_id": item.get("audit_run_id"),
            "policy_id": item.get("policy_id"),
            "applied_by": "manual",
            "notes": notes,
        })

        # Update approval status
        client.table("dns_approval_queue").update({
            "status": "approved",
            "reviewed_by": "nishad",
            "review_notes": notes,
        }).eq("id", approval_id).execute()

        return _text(
            f"Approval '{approval_id}' applied successfully.\n"
            f"Domain: {domain}\n"
            f"Action: {action}\n"
            f"Record: {item.get('record_type')} {item.get('record_name')}\n"
            f"Cloudflare result: {json.dumps(cf_result, indent=2, default=str)}"
        )

    except Exception as e:
        return _text(f"Failed to apply approval '{approval_id}': {e}")


def _handle_dns_reject(args: dict) -> list[TextContent]:
    _require_supabase()

    approval_id = args["approval_id"]
    reason = args.get("reason", "")

    client = get_supabase_client()

    resp = client.table("dns_approval_queue").select("*").eq("id", approval_id).execute()
    if not resp.data:
        return _text(f"Approval '{approval_id}' not found.")

    item = resp.data[0]
    if item.get("status") != "pending":
        return _text(f"Approval '{approval_id}' is '{item['status']}', not pending.")

    client.table("dns_approval_queue").update({
        "status": "rejected",
        "reviewed_by": "nishad",
        "review_notes": reason,
    }).eq("id", approval_id).execute()

    return _text(
        f"Approval '{approval_id}' rejected.\n"
        f"Domain: {item['domain']}\n"
        f"Reason: {reason or '(none given)'}"
    )


def _handle_dns_update_config(args: dict) -> list[TextContent]:
    _require_supabase()

    domain = args["domain"]
    client = get_supabase_client()

    config = _get_domain_config(domain)
    if not config:
        return _text(f"Domain '{domain}' not found in dns_domain_config.")

    updates = {}

    if "add_services" in args or "remove_services" in args:
        current_services = list(config.get("services") or [])
        for svc in (args.get("add_services") or []):
            if svc not in current_services:
                current_services.append(svc)
        for svc in (args.get("remove_services") or []):
            if svc in current_services:
                current_services.remove(svc)
        updates["services"] = current_services

    if "add_records" in args:
        current_custom = list(config.get("custom_records") or [])
        current_custom.extend(args["add_records"])
        updates["custom_records"] = current_custom

    if "notes" in args:
        updates["notes"] = args["notes"]

    if not updates:
        return _text("No changes provided to dns_update_config.")

    client.table("dns_domain_config").update(updates).eq("domain", domain).execute()

    return _text(
        f"Config updated for {domain}:\n" +
        "\n".join(f"  {k}: {v}" for k, v in updates.items())
    )


# =============================================================================
# Email alerting (graceful degradation if SendGrid not configured)
# =============================================================================

async def send_alert_email(subject: str, body: str, to: str = "nishad@omapex.com") -> None:
    """Send an alert email via SendGrid. Silently skips if not configured."""
    import os
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        # Try loading from config
        try:
            from dotenv import load_dotenv
            import platform
            from pathlib import Path
            if platform.system() == "Darwin":
                cfg = Path.home() / "om-apex/config/.env.providers"
            else:
                cfg = Path("C:/Users/14042/om-apex/config/.env.providers")
            if cfg.exists():
                load_dotenv(cfg)
                api_key = os.environ.get("SENDGRID_API_KEY")
        except Exception:
            pass

    if not api_key:
        logger.warning("SENDGRID_API_KEY not configured — skipping DNS alert email")
        return

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": to}]}],
                    "from": {"email": "dns-sentinel@omapex.com", "name": "DNS Sentinel"},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                },
            )
            if resp.status_code not in (200, 202):
                logger.warning(f"SendGrid alert failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.warning(f"Failed to send DNS alert email: {e}")

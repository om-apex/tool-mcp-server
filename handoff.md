# Handoff — MCP Server

## Current State
DEV-649 in progress — removing migrated tool modules (tasks, handoff, progress, context, calendar) from registration. Module files kept for rollback.

## Last Session
2026-04-04 — DEV-649: Removed registration of 5 migrated modules (26 tools) from server.py and http_server.py. These tools now live in Om Cortex at https://om-cortex.onrender.com/mcp. Updated auth.py demo mode tools, CLAUDE.md, DESIGN.md, and tests. 32 tools remain across 4 modules (documents, ai_quorum, incidents, dns_sentinel).

## Deployed State
- MCP Server: https://om-apex-mcp.onrender.com
- Render Service ID: `srv-d5snc28gjchc73b2se10`
- 32 tools, 4 modules (documents, ai_quorum, incidents, dns_sentinel)

## Key Decisions This Session
- Module files NOT deleted (kept for git history and rollback)
- `/mcp/core` endpoint now serves only ai_quorum + incidents
- Demo mode reduced to 1 tool (list_company_configs) — most demo tools were in migrated modules

## Blockers
None.

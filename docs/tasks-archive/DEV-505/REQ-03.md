# Implementation Plan — TASK-505 / REQ-03: Deploy, Verify, Update Docs

**Task:** TASK-505
**Requirement:** REQ-03
**Date:** 2026-03-17
**Status:** Ready for Execution
**Complexity:** Medium
**Total Steps:** 4
**Steps Remaining:** 4
**Depends On:** REQ-01, REQ-02

---

## Overview

Push the DB migration to Owner Portal Supabase, deploy the updated MCP server to Render, verify all tools work end-to-end, and update DB-SCHEMA-QUICK-REF.md.

## Scope
### In Scope
- Push migration to Owner Portal Supabase (`hympgocuivzxzxllgmcy`)
- Deploy to Render (push to main triggers auto-deploy)
- End-to-end verification of all modified tools
- Update DB-SCHEMA-QUICK-REF.md

### Out of Scope
- Code changes (completed in REQ-01 and REQ-02)

## Architecture Notes
- Owner Portal Supabase is NOT linked locally — use temp dir workaround for `supabase db push`
- Alternatively, use Supabase Management API or `psql` directly for the migration
- Render auto-deploys from main branch pushes (service `srv-d5snc28gjchc73b2se10`)
- MCP server needs a clean restart to pick up tool registration changes

---

## Execution Steps

### Step 1: Push DB migration to Owner Portal Supabase
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** `supabase/migrations/20260317_handoff_schema.sql`, Owner Portal Supabase credentials from `~/om-apex/config/.env.supabase.omapex-dashboard`
- **Creates/Modifies:** Owner Portal Supabase schema (remote)
- **Task:**
  1. Read the migration SQL
  2. Execute against Owner Portal Supabase using one of:
     - `/opt/homebrew/opt/libpq/bin/psql` with the connection string from `.env.supabase.omapex-dashboard`
     - Supabase Management API
     - Temp dir workaround per gotcha #1
  3. Verify `session_handoff` table is dropped
  4. Verify `session_handoff_history` has `project_code` column
- **Completion Check:** `\dt session_handoff` returns nothing; `\d session_handoff_history` shows `project_code TEXT` column
- **Depends On:** None

### Step 2: Commit and push to trigger Render deploy
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** Git status
- **Creates/Modifies:** Git (commit + push)
- **Task:**
  1. Stage all changed files in `tools/mcp-server/`
  2. Commit with message: `[TASK-505] Update ID generation (DEV/ISSUE prefixes) + handoff refactor`
  3. Push to `main` — triggers Render auto-deploy
  4. Monitor Render deploy status via `render deploys list` or similar
- **Completion Check:** Push succeeds; Render deploy starts
- **Depends On:** Step 1

### Step 3: End-to-end verification
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** Deployed MCP server
- **Creates/Modifies:** None (verification only — may create and delete test tasks)
- **Task:**
  1. Wait for Render deploy to complete
  2. Test `add_task` with `task_type: "enhancement"` — verify ID starts with `DEV-`
  3. Test `add_task` with `task_type: "issue"` — verify ID starts with `ISSUE-`
  4. Test `get_pending_tasks` with a `TASK-nnn` ID — verify backward compat
  5. Test `get_pending_tasks` with a `DEV-nnn` ID — verify new format works
  6. Test `save_session_handoff` with `project_code` — verify it inserts to history
  7. Test `get_handoff_history` with `project_code` filter — verify filtering works
  8. Verify `get_session_handoff` is NOT listed in available tools
  9. Clean up any test tasks created
- **Completion Check:** All 8 verification tests pass
- **Depends On:** Step 2

### Step 4: Update DB-SCHEMA-QUICK-REF.md
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** `docs/DB-SCHEMA-QUICK-REF.md`
- **Creates/Modifies:** `docs/DB-SCHEMA-QUICK-REF.md`
- **Task:**
  1. Remove `session_handoff` table schema section (table no longer exists)
  2. Add `project_code TEXT` to `session_handoff_history` schema
  3. Update the tasks table `id` column description to note DEV-nnn/ISSUE-nnn format
  4. Commit docs update
- **Completion Check:** DB-SCHEMA-QUICK-REF.md reflects current schema; no reference to dropped `session_handoff` table
- **Depends On:** Step 3

---

## Files Changed
<!-- Filled after execution -->

## Risks & Assumptions
- Owner Portal Supabase push may require the temp dir workaround (gotcha #1)
- Render deploy may take 2-5 minutes — need to wait before verification
- If deploy fails, check Render logs before retrying

## Open Questions
None.

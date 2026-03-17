# Implementation Plan — TASK-505 / REQ-02: Handoff Schema + Tool Refactor

**Task:** TASK-505
**Requirement:** REQ-02
**Date:** 2026-03-17
**Status:** Ready for Execution
**Complexity:** Medium
**Total Steps:** 4
**Steps Remaining:** 4
**Depends On:** None

---

## Overview

Drop the `session_handoff` singleton table, add `project_code` to `session_handoff_history`, simplify `save_session_handoff` to INSERT-only, remove `get_session_handoff` tool entirely, and add `project_code` parameter to both `save_session_handoff` and `get_handoff_history`.

## Scope
### In Scope
- DB migration: DROP `session_handoff`, ALTER `session_handoff_history`
- `supabase_client.py`: rewrite `save_session_handoff`, remove `get_session_handoff`, update `get_handoff_history`
- `tools/handoff.py`: remove `get_session_handoff` tool, update save/history tools with `project_code`
- Tool registration lists (READING, WRITING arrays)

### Out of Scope
- Task ID changes (REQ-01)
- Deployment (REQ-03)
- Local handoff.md file management (handled by Claude Code rules)

## Architecture Notes
- `session_handoff` is a singleton table with CHECK constraint `id = 1`. `DROP TABLE IF EXISTS` removes it cleanly.
- `session_handoff_history` keeps all existing rows — only adding a column (nullable TEXT, no default needed)
- `save_session_handoff` becomes a simple INSERT into history — no more read-archive-upsert cycle
- `checkpoint` parameter is removed — with no singleton to upsert, every save is just an INSERT. The concept of "checkpoint vs full" was tied to the archive-before-overwrite pattern.
- `project_code` is required on both `save_session_handoff` and `get_handoff_history` — every handoff belongs to a project

---

## Execution Steps

### Step 1: Write DB migration
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** `supabase/migrations/` (existing migration naming convention)
- **Creates/Modifies:** `supabase/migrations/20260317_handoff_schema.sql` (new)
- **Task:**
  1. Create migration file with timestamp prefix
  2. Contents:
     ```sql
     -- TASK-505: Handoff schema refactor
     -- Drop singleton session_handoff table (replaced by local handoff.md files)
     DROP TABLE IF EXISTS session_handoff;

     -- Add project_code to history for per-project filtering
     ALTER TABLE session_handoff_history
       ADD COLUMN IF NOT EXISTS project_code TEXT;
     ```
  3. Verify syntax is valid PostgreSQL
- **Completion Check:** Migration file exists with correct SQL
- **Depends On:** None

### Step 2: Rewrite handoff functions in supabase_client.py
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/supabase_client.py` (lines 785-894)
- **Creates/Modifies:** `src/om_apex_mcp/supabase_client.py`
- **Task:**
  1. **Delete** `get_session_handoff()` function (lines 785-805)
  2. **Rewrite** `save_session_handoff()` (lines 808-869):
     - New signature: `save_session_handoff(content: str, created_by: str, interface: str, project_code: str) -> dict`
     - Remove `checkpoint` parameter
     - Remove the "read existing → archive to history" block
     - Remove the singleton upsert block
     - Replace with a single INSERT into `session_handoff_history`:
       ```python
       record = {
           "content": content,
           "created_by": created_by,
           "interface": interface,
           "session_date": datetime.now().strftime("%Y-%m-%d"),
           "project_code": project_code,
       }
       response = client.table("session_handoff_history").insert(record).execute()
       ```
     - Return the inserted record
     - Update docstring
  3. **Update** `get_handoff_history()` (lines 872-894):
     - Add `project_code: str` parameter (required)
     - Add filter: `if project_code: query = query.eq("project_code", project_code)`
     - Update docstring
- **Completion Check:** `get_session_handoff` is gone; `save_session_handoff` does INSERT only; `get_handoff_history` accepts `project_code` filter
- **Depends On:** Step 1

### Step 3: Update handoff tool definitions and handler
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/tools/handoff.py` (full file)
- **Creates/Modifies:** `src/om_apex_mcp/tools/handoff.py`
- **Task:**
  1. **Remove** the `get_session_handoff` Tool definition (lines 29-37)
  2. **Remove** the `get_session_handoff` handler block (lines 103-131)
  3. **Remove** `get_session_handoff` from the `READING` list (line 23)
  4. **Remove** the import of `get_session_handoff as sb_get_handoff` (line 16)
  5. **Update** `save_session_handoff` Tool definition:
     - Remove `checkpoint` property from inputSchema
     - Add `project_code` property: `{"type": "string", "description": "Project code for this handoff (e.g., ai-quorum, mcp-server)"}`
     - Update description to remove "Archives the previous handoff" language
     - `project_code` IS required — add to `"required"` list in inputSchema
  6. **Update** `save_session_handoff` handler:
     - Remove `checkpoint` argument reading
     - Add `project_code = arguments.get("project_code")`
     - Pass `project_code` to `sb_save_handoff()`
     - Update response messages (remove "Previous handoff archived" and checkpoint messages)
  7. **Update** `get_handoff_history` Tool definition:
     - Add `project_code` property: `{"type": "string", "description": "Filter by project code (e.g., ai-quorum)"}` — add to `"required"` list
  8. **Update** `get_handoff_history` handler:
     - Read `project_code = arguments.get("project_code")`
     - Pass to `sb_get_history(limit=limit, created_by=created_by, project_code=project_code)`
  9. Update module docstring at top of file
- **Completion Check:** `get_session_handoff` completely removed; `save_session_handoff` has required `project_code`, no `checkpoint`; `get_handoff_history` has required `project_code` filter
- **Depends On:** Step 2

### Step 4: Verify server registration
- **Agent:** Developer
- **Status:** [ ] Incomplete
- **Reads:** `src/om_apex_mcp/server.py`, `src/om_apex_mcp/http_server.py`
- **Creates/Modifies:** None (verification only, unless issues found)
- **Task:**
  1. The handoff module is loaded dynamically via `handoff.register()` — since we changed the `register()` return value (fewer tools), the server picks it up automatically
  2. Verify no hardcoded references to `get_session_handoff` in server.py or http_server.py
  3. Check if any other module imports `get_session_handoff` from supabase_client
  4. Update the tool count comment if one exists (was 3 handoff tools → now 2)
- **Completion Check:** Server imports compile without error; no dangling references to removed function/tool
- **Depends On:** Step 3

---

## Files Changed
<!-- Filled after execution -->

## Risks & Assumptions
- Dropping `session_handoff` is irreversible — any data in the singleton row is lost. The last handoff content should already be in `session_handoff_history` (it's archived on every save). Verify this before running the migration.
- The `checkpoint` parameter removal is a breaking change for any caller still using it. Since the only callers are Claude Code sessions (via MCP tool calls), and we're updating the rules in TASK-504, this is acceptable.
- `project_code` on `session_handoff_history` is nullable at the DB level (old rows have NULL). New inserts always include it (required param). Old NULL rows are excluded by `.eq("project_code", value)` queries — this is acceptable since pre-project handoffs are legacy data.

## Open Questions
None.

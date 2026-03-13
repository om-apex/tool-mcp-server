# Implementation Plan — TASK-449 / REQ-02: Add project_code to add_task tool

**Task:** TASK-449
**Requirement:** REQ-02
**Date:** 2026-03-12
**Status:** Ready for Execution
**Complexity:** Low
**Total Steps:** 2
**Steps Remaining:** 0
**Depends On:** REQ-01

---

## Overview

Add `project_code` as a required parameter to the `add_task` MCP tool. The handler will use the `resolve_project_code` helper (from REQ-01) to convert the human-friendly code to a UUID and store it in `tasks.project_id`.

## Scope

### In Scope
- Add `project_code` to `add_task` tool's `inputSchema` as a required field
- Update the `add_task` handler to resolve project_code and include `project_id` in the insert dict
- Include project name in success response for confirmation

### Out of Scope
- The lookup helper itself (REQ-01)
- `update_task` changes (REQ-03)
- Rule/doc updates (REQ-04)

## Architecture Notes

- `project_code` is added to `required` array alongside `description`, `category`, `company`, `priority`.
- The handler calls `resolve_project_code()` early — if it raises `ValueError`, return an error response with valid codes. This fails fast before generating a task ID.
- The resolved UUID is stored as `project_id` in the new_task dict.
- The success response already returns the full task JSON; the `project_id` will be visible there. No additional project name lookup is needed — the UUID in the response is sufficient.

## Sub-Agent Roles Involved

- **Solution Architect** — solo execution

---

## Execution Steps

### Step 1: Add project_code to add_task inputSchema
- **Agent:** Solution Architect
- **Status:** [x] Complete
- **Reads:** `tools/mcp-server/src/om_apex_mcp/tools/tasks.py` (lines 89-108)
- **Creates/Modifies:** `tools/mcp-server/src/om_apex_mcp/tools/tasks.py`
- **Task:** In the `add_task` Tool definition (line 90-108):
  1. Add `"project_code"` property to `properties` dict:
     ```python
     "project_code": {"type": "string", "description": "Project code (e.g., mcp-server, portal, ai-quorum, root). Required."},
     ```
  2. Add `"project_code"` to the `required` array:
     ```python
     "required": ["description", "category", "company", "priority", "project_code"],
     ```
- **Completion Check:** Tool schema includes `project_code` as a required field.
- **Depends On:** None

### Step 2: Update add_task handler to resolve and store project_id
- **Agent:** Solution Architect
- **Status:** [x] Complete
- **Reads:** `tools/mcp-server/src/om_apex_mcp/tools/tasks.py` (lines 216-251)
- **Creates/Modifies:** `tools/mcp-server/src/om_apex_mcp/tools/tasks.py`
- **Task:** In the `add_task` handler block (line 216+):
  1. After `_require_supabase()` (line 217), add project_code resolution:
     ```python
     # Resolve project_code to UUID
     project_code = arguments["project_code"]
     try:
         project_id = resolve_project_code(project_code)
     except ValueError as e:
         return [TextContent(type="text", text=f"Error: {e}")]
     ```
  2. After building `new_task` dict (line 234), add:
     ```python
     new_task["project_id"] = project_id
     ```
     Place this right after `"created_at"` and before the optional field checks.
- **Completion Check:** Calling `add_task` without `project_code` returns validation error. Calling with invalid code returns error with valid codes list. Calling with valid code creates task with `project_id` populated.
- **Depends On:** Step 1, REQ-01

---

## Risks & Assumptions

- **Assumption:** REQ-01's `resolve_project_code` is implemented and importable before this REQ executes.
- **Risk:** If `resolve_project_code` raises `RuntimeError` (Supabase unavailable), it will propagate up. This is acceptable — `_require_supabase()` already guards against this.

## Open Questions

None.

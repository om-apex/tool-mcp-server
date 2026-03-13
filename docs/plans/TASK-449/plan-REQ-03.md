# Implementation Plan — TASK-449 / REQ-03: Add project_code to update_task tool

**Task:** TASK-449
**Requirement:** REQ-03
**Date:** 2026-03-12
**Status:** Ready for Execution
**Complexity:** Low
**Total Steps:** 2
**Steps Remaining:** 0
**Depends On:** REQ-01

---

## Overview

Add `project_code` as an optional parameter to the `update_task` MCP tool. When provided, the handler resolves it to a UUID using the shared helper and includes `project_id` in the update dictionary. This allows correcting or setting the project association on existing tasks.

## Scope

### In Scope
- Add `project_code` to `update_task` tool's `inputSchema` as an optional field
- Update the `update_task` handler to resolve and include `project_id` when `project_code` is provided

### Out of Scope
- The lookup helper itself (REQ-01)
- `add_task` changes (REQ-02)
- Rule/doc updates (REQ-04)

## Architecture Notes

- `project_code` is optional in `update_task` — it's only used when you want to set or change the project.
- The resolution logic is identical to REQ-02: call `resolve_project_code()`, catch `ValueError`, return error with valid codes.
- The resolved UUID is stored as `project_id` in the updates dict.

## Sub-Agent Roles Involved

- **Solution Architect** — solo execution

---

## Execution Steps

### Step 1: Add project_code to update_task inputSchema
- **Agent:** Solution Architect
- **Status:** [x] Complete
- **Reads:** `tools/mcp-server/src/om_apex_mcp/tools/tasks.py` (lines 133-153)
- **Creates/Modifies:** `tools/mcp-server/src/om_apex_mcp/tools/tasks.py`
- **Task:** In the `update_task` Tool definition (lines 133-153), add `"project_code"` to the `properties` dict:
  ```python
  "project_code": {"type": "string", "description": "Project code to associate with task (e.g., mcp-server, portal, ai-quorum, root). Optional."},
  ```
  Add it after `"approved_at"` (line 150). Do NOT add to `required` — it stays optional.
- **Completion Check:** Tool schema includes `project_code` as an optional field.
- **Depends On:** None

### Step 2: Update update_task handler to resolve and store project_id
- **Agent:** Solution Architect
- **Status:** [x] Complete
- **Reads:** `tools/mcp-server/src/om_apex_mcp/tools/tasks.py` (lines 314-362)
- **Creates/Modifies:** `tools/mcp-server/src/om_apex_mcp/tools/tasks.py`
- **Task:** In the `update_task` handler block (line 314+), add project_code resolution after the existing field checks (after the `approved_at` block, ~line 352):
  ```python
  if arguments.get("project_code"):
      try:
          project_uuid = resolve_project_code(arguments["project_code"])
          updates["project_id"] = project_uuid
          updated_fields.append("project_id")
      except ValueError as e:
          return [TextContent(type="text", text=f"Error: {e}")]
  ```
- **Completion Check:** Calling `update_task` with a valid `project_code` sets `project_id` on the task. Calling with an invalid code returns an error with valid codes list. Calling without `project_code` works as before (no change to project_id).
- **Depends On:** Step 1, REQ-01

---

## Risks & Assumptions

- **Assumption:** REQ-01's `resolve_project_code` is implemented before this REQ executes.
- **Risk:** None specific — same patterns as existing update_task field handling.

## Open Questions

None.

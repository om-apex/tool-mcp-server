# Implementation Plan — TASK-449 / REQ-04: Update workflow rules and documentation

**Task:** TASK-449
**Requirement:** REQ-04
**Date:** 2026-03-12
**Status:** Ready for Execution
**Complexity:** Low
**Total Steps:** 3
**Steps Remaining:** 0
**Depends On:** None

---

## Overview

Update Claude Code workflow rules to document the mandatory `project_code` field and the confirmation protocol. Fix the DB schema reference doc to accurately reflect the actual column name and type.

## Scope

### In Scope
- Update `~/.claude/rules/02-mcp-tools.md` — add project_code mandatory note and confirmation protocol
- Update `~/.claude/rules/06-workflow.md` — add project_code requirement to task creation sections
- Fix `tools/mcp-server/docs/DB-SCHEMA-QUICK-REF.md` — correct `project_code TEXT` to `project_id UUID`

### Out of Scope
- MCP tool code changes (REQ-01, REQ-02, REQ-03)
- Syncing rules to dotfiles repo (done by `sync-rules.sh` separately)

## Architecture Notes

- Rule changes are behavioral instructions for Claude Code, not code.
- The confirmation protocol should be concise: use `$PROJECT_CODE` as default, confirm with Nishad if task context suggests a different project, propose directly if clearly derivable.
- The DB schema doc fix is a simple column name/type correction.

## Sub-Agent Roles Involved

- **Solution Architect** — solo execution

---

## Execution Steps

### Step 1: Update 02-mcp-tools.md with project_code requirements
- **Agent:** Solution Architect
- **Status:** [x] Complete
- **Reads:** `~/.claude/rules/02-mcp-tools.md`
- **Creates/Modifies:** `~/.claude/rules/02-mcp-tools.md`
- **Task:** Add a new section after the `add_task` row in the MCP tools table or after the `get_pending_tasks` Filter Requirement section. Add:
  ```markdown
  ### `add_task` — Mandatory `project_code`
  Every task must have a `project_code`. This field is required by the MCP tool.

  **Protocol:**
  1. Default to `$PROJECT_CODE` from the current session
  2. If the task clearly belongs to a different project (e.g., mentions "portal"
     while session is `ai-quorum`), propose the correct code
  3. If ambiguous, confirm with Nishad: "Creating as `mcp-server` task — correct?"
  4. Valid codes: `root`, `ai-quorum`, `crm-integration`, `om-cortex`, `om-wms`,
     `vision-picking`, `wms-floor-assistant`, `wms-gate-keeper`, `ai-solutions`,
     `apex`, `luxe-properties`, `portal`, `supply-chain`, `mcp-server`, `sdlc-standards`

  ### `update_task` — Optional `project_code`
  Use `project_code` parameter to set or correct a task's project association.
  ```
- **Completion Check:** Rule file contains the new section with protocol and valid codes list.
- **Depends On:** None

### Step 2: Update 06-workflow.md with project_code in task creation
- **Agent:** Solution Architect
- **Status:** [x] Complete
- **Reads:** `~/.claude/rules/06-workflow.md`
- **Creates/Modifies:** `~/.claude/rules/06-workflow.md`
- **Task:** Add a brief note about mandatory project_code in the "Six Task Sources" section. At the top of the section (or as a standalone subsection before Source 1), add:
  ```markdown
  ### Project Code Requirement
  Every task created via `add_task` requires a `project_code` parameter.
  See `02-mcp-tools.md` for the confirmation protocol and valid codes.
  ```
  This keeps the workflow rule lean and delegates detail to 02-mcp-tools.md.
- **Completion Check:** 06-workflow.md references the project_code requirement and points to 02-mcp-tools.md for protocol details.
- **Depends On:** None

### Step 3: Fix DB-SCHEMA-QUICK-REF.md — project_code -> project_id
- **Agent:** Solution Architect
- **Status:** [x] Complete
- **Reads:** `tools/mcp-server/docs/DB-SCHEMA-QUICK-REF.md` (line 20)
- **Creates/Modifies:** `tools/mcp-server/docs/DB-SCHEMA-QUICK-REF.md`
- **Task:** On line 20, change:
  ```
  | project_code | TEXT | Optional project code |
  ```
  to:
  ```
  | project_id | UUID | FK to projects.id — resolved from project_code at creation time |
  ```
  Also update the "Last updated" date at the top of the file.
- **Completion Check:** Doc correctly shows `project_id UUID` with FK note. No reference to `project_code TEXT` remains in the tasks schema section.
- **Depends On:** None

---

## Risks & Assumptions

- **Assumption:** `sync-rules.sh` will be run after rule changes to sync to dotfiles repo. This is standard practice and not part of this REQ.
- **Risk:** None — these are documentation-only changes.

## Open Questions

None.

# Team Protocol — Multi-Agent Coordination

> Last updated: 2026-02-09

## Overview

Om Apex uses Claude Code's multi-agent teams for parallel execution of complex tasks. This protocol defines how teams are created, coordinated, and managed.

## Roles

### Solution Architect (Team Lead)
- Decides team composition and size based on work at hand
- Assigns tasks to teammates
- Makes architectural decisions without waiting for user approval
- Records all decisions via MCP `add_decision`
- Resolves blockers and reassigns work as needed

### Developers (1-N)
- Execute assigned tasks (frontend, backend, infrastructure)
- Commit frequently with clear messages
- Report completion and blockers to Architect
- Scale dynamically — more developers spawn as work grows

### Tester/QA (0-N)
- Verify completed work against requirements
- Run test suites and report results
- Spawn as testing workload increases
- Zero testers is valid for small tasks

### Researcher (0-1)
- Explores codebase, reads docs, gathers context
- Read-only agent — cannot edit files
- Used for investigation before implementation

## Dynamic Team Sizing

The Architect decides team composition based on the task. Not all roles are needed for every task.

| Task Type | Typical Team |
|-----------|-------------|
| Single bug fix | 1 developer (no team needed) |
| Feature addition | 1-2 developers + 1 tester |
| Major refactor | 2-3 developers + 1-2 testers |
| Full sprint | 3-5 developers + 2-3 testers |
| Investigation | 1 researcher |

### Scaling Rules
- Start with minimum viable team
- Add developers when parallel work opportunities appear
- Add testers when implemented features need verification
- Scale down when work completes — send shutdown requests
- Never run more agents than there are independent tasks

## Work Assignment

1. Architect creates tasks via `TaskCreate` with clear descriptions
2. Architect assigns tasks to teammates via `TaskUpdate` with `owner`
3. Teammates claim unassigned tasks in ID order (lowest first)
4. When a task is done, teammate marks it `completed` and checks `TaskList` for next work
5. If blocked, teammate notifies Architect immediately

## Communication Protocol

### Between Teammates
- Use `SendMessage` for direct communication (required — text output is NOT visible)
- Use `TaskUpdate` to mark task status changes
- Commit code frequently with clear commit messages
- Never edit the same file as another teammate simultaneously

### With Architect
- Report task completion via `SendMessage`
- Report blockers immediately — don't stay stuck > 10 minutes
- Architect resolves conflicts and reassigns work

### With User (Nishad)
- Architect is the primary contact with the user
- Teammates do not message the user directly
- Architect summarizes team progress when asked
- Blockers requiring user input are escalated by Architect

## Git Strategy

### Branch Model
- All work on `main` branch (small team, fast iteration)
- Feature branches only for risky changes or when explicitly requested

### Commit Protocol
- One feature/fix per commit
- Clear commit messages: `"Fix session timeout on profile page"`
- Teammates work on different files to avoid conflicts
- If conflicts occur: Architect resolves, then work continues

### Push Protocol
- Push after each completed feature/fix
- Verify build passes before pushing
- Never force-push to main

## Decision Making

The Solution Architect has authority to make decisions without user approval for:
- Technology choices within existing stack
- Implementation approaches
- Team composition and sizing
- Task prioritization and reassignment
- Architecture patterns (within project conventions)

The Architect MUST:
- Record all decisions via MCP `add_decision` with rationale
- Inform the user of significant decisions at next check-in
- Escalate to user only for: budget impact, new external services, breaking changes to deployed systems

## Escalation Protocol

| Situation | Action |
|-----------|--------|
| Teammate blocked > 10 min | Message Architect |
| Architect can't resolve | Create HIGH priority task in MCP, message user |
| Deploy failure | Stop all work, investigate, notify user |
| MCP server down | Continue work, stage updates in `.pending-sync.md` |
| Merge conflict | Architect resolves, affected teammates pause |
| Test failures in main | Stop new work, fix first |

## Shutdown Protocol

1. Architect verifies all assigned tasks are completed
2. Architect sends `shutdown_request` to each teammate
3. Teammates approve shutdown (or reject with reason if still working)
4. Architect confirms all teammates shut down
5. Architect commits final state, updates handoff, logs progress

## Quality Gates

Before marking a phase complete:
- [ ] All assigned tasks marked completed
- [ ] Code builds without errors
- [ ] No console errors on page load
- [ ] Git is clean (all committed and pushed)
- [ ] Task tracker updated

Before demo/deployment:
- [ ] Full test pass by QA teammate(s)
- [ ] All critical/high bugs resolved
- [ ] User has reviewed and approved
- [ ] Handoff updated with deployment status

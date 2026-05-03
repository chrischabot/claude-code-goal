---
description: "Show goal plugin command help"
argument-hint: ""
hide-from-slash-command-tool: "true"
---

# Goal Help

The goal plugin provides persistent, markdown-backed goal mode for Claude Code.

Commands:

- `/goal:goal OBJECTIVE [--max-iterations N] [--completion-promise TEXT]` sets a new active goal.
- `/goal:goal` or `/goal:status` shows the current goal.
- `/goal:pause` pauses continuation without deleting state.
- `/goal:resume` resumes continuation and asks Claude to keep working.
- `/goal:stop` stops continuation while preserving state.
- `/goal:clear` deletes this session's goal state file.
- `/goal:complete` marks the goal complete.
- `/goal:note NOTE` records a continuation note.

State is stored under `.claude/goals/current.goal.md` when the slash command cannot see Claude Code's session ID, or `.claude/goals/<session-id>.goal.md` when it can. The hooks record and respect the real session ID once they observe it. While a goal is active, the Stop hook blocks normal turn termination and feeds Claude a continuation prompt until the completion promise is emitted or max iterations is reached.

---
description: "Set or show the active persistent goal"
argument-hint: "[OBJECTIVE] [--max-iterations N] [--completion-promise TEXT]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py:*)"]
hide-from-slash-command-tool: "true"
---

# Goal Command

Create or replace the active goal for this Claude Code session. With no arguments, show the current goal status.

```!
"${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py" goal-raw <<'__CLAUDE_GOAL_ARGUMENTS__'
$ARGUMENTS
__CLAUDE_GOAL_ARGUMENTS__
```

If the command output says a goal was activated, begin working on that objective now. Keep working autonomously until the objective is complete, then output the exact completion promise shown by the command.

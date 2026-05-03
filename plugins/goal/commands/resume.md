---
description: "Resume a paused or stopped goal"
argument-hint: ""
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py:*)"]
hide-from-slash-command-tool: "true"
---

# Resume Goal

```!
"${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py" resume
```

If the command succeeds, continue the goal now. Read the current state before choosing the next action and only output the completion promise when the goal is genuinely complete.

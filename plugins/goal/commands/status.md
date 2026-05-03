---
description: "Show the active goal state"
argument-hint: ""
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py:*)"]
hide-from-slash-command-tool: "true"
---

# Goal Status

```!
"${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py" status
```

Report the goal status and state file path concisely.

---
description: "Delete the goal state file for this session"
argument-hint: ""
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py:*)"]
hide-from-slash-command-tool: "true"
---

# Clear Goal

```!
"${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py" clear
```

Confirm that the goal state has been cleared.

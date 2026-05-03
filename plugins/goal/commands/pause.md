---
description: "Pause autonomous goal continuation without deleting state"
argument-hint: ""
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py:*)"]
hide-from-slash-command-tool: "true"
---

# Pause Goal

```!
"${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py" pause
```

Confirm that the goal is paused. Do not continue working on the paused goal unless the user asks.

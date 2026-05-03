---
description: "Stop autonomous goal continuation while preserving state"
argument-hint: ""
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py:*)"]
hide-from-slash-command-tool: "true"
---

# Stop Goal

```!
"${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py" stop
```

Confirm that the goal has been stopped and that the state file remains available for inspection or later resume.

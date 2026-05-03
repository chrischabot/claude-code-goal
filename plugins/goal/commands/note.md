---
description: "Append a continuation note to the active goal"
argument-hint: "NOTE"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py:*)"]
hide-from-slash-command-tool: "true"
---

# Goal Note

```!
"${CLAUDE_PLUGIN_ROOT}/bin/goalctl.py" note-raw <<'__CLAUDE_GOAL_NOTE__'
$ARGUMENTS
__CLAUDE_GOAL_NOTE__
```

Confirm that the note was recorded.

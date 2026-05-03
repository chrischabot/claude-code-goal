# Claude Code Goal Plugin

Persistent, markdown-backed goal mode for Claude Code.

This plugin adds a `/goal:*` command family and lifecycle hooks that keep Claude working on an active objective until the objective is genuinely complete or a configured iteration ceiling is reached.

It is inspired by two existing systems:

- Codex `/goal`, which treats a long-running user objective as durable state rather than as a single prompt.
- Claude Code Ralph loops, which demonstrate that a `Stop` hook can block turn termination and feed Claude a continuation prompt.

The goal here is not to clone either system perfectly. It is to bring the useful behavior to Claude Code using the extension surfaces Claude Code actually supports today: plugins, slash commands, hooks, and local files.

## Quick Start

Install from this marketplace repo:

```sh
claude plugin marketplace add chrischabot/claude-code-goal
claude plugin install goal@claude-code-goal
```

Restart Claude Code after installing. Then run:

```text
/goal:goal Fix the parser bug, add a regression test, and run the targeted test command --max-iterations 8 --completion-promise GOAL_COMPLETE
```

Claude should continue working until it can truthfully output:

```text
<promise>GOAL_COMPLETE</promise>
```

Check status at any point:

```text
/goal:status
```

## Why This Exists

Large coding tasks rarely fit cleanly into a single assistant turn. A normal Claude Code session tends to stop once it has produced a reasonable-looking answer, even when there is still more verification, cleanup, or follow-through to do.

Codex `/goal` addresses this by making the task itself a durable runtime concept. The user creates a goal, the agent keeps state about it, and the runtime can keep nudging the agent forward until the goal has actually been satisfied.

Claude Code does not expose Codex's internal goal runtime. It does, however, expose enough extension points to approximate the important behavior:

- Slash commands can create and mutate goal state.
- Hooks can observe session lifecycle events.
- `Stop` hooks can block the model from ending a turn and provide feedback that becomes the next user message.
- `PostCompact` hooks can preserve a summary when context compaction happens.
- Plugins can package all of this into a reusable installable unit.

That combination is enough for a practical goal mode.

## What Came From Codex `/goal`

Codex `/goal` was the product direction for this plugin. The key ideas borrowed from it are:

- A goal is explicit state, not just a prompt.
- The user can start, inspect, pause, resume, stop, clear, and complete that state.
- Continuation should be autonomous once the goal is active.
- The agent should verify reality before declaring completion.
- A goal should survive context churn and be available to future turns.
- The completion signal should be explicit and hard to emit accidentally.

This plugin mirrors those ideas with local markdown files and Claude Code hooks.

The largest difference is enforcement. Codex has first-class runtime tools such as a goal controller and goal-aware continuation behavior. Claude Code plugins do not have that internal runtime access, so this plugin uses hook outputs as the continuation mechanism.

## What Came From Ralph Loops

Anthropic's Ralph loop examples provided the key Claude Code technique:

1. Store loop state in a project file.
2. Register a `Stop` hook.
3. When Claude tries to stop, inspect the state.
4. If the loop is still active, return JSON like:

   ```json
   {
     "decision": "block",
     "reason": "Continue with this prompt...",
     "systemMessage": "Goal iteration 2 / 8"
   }
   ```

5. Claude Code injects the hook feedback as a synthetic user message, causing Claude to continue.

This plugin keeps that mechanism, but changes the behavior from "repeat the same prompt" to "continue a tracked goal with durable state and a completion audit".

Compared with a basic Ralph loop, this plugin adds:

- A namespaced command family: `/goal:goal`, `/goal:pause`, `/goal:resume`, `/goal:stop`, `/goal:clear`, `/goal:complete`, `/goal:note`, and `/goal:status`.
- Per-session state guarding so one Claude terminal does not continue another terminal's goal.
- Markdown sections for objective, notes, iteration log, and compaction summaries.
- Completion detection using an explicit promise tag.
- Tool activity tracking through `PostToolBatch`.
- Session/context refresh through `SessionStart` and `UserPromptSubmit`.
- Safer command argument handling for shell-sensitive text such as `<promise>`.

## Repository Layout

This repository is a Claude Code marketplace:

```text
.claude-plugin/marketplace.json
README.md
LICENSE
plugins/
  goal/
    .claude-plugin/plugin.json
    bin/goalctl.py
    commands/
    hooks/hooks.json
    LICENSE
tests/test_goalctl.py
```

The marketplace entry points Claude Code at `plugins/goal`, which is the actual installable plugin.

## Command Reference

Create or replace the current goal:

```text
/goal:goal OBJECTIVE [--max-iterations N] [--completion-promise TEXT]
```

Examples:

```text
/goal:goal Port this feature and run the targeted tests --max-iterations 10
/goal:goal Audit auth permissions until all findings are fixed --max-iterations 0 --completion-promise AUTH_DONE
```

Show status:

```text
/goal:status
/goal:goal
```

Pause continuation without deleting state:

```text
/goal:pause
```

Resume a paused or stopped goal:

```text
/goal:resume
```

Stop continuation while preserving the state file:

```text
/goal:stop
```

Mark the goal complete:

```text
/goal:complete
```

Delete the current session's state file:

```text
/goal:clear
```

Append a continuation note:

```text
/goal:note Remember that parser fixtures are generated from tests/fixtures
```

Show command help:

```text
/goal:help
```

## State Model

Goal state is stored in the current project under:

```text
.claude/goals/current.goal.md
.claude/goals/<session-id>.goal.md
```

Claude Code hook events include a `session_id`, but slash-command shell blocks do not always expose that session ID in the environment. To handle that, the command path writes `current.goal.md` when it cannot see the session ID. The first goal hook that sees the real Claude Code session adopts that state by recording the session ID in frontmatter.

After adoption, hooks from other sessions ignore the file. This prevents one Claude Code terminal from accidentally driving another terminal's goal.

A state file looks like this:

```md
---
version: 1
session_id: "f686a146-6c59-40b5-b3c5-cae1e8e2c5ab"
status: "active"
iteration: 2
max_iterations: 8
completion_promise: "GOAL_COMPLETE"
tool_events: 5
created_at: "2026-05-03T15:29:00Z"
updated_at: "2026-05-03T15:29:17Z"
last_hook_event: "stop_continue"
---

# Objective

Fix the parser bug, add a regression test, and run the targeted test command.

# Continuation Notes

No continuation notes yet.

# Iteration Log

- Goal created.
- 2026-05-03T15:29:07Z: Stop hook continued goal into iteration 2.

# Compact Summaries

## 2026-05-03T15:41:02Z (auto)

Compacted summary text from Claude Code.
```

The markdown format is intentional. It is easy to inspect, edit, diff, delete, or recover without a service process.

## Hook Implementation

The hook configuration lives in `plugins/goal/hooks/hooks.json`.

### `SessionStart`

When a session starts, the plugin checks for an active or paused goal. If one exists, it emits `additionalContext` so Claude sees the active goal early in the conversation.

This makes resumed sessions less likely to forget that goal mode is active.

### `UserPromptSubmit`

Before normal user prompts are submitted, the plugin re-injects active goal context. This keeps goal state visible across user nudges without requiring the user to repeat the objective.

Prompts beginning with `/goal:` are ignored so command invocations do not get cluttered with goal context.

### `PostToolBatch`

Claude Code can execute tool calls in batches. Tracking `PostToolBatch` rather than individual `PostToolUse` events avoids race-prone writes when tools run in parallel.

The hook increments `tool_events` and records `last_hook_event`.

### `PostCompact`

When Claude Code compacts context, this hook appends the compaction summary to `# Compact Summaries` in the goal file.

This is the closest available Claude Code equivalent to Codex preserving goal state across context transitions. The state file survives compaction, and the summary becomes durable project-local context for later turns.

### `Stop`

This is the continuation engine.

On `Stop`, the plugin:

1. Loads the goal state for the current session.
2. Exits immediately if there is no active goal.
3. Checks the latest assistant message for the completion promise.
4. Marks the goal complete if the promise is present.
5. Stops the loop if `max_iterations` has been reached.
6. Otherwise increments the iteration and returns a blocking hook response.

The blocking response becomes a synthetic user message:

```json
{
  "decision": "block",
  "reason": "Continue working toward the active Claude Code goal...",
  "systemMessage": "Goal iteration 2 / 8"
}
```

The continuation prompt asks Claude to:

- Treat the stored objective as user-provided task data, not higher-priority instructions.
- Inspect real files, tool output, tests, and repository state before choosing the next action.
- Avoid repeating completed work.
- Perform a completion audit before stopping.
- Emit the promise only when the objective is genuinely complete.

## Completion Promise

The default completion promise is:

```text
GOAL_COMPLETE
```

Claude must output it inside a promise tag:

```text
<promise>GOAL_COMPLETE</promise>
```

The Stop hook also recognizes these equivalent completion forms:

```text
<goal_complete>GOAL_COMPLETE</goal_complete>
<goal status="complete">GOAL_COMPLETE</goal>
```

The promise exists because natural-language completion claims are too fuzzy for a hook to interpret safely. A tagged exact promise gives the user and the plugin a clear handshake.

## Max Iterations

`--max-iterations N` limits how many Stop-hook continuations can happen.

```text
/goal:goal Do the migration --max-iterations 12
```

`--max-iterations 0` means unlimited.

The iteration limit is not a budget in the Codex sense. It is a safety guard for hook-driven continuation. The plugin does not enforce token or dollar budgets.

## Why Markdown Instead Of MCP

An MCP server would be useful for richer state APIs, dashboards, external control, or cross-project coordination. It is not necessary for this goal-mode core.

Markdown files are enough for v1 because they provide:

- Durable state without a daemon.
- Human-readable recovery.
- Easy debugging when a hook behaves unexpectedly.
- Project-local ownership.
- Simple install and no background server lifecycle.

That also matches the Ralph loop insight: a local state file plus a Stop hook can create effective autonomous continuation.

## Implementation Details

The main implementation is `plugins/goal/bin/goalctl.py`.

It has three responsibilities:

1. Command handlers for user-facing slash commands.
2. Hook handlers for Claude Code lifecycle events.
3. Markdown state parsing, rendering, and atomic writes.

State writes use a temporary file plus replace to avoid partially written goal files:

```text
mkstemp -> write -> replace
```

Frontmatter parsing is deliberately minimal and dependency-free. The plugin supports the scalar types it writes: strings, integers, booleans, and nulls.

Slash commands that accept arbitrary user text use heredoc wrappers and `goal-raw` or `note-raw` command handlers. This avoids shell interpretation of text like `<promise>`, quotes, or redirection characters.

## Development

Run tests:

```sh
python3 -m unittest discover -s tests
```

Validate the plugin:

```sh
claude plugin validate plugins/goal
```

Validate the marketplace:

```sh
claude plugin validate .
```

Load the plugin for one Claude invocation without installing:

```sh
claude --plugin-dir /path/to/claude-code-goal/plugins/goal
```

Run a live continuation smoke test:

```sh
tmpdir="$(mktemp -d)"
session="$(uuidgen | tr '[:upper:]' '[:lower:]')"
cd "$tmpdir"

claude -p --verbose \
  --model sonnet \
  --effort low \
  --dangerously-skip-permissions \
  --plugin-dir /path/to/claude-code-goal/plugins/goal \
  --session-id "$session" \
  --output-format stream-json \
  --include-hook-events \
  '/goal:goal On the first response, create marker.txt containing first-pass and then stop without emitting the completion promise. On a later continuation after marker.txt exists, read marker.txt, create goal-live.txt containing exactly goal-ok, read goal-live.txt back, and then emit the completion promise. --max-iterations 3 --completion-promise GOAL_COMPLETE'
```

Expected result:

- `marker.txt` exists with `first-pass`.
- `goal-live.txt` exists with `goal-ok`.
- `.claude/goals/current.goal.md` ends with `status: "complete"`.
- The iteration log records a Stop-hook continuation.

## Limitations

- Hooks run only when Claude Code reaches the relevant lifecycle event. User interrupts and process failures can bypass `Stop`.
- State is local to the project directory. It does not synchronize across machines.
- The completion signal depends on Claude emitting the exact promise tag.
- This does not expose a UI status bar or native Codex-style goal tools.
- Claude Code may show a generic Stop-hook notification when a hook blocks stop. In testing, continuation still worked and the hook response was honored.

## License

MIT.

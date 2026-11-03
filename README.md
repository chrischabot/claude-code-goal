# Claude Code Goal

Claude Code Goal is a plugin that gives a Claude Code session a standing objective and keeps Claude working on it across turns. It is for anyone handing Claude a job too large for a single turn, such as a migration or a bug fix that should end with passing tests, because a normal session tends to stop once it has a reasonable-looking answer, and the verification and cleanup then wait for you to ask.

The plugin builds on two earlier ideas. [Codex `/goal`](https://developers.openai.com/codex/cli/slash-commands#set-or-view-a-task-goal-with-goal) treats a long-running objective as durable state rather than a single prompt, and Anthropic's [Ralph Loop plugin](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/ralph-loop) uses a `Stop` hook to refuse Claude's attempt to finish and hand it a prompt to continue with. This plugin brings them together: the objective, iteration count and log live in a markdown file in your project, and a `Stop` hook sends Claude back to work until it emits an exact completion tag or the goal reaches an iteration ceiling. There is no service to run, and when something looks wrong you can open the file and see what happened.

Claude Code added a built-in [`/goal`](https://code.claude.com/docs/en/goal) about a week after this plugin was published. It has a small, fast model judge your condition after each turn, and it is the simpler choice if all you need is a session that keeps going until that condition holds. This plugin is still useful when you want the state in a file you can read, edit and diff, a numeric ceiling enforced by a script, and explicit pause and resume. The trade-off is that completion rests on a tag Claude emits itself, so Claude is marking its own work where the built-in asks a second model.

## Install

You need Claude Code and Python 3.11 or later, available as `python3` on your `PATH`. The plugin has no other dependencies.

```sh
claude plugin marketplace add chrischabot/claude-code-goal
claude plugin install goal@claude-code-goal
```

Restart Claude Code after installing.

## Usage

Start a goal from inside a session. The commands are namespaced under the plugin, so the main one is `/goal:goal`; plain `/goal` is Claude Code's built-in.

```text
/goal:goal Fix the parser bug, add a regression test, and run the targeted test command --max-iterations 8
```

Claude starts immediately, and each time it tries to stop, the plugin sends it back to work until it outputs `<promise>GOAL_COMPLETE</promise>` or the goal reaches its ceiling. `--completion-promise TEXT` replaces that token with your own. A goal does not change your permission mode, so a tool call you have not allowed will still stop and ask.

The arguments are split with shell-style quoting. Flags can appear anywhere in the text, line breaks collapse into spaces, and an objective containing an apostrophe needs double quotes around it, as in `/goal:goal "Fix the user's login bug"`.

| Command | Effect |
| --- | --- |
| `/goal:goal OBJECTIVE [--max-iterations N] [--completion-promise TEXT]` | Creates or replaces the goal and starts work. With no arguments, shows status. |
| `/goal:status` | Shows the status, iteration, tool-call count, completion promise and objective. |
| `/goal:pause` | Stops continuation. Claude is still told about a paused goal when a session starts. |
| `/goal:resume` | Reactivates a paused or stopped goal and carries on. |
| `/goal:stop` | Stops continuation and keeps the state file. |
| `/goal:complete` | Marks the goal complete. |
| `/goal:clear` | Deletes the state file. |
| `/goal:note NOTE` | Appends a timestamped note to the state file. |
| `/goal:help` | Lists the commands. |

### What ends a goal

A goal runs until Claude emits the completion tag, the goal reaches its ceiling, or you run `/goal:pause`, `/goal:stop`, `/goal:complete` or `/goal:clear`. `--max-iterations N` sets the ceiling and counts passes including the first, so `--max-iterations 8` allows seven continuations. The default is 30, and 0 removes the ceiling. The plugin counts passes rather than tokens or money and enforces no budget, so an unlimited goal keeps spending until one of the other conditions ends it. A goal that stopped at its ceiling gets only one more turn from `/goal:resume`, because the next `Stop` still finds it at the limit, so raise `max_iterations` in the state file first if it needs longer.

Two things outside the plugin can also end a turn while the goal is still active. Claude Code overrides a `Stop` hook that has blocked eight times in a row with no tool call in between, and ends the turn with a warning. Any tool call resets that count, so the cap mainly catches a goal that has stopped doing anything, and `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` raises or disables it. An interrupt or a process failure can bypass `Stop` altogether, because hooks run only when Claude Code reaches the relevant event. In both cases the file still marks the goal as active, so your next prompt in that session picks it up.

## How it works

The commands and hooks share one script, `plugins/goal/bin/goalctl.py`, and the `Stop` hook is what keeps the work going. When Claude tries to end a turn, the hook loads the goal for that session and, if the goal is active, looks for the completion tag in Claude's last message. If the tag is there, it marks the goal complete, and if the goal is at its ceiling, it marks it stopped; either way Claude is allowed to finish. Otherwise the hook increments the iteration, logs it and returns `"decision": "block"` with a continuation prompt, which Claude Code hands to Claude as the reason to keep working. That prompt presents the objective as task data rather than as higher-priority instructions, tells Claude to read real files, command output and test results before choosing its next action, and asks for a requirement-by-requirement audit before it emits the tag. The audit is an instruction rather than something the script can check, because all the hook can see is whether the tag is present. The hook accepts the token inside `<promise>`, `<goal_complete>` or `<goal status="complete">`, and the token itself has to match exactly.

The remaining hooks keep the goal in view and maintain the file:

| Hook | Job |
| --- | --- |
| `SessionStart` | Tells Claude about an active or paused goal. |
| `UserPromptSubmit` | Repeats the active goal with each prompt, skipping `/goal:` commands. |
| `PostToolBatch` | Counts tool calls once per batch, which avoids concurrent writes when tools run in parallel. |
| `PostCompact` | Appends Claude Code's compaction summary to the state file. |
| `SessionEnd` | Records that the session ended. |

State lives in `.claude/goals/` in your project, as a file like this:

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
```

Hook events include Claude Code's session ID, but slash commands cannot always see it. A command that can see it writes `<session-id>.goal.md`. One that cannot writes `current.goal.md`, and the first hook to fire adopts that file by recording its session ID in the frontmatter. From then on, hooks from any other session ignore the goal, which stops a second terminal in the same project from continuing it. Writes go through a temporary file and a rename, so a process that dies midway does not leave a half-written goal.

Notes and compaction summaries stay in the file. The hooks feed back only the objective, the counters, the completion promise and a truncated copy of Claude's last message, so Claude sees a note only if it opens the file.

A local file was enough for this core. An MCP server would suit dashboards or cross-project coordination, but durable state alone does not need a daemon to keep alive.

## Limitations

- A goal belongs to one session ID, and Claude Code changes that ID on `/clear` as well as in a new session. The hooks then stop seeing the goal, so set it again. Terminals that cannot see their session ID also share `current.goal.md`, so `/goal:goal` in one replaces the goal in the other.
- State is local to the project directory and does not sync across machines. The plugin does not add `.claude/goals/` to your `.gitignore`, so add it if you do not want goal files committed.
- Claude Code reports a blocked stop with a hook notification that can look like an error. That block is how continuation works.
- There is no status bar or other native goal interface, so `/goal:status` and the state file are how you check progress.

## Development

The repository is itself a Claude Code marketplace. `.claude-plugin/marketplace.json` points at `plugins/goal`, which holds the plugin manifest, command files, hook configuration and controller.

```sh
python3 -m unittest discover -s tests
claude plugin validate plugins/goal
claude plugin validate .
claude --plugin-dir /path/to/claude-code-goal/plugins/goal
```

The unit tests need only Python and drive `goalctl.py` as a subprocess with simulated hook payloads, so they cover the state machine rather than Claude Code itself. The last command loads the plugin for one session without installing it. To check real continuation, run this smoke test, which calls a model and skips permission prompts, so keep it in a temporary directory:

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

Afterwards `marker.txt` should contain `first-pass`, `goal-live.txt` should contain `goal-ok`, and the state file under `.claude/goals/` should show `status: "complete"` with a logged Stop-hook continuation.

## Credits and license

The product direction comes from Codex `/goal`. The `Stop`-hook continuation comes from Anthropic's Ralph Loop plugin, which implements Geoffrey Huntley's Ralph technique and uses the same `--max-iterations` and `--completion-promise` flags and `<promise>` tag. Where Ralph feeds the same prompt back each time, this plugin builds its continuation prompt from tracked state, asks for a completion audit, and adds commands to pause, resume, stop and annotate the goal.

Released under the [MIT License](LICENSE). The license file carries the line `Copyright (c) 2026 OpenAI Codex`, and `plugins/goal/.claude-plugin/plugin.json` names OpenAI Codex as the plugin's author. Chris Chabot owns and publishes this marketplace.

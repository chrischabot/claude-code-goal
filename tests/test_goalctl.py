from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOALCTL = ROOT / "plugins" / "goal" / "bin" / "goalctl.py"


class GoalCtlTest(unittest.TestCase):
    def run_goalctl(
        self,
        cwd: Path,
        *args: str,
        session_id: str = "test-session",
        stdin: dict[str, object] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["CLAUDE_CODE_SESSION_ID"] = session_id
        input_text = json.dumps(stdin) if stdin is not None else None
        return subprocess.run(
            [sys.executable, str(GOALCTL), *args],
            cwd=cwd,
            env=env,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def assert_ok(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")

    def state_path(self, cwd: Path, session_id: str = "test-session") -> Path:
        return cwd / ".claude" / "goals" / f"{session_id}.goal.md"

    def read_state_text(self, cwd: Path, session_id: str = "test-session") -> str:
        return self.state_path(cwd, session_id).read_text(encoding="utf-8")

    def test_goal_lifecycle_and_markdown_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)

            result = self.run_goalctl(
                cwd,
                "goal",
                "Write",
                "the",
                "thing",
                "--max-iterations",
                "4",
                "--completion-promise",
                "DONE",
            )
            self.assert_ok(result)
            state_text = self.read_state_text(cwd)
            self.assertIn("status: \"active\"", state_text)
            self.assertIn("max_iterations: 4", state_text)
            self.assertIn("completion_promise: \"DONE\"", state_text)
            self.assertIn("Write the thing", state_text)

            result = self.run_goalctl(cwd, "status")
            self.assert_ok(result)
            self.assertIn("Goal status: active", result.stdout)
            self.assertIn("Iteration: 1", result.stdout)

            result = self.run_goalctl(cwd, "pause")
            self.assert_ok(result)
            self.assertIn("Goal paused.", result.stdout)
            self.assertIn("status: \"paused\"", self.read_state_text(cwd))

            result = self.run_goalctl(
                cwd,
                "hook-stop",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "test-session",
                    "stop_hook_active": False,
                    "last_assistant_message": "Not finished.",
                },
            )
            self.assert_ok(result)
            self.assertEqual("", result.stdout)
            self.assertIn("status: \"paused\"", self.read_state_text(cwd))

            result = self.run_goalctl(cwd, "resume")
            self.assert_ok(result)
            self.assertIn("Goal active.", result.stdout)
            self.assertIn("status: \"active\"", self.read_state_text(cwd))

            result = self.run_goalctl(cwd, "note", "Verified", "parser", "fixtures")
            self.assert_ok(result)
            self.assertIn("Verified parser fixtures", self.read_state_text(cwd))

            result = self.run_goalctl(cwd, "complete")
            self.assert_ok(result)
            self.assertIn("status: \"complete\"", self.read_state_text(cwd))

            result = self.run_goalctl(cwd, "clear")
            self.assert_ok(result)
            self.assertFalse(self.state_path(cwd).exists())

    def test_stop_hook_continues_then_stops_at_max_iterations(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            result = self.run_goalctl(cwd, "goal", "--max-iterations", "2", "Finish", "carefully")
            self.assert_ok(result)

            result = self.run_goalctl(
                cwd,
                "hook-stop",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "test-session",
                    "stop_hook_active": False,
                    "last_assistant_message": "I need more time.",
                },
            )
            self.assert_ok(result)
            payload = json.loads(result.stdout)
            self.assertEqual(
                {
                    "decision": "block",
                    "systemMessage": "Goal iteration 2 / 2",
                },
                {
                    "decision": payload["decision"],
                    "systemMessage": payload["systemMessage"],
                },
            )
            self.assertIn("Continue working toward the active Claude Code goal.", payload["reason"])
            self.assertIn("- Iteration: 2", payload["reason"])
            self.assertIn("iteration: 2", self.read_state_text(cwd))

            result = self.run_goalctl(
                cwd,
                "hook-stop",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "test-session",
                    "stop_hook_active": False,
                    "last_assistant_message": "Still not done.",
                },
            )
            self.assert_ok(result)
            self.assertEqual("", result.stdout)
            state_text = self.read_state_text(cwd)
            self.assertIn("status: \"stopped\"", state_text)
            self.assertIn("Max iterations reached at iteration 2", state_text)

    def test_stop_hook_completion_promise_marks_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            result = self.run_goalctl(
                cwd,
                "goal",
                "--completion-promise",
                "SHIP_IT",
                "Ship",
                "the",
                "change",
            )
            self.assert_ok(result)

            result = self.run_goalctl(
                cwd,
                "hook-stop",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "test-session",
                    "stop_hook_active": False,
                    "last_assistant_message": "All done.\n<promise>SHIP_IT</promise>",
                },
            )
            self.assert_ok(result)
            self.assertEqual("", result.stdout)
            state_text = self.read_state_text(cwd)
            self.assertIn("status: \"complete\"", state_text)
            self.assertIn("Completion promise detected at iteration 1", state_text)

    def test_stop_hook_active_still_detects_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            result = self.run_goalctl(cwd, "goal", "--max-iterations", "2", "Finish", "after", "continuation")
            self.assert_ok(result)

            result = self.run_goalctl(
                cwd,
                "hook-stop",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "test-session",
                    "stop_hook_active": True,
                    "last_assistant_message": "Verified.\n<promise>GOAL_COMPLETE</promise>",
                },
            )
            self.assert_ok(result)
            self.assertEqual("", result.stdout)
            self.assertIn("status: \"complete\"", self.read_state_text(cwd))

    def test_stop_hook_active_can_continue_until_max_iterations(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            result = self.run_goalctl(cwd, "goal", "--max-iterations", "2", "Need", "two", "passes")
            self.assert_ok(result)

            result = self.run_goalctl(
                cwd,
                "hook-stop",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "test-session",
                    "stop_hook_active": True,
                    "last_assistant_message": "Not done.",
                },
            )
            self.assert_ok(result)
            payload = json.loads(result.stdout)
            self.assertEqual("block", payload["decision"])
            self.assertIn("iteration: 2", self.read_state_text(cwd))

            result = self.run_goalctl(
                cwd,
                "hook-stop",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "test-session",
                    "stop_hook_active": True,
                    "last_assistant_message": "Still incomplete.",
                },
            )
            self.assert_ok(result)
            self.assertEqual("", result.stdout)
            self.assertIn("status: \"stopped\"", self.read_state_text(cwd))

    def test_raw_goal_arguments_preserve_shell_metacharacters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            result = self.run_goalctl(
                cwd,
                "goal-raw",
                stdin=None,
            )
            self.assert_ok(result)

            result = subprocess.run(
                [sys.executable, str(GOALCTL), "goal-raw"],
                cwd=cwd,
                env={**os.environ, "CLAUDE_CODE_SESSION_ID": "test-session"},
                input="Create a file mentioning '<promise>' literally --max-iterations 2 --completion-promise DONE",
                text=True,
                capture_output=True,
                check=False,
            )
            self.assert_ok(result)
            state_text = self.read_state_text(cwd)
            self.assertIn("Create a file mentioning <promise> literally", state_text)
            self.assertIn("max_iterations: 2", state_text)
            self.assertIn("completion_promise: \"DONE\"", state_text)

    def test_hook_adopts_current_state_when_command_has_no_session_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            env = os.environ.copy()
            env.pop("CLAUDE_CODE_SESSION_ID", None)
            env.pop("CLAUDE_SESSION_ID", None)
            result = subprocess.run(
                [sys.executable, str(GOALCTL), "goal", "--max-iterations", "2", "Adopt", "me"],
                cwd=cwd,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assert_ok(result)
            current_state = cwd / ".claude" / "goals" / "current.goal.md"
            self.assertTrue(current_state.exists())
            self.assertIn("session_id: \"current\"", current_state.read_text(encoding="utf-8"))

            result = self.run_goalctl(
                cwd,
                "hook-stop",
                session_id="adopt-session",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "adopt-session",
                    "stop_hook_active": False,
                    "last_assistant_message": "Not finished yet.",
                },
            )
            self.assert_ok(result)
            payload = json.loads(result.stdout)
            self.assertEqual("block", payload["decision"])
            state_text = current_state.read_text(encoding="utf-8")
            self.assertIn("session_id: \"adopt-session\"", state_text)
            self.assertIn("iteration: 2", state_text)

            result = self.run_goalctl(
                cwd,
                "hook-stop",
                session_id="other-session",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "other-session",
                    "stop_hook_active": False,
                    "last_assistant_message": "This is another session.",
                },
            )
            self.assert_ok(result)
            self.assertEqual("", result.stdout)
            self.assertIn("session_id: \"adopt-session\"", current_state.read_text(encoding="utf-8"))

    def test_context_hooks_and_compaction_capture_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            result = self.run_goalctl(cwd, "goal", "Keep", "context", "alive")
            self.assert_ok(result)

            result = self.run_goalctl(
                cwd,
                "hook-session-start",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "test-session",
                    "hook_event_name": "SessionStart",
                },
            )
            self.assert_ok(result)
            payload = json.loads(result.stdout)
            self.assertEqual("SessionStart", payload["hookSpecificOutput"]["hookEventName"])
            self.assertIn("Keep context alive", payload["hookSpecificOutput"]["additionalContext"])

            result = self.run_goalctl(
                cwd,
                "hook-post-compact",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "test-session",
                    "hook_event_name": "PostCompact",
                    "trigger": "auto",
                    "compact_summary": "Important compacted summary.",
                },
            )
            self.assert_ok(result)
            state_text = self.read_state_text(cwd)
            self.assertIn("# Compact Summaries", state_text)
            self.assertIn("Important compacted summary.", state_text)

            result = self.run_goalctl(
                cwd,
                "hook-post-tool-batch",
                stdin={
                    "cwd": str(cwd),
                    "session_id": "test-session",
                    "hook_event_name": "PostToolBatch",
                    "tool_calls": [{"tool_name": "Read"}, {"tool_name": "Bash"}],
                },
            )
            self.assert_ok(result)
            self.assertIn("tool_events: 2", self.read_state_text(cwd))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from daiklib.program import ProgramRunner
from daiklib.workspaces import safe_slug


class ProgramRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.issue = "github:backend#123"
        self.repository = self.root / "workspaces" / safe_slug(self.issue) / "backend"
        self.repository.mkdir(parents=True)
        self.state_home = self.root / "state"
        self.config = {
            "workspace": {"root": "workspaces"},
            "repositories": {"backend": {"path": "backend", "base": "main"}},
            "processes": {"broker": {"type": "broker"}},
        }

    def run_program(self, code: str, executable: str | None = None):
        workflow = {
            "states": {
                "testing": {
                    "type": "program",
                    "command": [executable or sys.executable, "-c", code],
                    "repository": "backend",
                    "timeout_seconds": 10,
                    "transitions": {
                        "succeeded": {"to": "review"},
                        "failed": {"to": "implementation"},
                        "error": {"to": "await_human"},
                    },
                }
            }
        }
        emitted = []
        with patch.dict(os.environ, {"DAIK_STATE_HOME": str(self.state_home)}):
            result = ProgramRunner(self.root, self.config, workflow).run(
                self.issue, "testing", emitted.append
            )
        return result, emitted

    def test_zero_exit_selects_succeeded_and_preserves_logs(self) -> None:
        result, emitted = self.run_program("print('verified')")

        self.assertEqual(emitted[0]["kind"], "program.started")
        self.assertEqual(emitted[1]["data"]["result"], "succeeded")
        self.assertEqual(emitted[1]["data"]["to"], "review")
        self.assertEqual(emitted[1]["data"]["exit_code"], 0)
        self.assertEqual(
            (result.log_directory / "program.stdout.log").read_text(), "verified\n"
        )

    def test_nonzero_exit_selects_failed(self) -> None:
        _, emitted = self.run_program("raise SystemExit(7)")

        self.assertEqual(emitted[1]["data"]["result"], "failed")
        self.assertEqual(emitted[1]["data"]["to"], "implementation")
        self.assertEqual(emitted[1]["data"]["exit_code"], 7)

    def test_start_failure_selects_error(self) -> None:
        _, emitted = self.run_program("", executable="missing-daik-test-command")

        self.assertEqual(emitted[1]["data"]["result"], "error")
        self.assertEqual(emitted[1]["data"]["to"], "await_human")
        self.assertIsNone(emitted[1]["data"]["exit_code"])
        self.assertIn("could not", emitted[1]["data"]["summary"])

    def test_secret_output_is_redacted_from_log_and_event(self) -> None:
        self.config["processes"]["broker"]["env"] = {
            "TOKEN": {"from_env": "PROGRAM_TEST_SECRET", "required": True}
        }
        with patch.dict(os.environ, {"PROGRAM_TEST_SECRET": "program-secret-marker"}):
            result, emitted = self.run_program(
                "import os; print(os.environ['TOKEN']); "
                "raise SystemExit(3)"
            )

        log = (result.log_directory / "program.stdout.log").read_text()
        self.assertNotIn("program-secret-marker", log)
        self.assertIn("[REDACTED]", log)
        self.assertNotIn("program-secret-marker", str(emitted))


if __name__ == "__main__":
    unittest.main()

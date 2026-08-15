from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


DAIK = Path(__file__).resolve().parents[1] / "daik"


class RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run_daik("site", "init", "--lang", "en", "--wet-run")
        (self.root / "AGENTS.md").write_text(
            "Read .agents/daik-workflow.yaml, .agents/daik-tracker.md, and "
            ".agents/daik-worker.md.\n",
            encoding="utf-8",
        )
        tracker = self.root / ".agents/daik-tracker.md"
        tracker.write_text(
            tracker.read_text(encoding="utf-8").replace(
                "<<DAIK:TRACKER_TOOL>>", "the configured test adapter"
            ),
            encoding="utf-8",
        )

    def run_daik(
        self, *arguments: str, expected_returncode: int = 0
    ) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["DAIK_STATE_HOME"] = str(self.root / "daik-state")
        result = subprocess.run(
            [sys.executable, str(DAIK), *arguments],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(
            result.returncode,
            expected_returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def configure_adapter(self, transition: str) -> None:
        adapter = self.root / "adapter.py"
        adapter.write_text(
            """\
import json
import os
import pathlib
import sys

invocation = json.load(sys.stdin)
pathlib.Path("received-invocation.json").write_text(
    json.dumps(invocation), encoding="utf-8"
)
print(json.dumps({
    "protocol_version": "daik.cli-wrapper-result.v1",
    "wrapper": {"name": "test"},
    "native_artifacts": [],
    "agent_result": {
        "transition": os.environ["TEST_TRANSITION"],
        "reason": "state work is ready",
        "evidence": ["adapter completed"],
        "summary": "implementation completed",
        "commits": ["abc123"],
        "validation": ["All relevant tests passed locally"],
        "decisions": [],
        "risks": [],
        "next_actions": ["run independent tests"],
    },
}))
""",
            encoding="utf-8",
        )
        wrapper = self.root / "adapter-wrapper.py"
        wrapper.write_text(
            """\
import os
import runpy
os.environ["TEST_TRANSITION"] = %s
runpy.run_path("adapter.py", run_name="__main__")
""" % json.dumps(transition),
            encoding="utf-8",
        )
        config = self.root / ".daik/config.yaml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                "  timeout_seconds: 3600\n",
                "  timeout_seconds: 30\n"
                "  command:\n"
                f"    - {json.dumps(sys.executable)}\n"
                f"    - {json.dumps(str(wrapper))}\n",
            ),
            encoding="utf-8",
        )

    def test_run_emits_started_completed_and_handoff_events(self) -> None:
        self.configure_adapter("ready_for_testing")

        result = self.run_daik(
            "work", "agent", "run", "github:backend#123", "--state", "implementation"
        )

        events = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(
            [item["kind"] for item in events],
            ["agent.started", "agent.completed", "handoff"],
        )
        self.assertEqual(events[1]["data"]["transition"], "ready_for_testing")
        self.assertEqual(events[1]["data"]["to"], "testing")
        self.assertEqual(events[2]["data"]["to_role"], "testing")
        self.assertEqual(
            events[2]["data"]["validation"], ["All relevant tests passed locally"]
        )
        invocation = json.loads(
            (self.root / "received-invocation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(invocation["issue"], "github:backend#123")
        self.assertIn("ready_for_testing", invocation["transitions"])
        self.assertEqual(invocation["protocol_version"], "daik.agent-invocation.v1")
        log_directory = Path(invocation["log_directory"])
        self.assertTrue(log_directory.is_dir())
        self.assertTrue((log_directory / "invocation.json").is_file())
        self.assertTrue((log_directory / "result.json").is_file())
        self.assertTrue((log_directory / "events.ndjson").is_file())

    def test_undeclared_transition_emits_failed_event(self) -> None:
        self.configure_adapter("skip_to_review")

        result = self.run_daik(
            "work",
            "agent",
            "run",
            "github:backend#123",
            "--state",
            "implementation",
            expected_returncode=1,
        )

        events = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([item["kind"] for item in events], ["agent.started", "agent.failed"])
        self.assertIn("undeclared transition", events[1]["data"]["error"])

    def test_final_state_cannot_be_run_as_an_agent(self) -> None:
        self.configure_adapter("ready_for_testing")

        result = self.run_daik(
            "work",
            "agent",
            "run",
            "github:backend#123",
            "--state",
            "completed",
            expected_returncode=2,
        )

        self.assertIn("workflow state is not an agent state", result.stderr)


if __name__ == "__main__":
    unittest.main()

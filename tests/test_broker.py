from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from daiklib.broker import pending_agent_completion, pending_program_completion
from daiklib.workspaces import event


DAIK = Path(__file__).resolve().parents[1] / "daik"


class BrokerTests(unittest.TestCase):
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
                "<<DAIK:TRACKER_TOOL>>", "the configured test joint"
            ),
            encoding="utf-8",
        )
        self.repo = self.root / "backend"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"], cwd=self.repo, check=True
        )
        (self.repo / "README.md").write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=self.repo, check=True)
        self.make_joint()
        self.make_wrapper()
        config = self.root / ".agents/daik-config.yaml"
        config.write_text(
            config.read_text(encoding="utf-8")
            .replace(
                "repositories:\n",
                "repositories:\n  backend:\n    path: backend\n    base: main\n",
            )
            .replace(
                "  timeout_seconds: 3600\n",
                "  timeout_seconds: 30\n"
                "  command:\n"
                f"    - {json.dumps(sys.executable)}\n"
                f"    - {json.dumps(str(self.wrapper))}\n",
            )
            .replace(
                "  joint_timeout_seconds: 30\n",
                "  joint_timeout_seconds: 30\n"
                "  joint:\n"
                f"    - {json.dumps(sys.executable)}\n"
                f"    - {json.dumps(str(self.joint))}\n",
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=environment,
        )
        self.assertEqual(
            result.returncode,
            expected_returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def make_joint(self) -> None:
        self.joint = self.root / "joint.py"
        self.joint.write_text(
            """\
import json
from pathlib import Path
import sys

request = json.load(sys.stdin)
store = Path("tracker-state.json")
state = json.loads(store.read_text()) if store.exists() else {
    "control_version": 0, "events": [], "status": "ready", "claimed": False
}
if request["operation"] == "issue.read_control":
    response = {"protocol_version": "daik.tracker-joint-result.v1", "status": "ok",
                "control_version": str(state["control_version"]), "events": state["events"]}
elif request["operation"] == "issue.commit_control":
    if request["expected_control_version"] != str(state["control_version"]):
        response = {"protocol_version": "daik.tracker-joint-result.v1",
                    "status": "conflict", "message": "stale control version"}
    else:
        state["events"].extend(request["events"])
        if request.get("status") is not None:
            state["status"] = request["status"]
        if request.get("claim"):
            state["claimed"] = True
        if request.get("close_reason") is not None:
            state["close_reason"] = request["close_reason"]
        state["control_version"] += 1
        store.write_text(json.dumps(state))
        response = {"protocol_version": "daik.tracker-joint-result.v1", "status": "ok",
                    "control_version": str(state["control_version"])}
else:
    response = {"protocol_version": "daik.tracker-joint-result.v1", "status": "error",
                "message": "unsupported operation"}
print(json.dumps(response))
""",
            encoding="utf-8",
        )

    def make_wrapper(self) -> None:
        self.wrapper = self.root / "wrapper.py"
        self.wrapper.write_text(
            """\
import json
import sys

invocation = json.load(sys.stdin)
transitions = {
    "implementation": "ready_for_testing",
    "testing": "tests_passed",
    "review": "approved",
    "pull_request": "published",
}
transition = transitions[invocation["state"]]
print(json.dumps({
    "protocol_version": "daik.cli-wrapper-result.v1",
    "wrapper": {"name": "test"},
    "native_artifacts": [],
    "agent_result": {
        "transition": transition, "reason": "done", "evidence": ["verified"],
        "summary": "state completed", "commits": [], "validation": [],
        "decisions": [], "risks": [], "next_actions": []
    }
}))
""",
            encoding="utf-8",
        )

    def test_runs_issue_to_successful_final_state(self) -> None:
        result = self.run_daik("work", "run", "github:backend#123")

        lines = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(lines[-1]["state"], "completed")
        tracker = json.loads((self.root / "tracker-state.json").read_text())
        self.assertTrue(tracker["claimed"])
        self.assertEqual(tracker["status"], "completed")
        self.assertEqual(tracker["close_reason"], "completed")
        kinds = [item["kind"] for item in tracker["events"]]
        self.assertEqual(kinds.count("workflow.transitioned"), 4)
        self.assertIn("workflow.started", kinds)
        self.assertIn("workflow.finished", kinds)
        self.assertTrue((self.root / "workspaces").is_dir())

    def test_completed_issue_is_not_run_again(self) -> None:
        self.run_daik("work", "run", "github:backend#123")
        first = json.loads((self.root / "tracker-state.json").read_text())

        result = self.run_daik("work", "run", "github:backend#123")

        second = json.loads((self.root / "tracker-state.json").read_text())
        self.assertEqual(first, second)
        self.assertEqual(json.loads(result.stdout)["state"], "completed")

    def test_runs_program_state_without_invoking_an_agent(self) -> None:
        workflow = self.root / ".agents/daik-workflow.yaml"
        content = workflow.read_text(encoding="utf-8")
        start = content.index("  testing:\n")
        end = content.index("\n  review:\n", start)
        program_state = f"""  testing:
    type: program
    command:
      - {json.dumps(sys.executable)}
      - -c
      - print('program verified')
    repository: backend
    timeout_seconds: 30
    transitions:
      succeeded:
        to: review
      failed:
        to: implementation
      error:
        to: await_human
"""
        workflow.write_text(content[:start] + program_state + content[end:], encoding="utf-8")

        result = self.run_daik("work", "run", "github:backend#123")

        self.assertEqual(json.loads(result.stdout.splitlines()[-1])["state"], "completed")
        tracker = json.loads((self.root / "tracker-state.json").read_text())
        program_events = [
            item for item in tracker["events"] if item["kind"].startswith("program.")
        ]
        self.assertEqual([item["kind"] for item in program_events], [
            "program.started", "program.completed"
        ])
        self.assertEqual(program_events[1]["data"]["result"], "succeeded")
        testing_agents = [
            item for item in tracker["events"]
            if item["kind"] == "agent.started" and item["data"]["state"] == "testing"
        ]
        self.assertEqual(testing_agents, [])

    def test_human_state_requires_declared_resume_transition(self) -> None:
        content = self.wrapper.read_text(encoding="utf-8")
        self.wrapper.write_text(
            content.replace('"implementation": "ready_for_testing"',
                            '"implementation": "needs_human"'),
            encoding="utf-8",
        )
        first = self.run_daik("work", "run", "github:backend#123")
        self.assertEqual(json.loads(first.stdout.splitlines()[-1])["state"], "await_human")

        invalid = self.run_daik(
            "work", "run", "github:backend#123", "--transition", "invented",
            expected_returncode=1,
        )
        self.assertIn("undeclared human transition", invalid.stderr)

        resumed = self.run_daik(
            "work", "run", "github:backend#123", "--transition", "cancel"
        )
        self.assertEqual(json.loads(resumed.stdout.splitlines()[-1])["state"], "cancelled")
        tracker = json.loads((self.root / "tracker-state.json").read_text())
        self.assertEqual(tracker["close_reason"], "cancelled")

    def test_finds_uncommitted_agent_completion_for_crash_recovery(self) -> None:
        issue = "github:backend#123"
        completion = event(
            "agent.completed",
            issue,
            {"state": "implementation", "transition": "ready_for_testing", "to": "testing"},
        )
        history = [event("workflow.started", issue, {"state": "implementation"}), completion]

        self.assertEqual(
            pending_agent_completion(issue, history, "implementation"), completion["data"]
        )
        history.append(
            event(
                "workflow.transitioned",
                issue,
                {"from": "implementation", "transition": "ready_for_testing", "to": "testing"},
            )
        )
        self.assertIsNone(pending_agent_completion(issue, history, "testing"))

    def test_finds_uncommitted_program_completion_for_crash_recovery(self) -> None:
        issue = "github:backend#123"
        completion = event(
            "program.completed",
            issue,
            {"state": "testing", "transition": "succeeded", "to": "review"},
        )
        history = [event("workflow.started", issue, {"state": "testing"}), completion]

        self.assertEqual(
            pending_program_completion(issue, history, "testing"), completion["data"]
        )
        history.append(
            event(
                "workflow.transitioned",
                issue,
                {"from": "testing", "transition": "succeeded", "to": "review"},
            )
        )
        self.assertIsNone(pending_program_completion(issue, history, "review"))


if __name__ == "__main__":
    unittest.main()

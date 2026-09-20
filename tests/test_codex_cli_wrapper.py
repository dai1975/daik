from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "cli-wrappers/codex/daik-cli-wrapper-codex"


class CodexCliWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.site = self.root / "site"
        self.site.mkdir()
        self.logs = self.root / "logs"
        self.logs.mkdir()
        self.codex_home = self.root / "codex-home"
        sessions = self.codex_home / "sessions/2026/08/12"
        sessions.mkdir(parents=True)
        self.thread_id = "0198f2a1-1111-7222-8333-123456789abc"
        self.session = sessions / f"rollout-{self.thread_id}.jsonl"
        self.session.write_text('{"session":true}\n', encoding="utf-8")
        self.fake_codex = self.root / "fake-codex.py"
        self.fake_codex.write_text(
            """\
#!/usr/bin/env python3
import json
from pathlib import Path
import sys

arguments = sys.argv[1:]
if arguments[0] != "exec" or "--json" not in arguments or arguments[-1] != "-":
    raise SystemExit(20)
output = Path(arguments[arguments.index("--output-last-message") + 1])
schema = Path(arguments[arguments.index("--output-schema") + 1])
json.loads(schema.read_text(encoding="utf-8"))
prompt = sys.stdin.read()
(output.parent / "received-prompt.txt").write_text(prompt, encoding="utf-8")
result = {
    "transition": "ready_for_testing",
    "reason": "implementation is complete",
    "evidence": ["tests added"],
    "summary": "implemented the issue",
    "commits": ["abc123"],
    "validation": ["All pytest tests passed"],
    "decisions": [],
    "risks": [],
    "next_actions": ["run independent tests"],
}
output.write_text(json.dumps(result), encoding="utf-8")
print(json.dumps({"type": "thread.started", "thread_id": %s}))
print(json.dumps({"type": "turn.completed", "usage": {}}))
""" % json.dumps(self.thread_id),
            encoding="utf-8",
        )
        self.fake_codex.chmod(0o700)

    def invocation(self) -> dict[str, object]:
        return {
            "protocol_version": "daik.agent-invocation.v1",
            "invocation_id": "invocation-1",
            "issue": "github:backend#123",
            "state": "implementation",
            "site_root": str(self.site),
            "log_directory": str(self.logs),
            "profile": {
                "name": "implementer",
                "role": "implementation",
                "instructions": "Implement the requested change.",
            },
            "task": "Implement and test the issue.",
            "context": {
                "site_instructions": "AGENTS.md",
                "worker_policy": ".agents/daik-worker.md",
            },
            "transitions": {
                "ready_for_testing": {
                    "to": "testing",
                    "when": "Implementation is complete.",
                }
            },
            "wrapper_options": {
                "executable": str(self.fake_codex),
                "sandbox": "workspace-write",
            },
        }

    def test_translates_invocation_and_reports_native_session(self) -> None:
        environment = dict(os.environ)
        environment["CODEX_HOME"] = str(self.codex_home)

        result = subprocess.run(
            [sys.executable, str(WRAPPER)],
            input=json.dumps(self.invocation()),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response["protocol_version"], "daik.cli-wrapper-result.v1")
        self.assertEqual(response["agent_result"]["transition"], "ready_for_testing")
        self.assertEqual(response["wrapper"]["thread_id"], self.thread_id)
        self.assertEqual(response["native_artifacts"][0]["path"], str(self.session))
        prompt = (self.logs / "received-prompt.txt").read_text(encoding="utf-8")
        self.assertIn("Current state: implementation", prompt)
        self.assertIn("Do not change claim, workflow state", prompt)
        events = (self.logs / "codex-events.jsonl").read_text(encoding="utf-8")
        self.assertIn(self.thread_id, events)

    def test_rejects_unknown_protocol(self) -> None:
        invocation = self.invocation()
        invocation["protocol_version"] = "example.invalid"

        result = subprocess.run(
            [sys.executable, str(WRAPPER)],
            input=json.dumps(invocation),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("protocol_version", result.stderr)


if __name__ == "__main__":
    unittest.main()

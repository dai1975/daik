from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


WRAPPER = (
    Path(__file__).resolve().parents[1]
    / "tracker-wrappers/github/daik-tracker-wrapper-github-gh"
)


class GitHubTrackerWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "state.json"
        self.state.write_text(
            json.dumps(
                {
                    "login": "alice",
                    "labels": ["daik:ready"],
                    "issues": {
                        "1": {
                            "number": 1,
                            "state": "OPEN",
                            "labels": [{"name": "daik:ready"}],
                            "assignees": [],
                            "blockedBy": [],
                            "comments": [],
                        }
                    },
                    "calls": [],
                }
            ),
            encoding="utf-8",
        )
        self.gh = self.root / "gh"
        self.gh.write_text(
            """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

path = Path(os.environ["FAKE_GH_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
state["calls"].append(args)

def value(flag):
    return args[args.index(flag) + 1]

result = None
if args[:2] == ["repo", "view"]:
    result = {"nameWithOwner": "owner/backend"}
elif args[:2] == ["api", "user"]:
    result = {"login": state["login"]}
elif args[:2] == ["issue", "list"]:
    result = list(state["issues"].values())
elif args[:2] == ["issue", "view"]:
    result = state["issues"][args[2]]
elif args[:2] == ["label", "list"]:
    result = [{"name": name} for name in state["labels"]]
elif args[:2] == ["label", "create"]:
    if args[2] not in state["labels"]:
        state["labels"].append(args[2])
elif args[:2] == ["issue", "comment"]:
    state["issues"][args[2]]["comments"].append({"body": value("--body")})
elif args[:2] == ["issue", "edit"]:
    issue = state["issues"][args[2]]
    labels = {item["name"] for item in issue["labels"]}
    index = 3
    while index < len(args):
        flag = args[index]
        if flag == "--repo":
            index += 2
        elif flag == "--add-label":
            labels.add(args[index + 1]); index += 2
        elif flag == "--remove-label":
            labels.discard(args[index + 1]); index += 2
        elif flag == "--add-assignee":
            issue["assignees"] = [{"login": state["login"]}]; index += 2
        else:
            raise SystemExit("unknown edit argument: " + flag)
    issue["labels"] = [{"name": name} for name in sorted(labels)]
elif args[:2] == ["issue", "close"]:
    state["issues"][args[2]]["state"] = "CLOSED"
else:
    raise SystemExit("unsupported fake gh call: " + repr(args))

path.write_text(json.dumps(state))
if result is not None:
    print(json.dumps(result))
""",
            encoding="utf-8",
        )
        self.gh.chmod(0o755)

    def invoke(
        self, request: dict[str, object], repository_path: bool = False
    ) -> dict[str, object]:
        environment = dict(os.environ)
        environment["FAKE_GH_STATE"] = str(self.state)
        repository_arguments = ["--repository", "backend=owner/backend"]
        if repository_path:
            checkout = self.root / "backend"
            checkout.mkdir(exist_ok=True)
            repository_arguments = ["--repository-path", f"backend={checkout}"]
        result = subprocess.run(
            [
                sys.executable,
                str(WRAPPER),
                *repository_arguments,
                "--required-label",
                "daik:ready",
                "--gh",
                str(self.gh),
            ],
            input=json.dumps(request),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def request(self, operation: str, **values: object) -> dict[str, object]:
        return {
            "protocol_version": "daik.tracker-wrapper.v1",
            "operation": operation,
            **values,
        }

    def test_lists_ready_work(self) -> None:
        result = self.invoke(
            self.request("work.list_ready", limit=2, exclude=[]), repository_path=True
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["issues"], ["github:backend#1"])

    def test_commits_events_claim_and_status_with_stale_version_detection(self) -> None:
        snapshot = self.invoke(
            self.request("issue.read_control", issue="github:backend#1")
        )
        event = {
            "schema": "daik.issue-event.v1",
            "kind": "workflow.started",
            "issue": "github:backend#1",
            "timestamp": "2026-08-15T00:00:00Z",
            "data": {"state": "implementation"},
        }
        committed = self.invoke(
            self.request(
                "issue.commit_control",
                issue="github:backend#1",
                expected_control_version=snapshot["control_version"],
                events=[event],
                status="implementation",
                claim=True,
            )
        )

        self.assertEqual(committed["status"], "ok")
        state = json.loads(self.state.read_text())
        issue = state["issues"]["1"]
        self.assertEqual(issue["assignees"], [{"login": "alice"}])
        labels = {item["name"] for item in issue["labels"]}
        self.assertIn("daik:running", labels)
        self.assertIn("daik:status:implementation", labels)
        self.assertNotIn("daik:ready", labels)
        self.assertIn("<!-- daik:issue-event:v1 -->", issue["comments"][0]["body"])
        refreshed = self.invoke(
            self.request("issue.read_control", issue="github:backend#1")
        )
        self.assertEqual(refreshed["events"], [event])

        stale = self.invoke(
            self.request(
                "issue.commit_control",
                issue="github:backend#1",
                expected_control_version=snapshot["control_version"],
                events=[event],
            )
        )
        self.assertEqual(stale["status"], "conflict")
        state = json.loads(self.state.read_text())
        self.assertEqual(len(state["issues"]["1"]["comments"]), 1)

    def test_rejects_claim_owned_by_another_actor(self) -> None:
        state = json.loads(self.state.read_text())
        state["issues"]["1"]["assignees"] = [{"login": "bob"}]
        self.state.write_text(json.dumps(state), encoding="utf-8")
        snapshot = self.invoke(
            self.request("issue.read_control", issue="github:backend#1")
        )

        result = self.invoke(
            self.request(
                "issue.commit_control",
                issue="github:backend#1",
                expected_control_version=snapshot["control_version"],
                events=[],
                claim=True,
            )
        )

        self.assertEqual(result["status"], "conflict")

    def test_closes_with_portable_reason_and_reason_label(self) -> None:
        snapshot = self.invoke(
            self.request("issue.read_control", issue="github:backend#1")
        )

        result = self.invoke(
            self.request(
                "issue.commit_control",
                issue="github:backend#1",
                expected_control_version=snapshot["control_version"],
                events=[],
                close_reason="cancelled",
            )
        )

        self.assertEqual(result["status"], "ok")
        state = json.loads(self.state.read_text())
        issue = state["issues"]["1"]
        self.assertEqual(issue["state"], "CLOSED")
        self.assertIn(
            "daik:close-reason:cancelled",
            {item["name"] for item in issue["labels"]},
        )
        close_calls = [call for call in state["calls"] if call[:2] == ["issue", "close"]]
        self.assertIn("not planned", close_calls[0])


if __name__ == "__main__":
    unittest.main()

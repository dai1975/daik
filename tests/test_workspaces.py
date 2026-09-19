from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


DAIK = Path(__file__).resolve().parents[1] / "daik"


class WorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run_daik("site", "init", "--wet-run")
        repository = self.root / "backend"
        repository.mkdir()
        self.run_command("git", "init", str(repository))
        self.run_command("git", "-C", str(repository), "config", "user.name", "Test")
        self.run_command("git", "-C", str(repository), "config", "user.email", "test@example.test")
        (repository / "README.md").write_text("backend\n", encoding="utf-8")
        self.run_command("git", "-C", str(repository), "add", "README.md")
        self.run_command("git", "-C", str(repository), "commit", "-m", "initial")
        self.run_command("git", "-C", str(repository), "branch", "-M", "main")
        config = self.root / ".daik/config.yaml"
        content = config.read_text(encoding="utf-8")
        content = content.replace(
            "repositories:\n\n",
            "repositories:\n  backend:\n    path: backend\n    base: main\n\n",
            1,
        )
        config.write_text(content, encoding="utf-8")

    def run_command(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(arguments, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return result

    def run_daik(
        self, *arguments: str, expected_returncode: int = 0
    ) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["DAIK_GH_TOKEN"] = "test-token"
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

    def test_workspace_lifecycle_emits_events_without_runtime_metadata(self) -> None:
        created = json.loads(self.run_daik("work", "workspace", "create", "backend#123").stdout)

        self.assertEqual(created["schema"], "daik.issue-event.v1")
        self.assertEqual(created["kind"], "workspace.prepared")
        record = created["data"]["repositories"][0]
        worktree = self.root / record["worktree"]
        self.assertTrue(worktree.is_dir())
        self.assertEqual(record["branch"], f"daik/{created['data']['workspace_id']}")
        self.assertFalse(any(path.name.endswith("workspace.json") for path in self.root.rglob("*")))

        reused = json.loads(self.run_daik("work", "workspace", "create", "backend#123").stdout)
        self.assertEqual(reused["kind"], "workspace.reused")

        shown = json.loads(self.run_daik("work", "workspace", "show", "backend#123").stdout)
        self.assertEqual(shown["data"]["repositories"][0]["head"], record["head"])

        event_path = self.root / "recorded-event.json"
        event_path.write_text(json.dumps(created), encoding="utf-8")
        reconciled = json.loads(
            self.run_daik(
                "work", "workspace", "reconcile", "backend#123", "--event", str(event_path)
            ).stdout
        )
        self.assertTrue(reconciled["data"]["compatible"])

        listing = json.loads(self.run_daik("work", "workspace", "list").stdout)
        self.assertEqual(listing[0]["workspace_id"], created["data"]["workspace_id"])

        preview = json.loads(self.run_daik("work", "workspace", "remove", "backend#123").stdout)
        self.assertEqual(preview["kind"], "workspace.remove-preview")
        self.assertTrue(worktree.exists())

        removed = json.loads(
            self.run_daik("work", "workspace", "remove", "backend#123", "--wet-run").stdout
        )
        self.assertEqual(removed["kind"], "workspace.removed")
        self.assertFalse(worktree.exists())
        branch = self.run_command(
            "git", "-C", str(self.root / "backend"), "branch", "--list", record["branch"]
        )
        self.assertIn(record["branch"], branch.stdout)

    def test_handoff_event_is_structured(self) -> None:
        result = self.run_daik(
            "work",
            "handoff",
            "create",
            "backend#123",
            "--from",
            "implementation",
            "--to",
            "review",
            "--phase",
            "review",
            "--summary",
            "Implementation complete",
            "--commit",
            "abc1234",
            "--validation",
            "All pytest tests passed",
            "--risk",
            "Windows is untested",
            "--next-action",
            "Review retry boundaries",
        )
        value = json.loads(result.stdout)
        self.assertEqual(value["kind"], "handoff")
        self.assertEqual(value["data"]["to_role"], "review")
        self.assertEqual(value["data"]["validation"], ["All pytest tests passed"])

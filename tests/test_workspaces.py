from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
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
        self.run_command(
            "git", "-C", str(repository), "remote", "add", "upstream",
            "https://example.test/backend.git",
        )
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
        self,
        *arguments: str,
        expected_returncode: int = 0,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command_environment = dict(os.environ)
        if environment:
            command_environment.update(environment)
        command_environment["DAIK_GH_TOKEN"] = "test-token"
        result = subprocess.run(
            [sys.executable, str(DAIK), *arguments],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
            env=command_environment,
        )
        self.assertEqual(
            result.returncode,
            expected_returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def test_clone_remote_name_ignores_ambient_default(self) -> None:
        home = self.root / "home"
        home.mkdir()
        (home / ".gitconfig").write_text(
            "[clone]\n\tdefaultRemoteName = local\n",
            encoding="utf-8",
        )

        created = json.loads(
            self.run_daik(
                "work",
                "workspace",
                "create",
                "backend#custom-clone-remote",
                environment={"HOME": str(home)},
            ).stdout
        )

        record = created["data"]["repositories"][0]
        self.assertEqual(record["remote"], "upstream")
        self.assertEqual(record["remote_url"], "https://example.test/backend.git")

    def test_remote_credentials_are_preserved_in_clone_but_omitted_from_event(self) -> None:
        source = self.root / "backend"
        credential = "unregistered-user:unregistered-token"
        remote_url = f"https://{credential}@example.test/backend.git?access=private#fragment"
        self.run_command(
            "git", "-C", str(source), "remote", "set-url", "upstream", remote_url
        )

        result = self.run_daik("work", "workspace", "create", "backend#credential")
        created = json.loads(result.stdout)
        record = created["data"]["repositories"][0]
        clone = self.root / record["path"]

        actual = self.run_command(
            "git", "-C", str(clone), "remote", "get-url", "upstream"
        ).stdout.strip()
        self.assertEqual(actual, remote_url)
        self.assertEqual(record["remote_url"], "https://example.test/backend.git")
        self.assertNotIn(credential, result.stdout)
        self.assertNotIn("access=private", result.stdout)

    def test_configured_secret_in_remote_is_not_replaced_operationally(self) -> None:
        source = self.root / "backend"
        remote_url = "https://test-token@example.test/backend.git"
        self.run_command(
            "git", "-C", str(source), "remote", "set-url", "upstream", remote_url
        )

        result = self.run_daik("work", "workspace", "create", "backend#configured-secret")
        created = json.loads(result.stdout)
        clone = self.root / created["data"]["repositories"][0]["path"]

        actual = self.run_command(
            "git", "-C", str(clone), "remote", "get-url", "upstream"
        ).stdout.strip()
        self.assertEqual(actual, remote_url)
        self.assertNotIn("test-token", result.stdout)
        self.assertNotIn("[REDACTED]", actual)

    def test_workspace_lifecycle_emits_events_without_runtime_metadata(self) -> None:
        created = json.loads(self.run_daik("work", "workspace", "create", "backend#123").stdout)

        self.assertEqual(created["schema"], "daik.issue-event.v1")
        self.assertEqual(created["kind"], "workspace.prepared")
        record = created["data"]["repositories"][0]
        clone = self.root / record["path"]
        self.assertTrue((clone / ".git").is_dir())
        self.assertEqual(record["branch"], f"daik/{created['data']['workspace_id']}")
        self.assertEqual(record["remote"], "upstream")
        self.assertEqual(record["remote_url"], "https://example.test/backend.git")
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
        self.assertTrue(clone.exists())

        removed = json.loads(
            self.run_daik("work", "workspace", "remove", "backend#123", "--wet-run").stdout
        )
        self.assertEqual(removed["kind"], "workspace.removed")
        self.assertFalse(clone.exists())
        self.assertTrue((self.root / "backend" / ".git").is_dir())

    def test_clone_is_independent_and_excludes_working_tree_changes(self) -> None:
        source = self.root / "backend"
        (source / "README.md").write_text("dirty\n", encoding="utf-8")
        (source / "untracked.txt").write_text("private\n", encoding="utf-8")

        created = json.loads(self.run_daik("work", "workspace", "create", "backend#456").stdout)
        clone = self.root / created["data"]["repositories"][0]["path"]

        self.assertEqual((clone / "README.md").read_text(encoding="utf-8"), "backend\n")
        self.assertFalse((clone / "untracked.txt").exists())
        head = created["data"]["repositories"][0]["head"]
        source_object = source / ".git" / "objects" / head[:2] / head[2:]
        clone_object = clone / ".git" / "objects" / head[:2] / head[2:]
        self.assertTrue(source_object.is_file())
        self.assertTrue(clone_object.is_file())
        self.assertNotEqual(source_object.stat().st_ino, clone_object.stat().st_ino)
        (clone / "clone.txt").write_text("writable\n", encoding="utf-8")
        self.run_command("git", "-C", str(clone), "add", "clone.txt")
        self.run_command("git", "-C", str(clone), "commit", "-m", "clone commit")

    def test_source_remote_rules_are_diagnostic(self) -> None:
        source = self.root / "backend"
        self.run_command("git", "-C", str(source), "remote", "remove", "upstream")
        result = self.run_daik(
            "work", "workspace", "create", "backend#remote", expected_returncode=2
        )
        self.assertIn("must have exactly one remote; found 0", result.stderr)

        self.run_command(
            "git", "-C", str(source), "remote", "add", "origin",
            "https://example.test/backend.git",
        )
        self.run_command(
            "git", "-C", str(source), "remote", "add", "mirror",
            "https://example.test/mirror.git",
        )
        result = self.run_daik(
            "work", "workspace", "create", "backend#remotes", expected_returncode=2
        )
        self.assertIn("must have exactly one remote; found 2", result.stderr)

        self.run_command("git", "-C", str(source), "remote", "remove", "mirror")
        self.run_command(
            "git", "-C", str(source), "remote", "set-url", "--push", "origin",
            "ssh://git@example.test/backend.git",
        )
        result = self.run_daik(
            "work", "workspace", "create", "backend#push-url", expected_returncode=2
        )
        self.assertIn("different fetch and push URLs", result.stderr)

    def test_reuse_rejects_non_clone_and_changed_remote(self) -> None:
        created = json.loads(self.run_daik("work", "workspace", "create", "backend#reuse").stdout)
        clone = self.root / created["data"]["repositories"][0]["path"]
        self.run_command(
            "git", "-C", str(clone), "remote", "set-url", "upstream",
            "https://example.test/other.git",
        )
        result = self.run_daik(
            "work", "workspace", "create", "backend#reuse", expected_returncode=2
        )
        self.assertIn("remote is", result.stderr)

        shutil.rmtree(clone / ".git")
        (clone / ".git").write_text("gitdir: /tmp/shared\n", encoding="utf-8")
        result = self.run_daik(
            "work", "workspace", "show", "backend#reuse", expected_returncode=2
        )
        self.assertIn("no independent .git directory", result.stderr)

    def test_lifecycle_rejects_external_git_metadata_and_object_storage(self) -> None:
        issue = "backend#linked-metadata"
        created = json.loads(self.run_daik("work", "workspace", "create", issue).stdout)
        clone = self.root / created["data"]["repositories"][0]["path"]
        external_git = self.root / "external-git"
        (clone / ".git").rename(external_git)
        (clone / ".git").symlink_to(external_git, target_is_directory=True)

        commands = (("create", issue), ("show", issue), ("remove", issue, "--wet-run"))
        for command in commands:
            result = self.run_daik("work", "workspace", *command, expected_returncode=2)
            self.assertIn("no independent .git directory", result.stderr)
        self.assertTrue(external_git.is_dir())

        (clone / ".git").unlink()
        external_git.rename(clone / ".git")
        alternates = clone / ".git" / "objects" / "info" / "alternates"
        alternates.write_text(str(self.root / "backend" / ".git" / "objects") + "\n")
        result = self.run_daik(
            "work", "workspace", "show", issue, expected_returncode=2
        )
        self.assertIn("uses Git object alternates", result.stderr)

    def test_lifecycle_rejects_repository_and_workspace_symlink_escape(self) -> None:
        issue = "backend#linked-repository"
        created = json.loads(self.run_daik("work", "workspace", "create", issue).stdout)
        clone = self.root / created["data"]["repositories"][0]["path"]
        workspace = clone.parent
        external_clone = self.root / "external-clone"
        clone.rename(external_clone)
        clone.symlink_to(external_clone, target_is_directory=True)

        commands = (("create", issue), ("show", issue), ("remove", issue, "--wet-run"))
        for command in commands:
            result = self.run_daik("work", "workspace", *command, expected_returncode=2)
            self.assertIn("escapes its Issue workspace", result.stderr)
        self.assertTrue((external_clone / ".git").is_dir())

        clone.unlink()
        workspace.rmdir()
        external_workspace = self.root / "external-workspace"
        external_workspace.mkdir()
        (external_workspace / "backend").symlink_to(external_clone, target_is_directory=True)
        workspace.symlink_to(external_workspace, target_is_directory=True)
        for command in commands:
            result = self.run_daik("work", "workspace", *command, expected_returncode=2)
            self.assertIn("escapes its Issue workspace", result.stderr)
        self.assertTrue((external_clone / ".git").is_dir())

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

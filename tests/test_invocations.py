from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from daiklib.invocations import (
    InvocationError,
    create_log_directory,
    link_native_artifacts,
    state_root,
)


class InvocationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.site = self.root / "my-site"
        self.site.mkdir()

    def test_state_root_precedence(self) -> None:
        self.assertEqual(
            state_root(
                {
                    "DAIK_STATE_HOME": "/private/daik",
                    "XDG_STATE_HOME": "/state",
                    "HOME": "/home/user",
                }
            ),
            Path("/private/daik"),
        )
        self.assertEqual(
            state_root({"XDG_STATE_HOME": "/state", "HOME": "/home/user"}),
            Path("/state/daik"),
        )
        self.assertEqual(
            state_root({"HOME": "/home/user"}), Path("/home/user/.local/state/daik")
        )

    def test_creates_private_issue_and_invocation_directory(self) -> None:
        state = self.root / "state"
        with patch.dict(os.environ, {"DAIK_STATE_HOME": str(state)}):
            invocation_id, directory = create_log_directory(
                self.site, "github:backend#123"
            )

        self.assertIn("github-backend-123", str(directory))
        self.assertIn(invocation_id, directory.name)
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)

    def test_links_only_current_user_native_session(self) -> None:
        logs = self.root / "logs"
        logs.mkdir()
        session = self.root / "session.jsonl"
        session.write_text("{}\n", encoding="utf-8")

        records = link_native_artifacts(
            logs,
            [{"type": "session", "id": "thread-1", "path": str(session)}],
        )

        self.assertEqual(records[0]["status"], "linked")
        self.assertEqual((logs / "native-session").resolve(), session)
        self.assertTrue((logs / "native-session.json").is_file())

    def test_rejects_symlinked_state_root(self) -> None:
        target = self.root / "target"
        target.mkdir()
        linked = self.root / "linked-state"
        linked.symlink_to(target, target_is_directory=True)
        with patch.dict(os.environ, {"DAIK_STATE_HOME": str(linked)}):
            with self.assertRaises(InvocationError):
                create_log_directory(self.site, "issue-1")

    def test_rejects_symlink_inside_state_tree(self) -> None:
        state = self.root / "state"
        state.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (state / "sites").symlink_to(outside, target_is_directory=True)
        with patch.dict(os.environ, {"DAIK_STATE_HOME": str(state)}):
            with self.assertRaises(InvocationError):
                create_log_directory(self.site, "issue-1")


if __name__ == "__main__":
    unittest.main()

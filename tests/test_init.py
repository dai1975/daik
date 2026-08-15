from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


DAIK = Path(__file__).resolve().parents[1] / "daik"


class InitTests(unittest.TestCase):
    def make_workspace(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        return root

    def run_daik(
        self, root: Path, *arguments: str, expected_returncode: int = 0
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(DAIK), *arguments],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            expected_returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def test_init_creates_contract_without_agents_md(self) -> None:
        root = self.make_workspace()

        result = self.run_daik(root, "site", "init", "--wet-run")

        self.assertIn("Not modified: AGENTS.md", result.stdout)
        self.assertFalse((root / "AGENTS.md").exists())
        self.assertTrue((root / ".daik/daik-AGENTS.md.template").is_file())
        self.assertTrue((root / ".daik/AGENTS.md").is_file())
        self.assertEqual((root / ".daik/.ignore").read_text(encoding="utf-8"), "*\n")
        self.assertTrue((root / ".agents/daik-workflow.yaml").is_file())
        self.assertTrue((root / ".daik/config.yaml").is_file())
        self.assertTrue((root / ".agents/daik-tracker.md").is_file())
        self.assertTrue((root / ".agents/daik-worker.md").is_file())
        self.assertTrue((root / ".agents/daik-agent-context-spec.md").is_file())
        self.assertTrue((root / ".daik/tracker-wrapper-spec.md").is_file())
        self.assertTrue((root / ".agents/daik-workflow-spec.md").is_file())
        self.assertTrue((root / ".agents/daik-issue-event-spec.md").is_file())
        self.assertTrue(
            (root / ".agents/skills/daik-check-github-issues-compatibility/SKILL.md").is_file()
        )
        self.assertTrue((root / "workspaces").is_dir())

        manifest = json.loads((root / ".daik/manifest.json").read_text())
        self.assertEqual(manifest["tool"], "daik")
        self.assertEqual(manifest["language"], "ja")
        self.assertEqual(
            [pack["id"] for pack in manifest["packs"]],
            [
                "daik.base.default",
                "daik.workflow.standard",
                "daik.tracker.github-issues",
            ],
        )
        self.assertEqual(
            manifest["files"][".agents/daik-workflow.yaml"]["owner"], "user"
        )
        workflow = (root / ".agents/daik-workflow.yaml").read_text(encoding="utf-8")
        tracker = (root / ".agents/daik-tracker.md").read_text(encoding="utf-8")
        self.assertIn('workflow_pack: "daik.workflow.standard"', workflow)
        self.assertIn('tracker_instructions: ".agents/daik-tracker.md"', workflow)
        self.assertIn("  artifact: workflow", workflow)
        self.assertIn("  user_action: review-and-customize", workflow)
        self.assertIn('    - "issue.set_phase"', workflow)
        self.assertIn("api_version: daik.dev/v1alpha1", workflow)
        self.assertIn("initial: implementation", workflow)
        self.assertIn("type: agent", workflow)
        self.assertIn("otherwise: true", workflow)
        self.assertNotIn("## GitHub Issues tracker mapping", workflow)
        self.assertIn('artifact: tracker', tracker)
        self.assertIn('tracker_pack: "daik.tracker.github-issues"', tracker)
        self.assertIn("## GitHub Issues tracker mapping", tracker)
        self.assertIn("<<DAIK:TRACKER_TOOL>>", tracker)
        agents = (root / ".daik/daik-AGENTS.md.template").read_text(encoding="utf-8")
        self.assertIn("<!-- DAIK:COPY:BEGIN -->", agents)
        self.assertIn("<!-- DAIK:COPY:END -->", agents)
        self.assertIn("<<DAIK:SITE_GUIDE>>", agents)
        self.assertIn(".agents/daik-issue-event-spec.md", agents)
        self.assertIn(".agents/daik-worker.md", agents)
        self.assertNotIn(".daik/config.yaml", agents)
        self.assertNotIn(".daik/tracker-wrapper-spec.md", agents)
        config = (root / ".daik/config.yaml").read_text(encoding="utf-8")
        self.assertIn("artifact: config", config)
        self.assertIn("workspace:\n  root: workspaces", config)
        self.assertIn("tracker:\n", config)
        self.assertIn("wrapper: github-gh", config)
        self.assertNotIn("adapter:", config)
        self.assertNotIn("command: gh", config)
        self.assertTrue((root / ".daik/github-issues-spec.md").is_file())
        self.assertTrue(
            (root / ".agents/skills/daik-check-github-issues-compatibility/SKILL.md").is_file()
        )
        self.assertLess(config.index("workspace:"), config.index("tracker:"))
        self.assertEqual(manifest["document"]["artifact"], "manifest")

    def test_repeated_init_preserves_user_files(self) -> None:
        root = self.make_workspace()
        self.run_daik(root, "site", "init", "--wet-run")
        workflow = root / ".agents/daik-workflow.yaml"
        workflow.write_text("custom workflow\n", encoding="utf-8")

        result = self.run_daik(root, "site", "init", "--wet-run")

        self.assertEqual(workflow.read_text(encoding="utf-8"), "custom workflow\n")
        self.assertIn("Kept: .agents/daik-workflow.yaml", result.stdout)
        manifest = json.loads((root / ".daik/manifest.json").read_text())
        self.assertEqual(
            manifest["files"][".agents/daik-workflow.yaml"]["state"], "modified"
        )

    def test_existing_agents_md_is_not_modified(self) -> None:
        root = self.make_workspace()
        agents = root / "AGENTS.md"
        agents.write_text("user instructions\n", encoding="utf-8")

        self.run_daik(root, "site", "init", "--wet-run")

        self.assertEqual(agents.read_text(encoding="utf-8"), "user instructions\n")

    def test_default_preview_writes_nothing(self) -> None:
        root = self.make_workspace()

        result = self.run_daik(root, "site", "init")

        self.assertIn("Would create: .agents/daik-workflow.yaml", result.stdout)
        self.assertIn("Preview only", result.stdout)
        self.assertFalse((root / ".agents").exists())
        self.assertFalse((root / "workspaces").exists())

    def test_wet_run_creates_missing_site_root(self) -> None:
        parent = self.make_workspace()
        root = parent / "new" / "site"

        result = self.run_daik(
            parent, "site", "init", "--root", str(root), "--wet-run"
        )

        self.assertIn(f"Created site root: {root}", result.stdout)
        self.assertTrue((root / ".daik/config.yaml").is_file())
        self.assertTrue((root / ".daik/manifest.json").is_file())
        self.assertTrue((root / "workspaces").is_dir())

    def test_preview_does_not_create_missing_site_root(self) -> None:
        parent = self.make_workspace()
        root = parent / "new" / "site"

        result = self.run_daik(parent, "site", "init", "--root", str(root))

        self.assertIn(f"Would create site root: {root}", result.stdout)
        self.assertIn("Preview only", result.stdout)
        self.assertFalse(root.exists())

    def test_init_rejects_file_as_site_root(self) -> None:
        parent = self.make_workspace()
        root = parent / "site"
        root.write_text("not a directory\n", encoding="utf-8")

        result = self.run_daik(
            parent,
            "site",
            "init",
            "--root",
            str(root),
            "--wet-run",
            expected_returncode=2,
        )

        self.assertIn("workspace root is not a directory", result.stderr)

    def test_workspaces_path_must_be_a_directory(self) -> None:
        root = self.make_workspace()
        (root / "workspaces").write_text("not a directory\n", encoding="utf-8")

        result = self.run_daik(root, "site", "init", "--wet-run", expected_returncode=2)

        self.assertIn("expected a directory", result.stderr)
        self.assertFalse((root / ".agents").exists())

    def test_flat_init_command_is_not_accepted(self) -> None:
        root = self.make_workspace()

        result = self.run_daik(root, "init", expected_returncode=2)

        self.assertIn("invalid choice", result.stderr)

    def test_no_arguments_prints_top_level_help(self) -> None:
        root = self.make_workspace()

        result = self.run_daik(root)

        self.assertIn(
            "usage: daik [-h] [--version] <subcommand> ...\n"
            "       daik site <init | packs | validate | doctor> ...",
            result.stdout,
        )
        self.assertIn("<subcommand>", result.stdout)
        self.assertIn("site", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_symlinked_agents_directory_is_rejected(self) -> None:
        root = self.make_workspace()
        outside = root / "outside"
        outside.mkdir()
        (root / ".agents").symlink_to(outside, target_is_directory=True)

        result = self.run_daik(root, "site", "init", "--wet-run", expected_returncode=2)

        self.assertIn("contains a symlink", result.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlinked_daik_directory_is_rejected(self) -> None:
        root = self.make_workspace()
        outside = root / "outside"
        outside.mkdir()
        (root / ".daik").symlink_to(outside, target_is_directory=True)

        result = self.run_daik(root, "site", "init", "--wet-run", expected_returncode=2)

        self.assertIn("contains a symlink", result.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_english_pack_variants_are_selected(self) -> None:
        root = self.make_workspace()

        self.run_daik(root, "site", "init", "--lang", "en", "--wet-run")

        workflow = (root / ".agents/daik-workflow.yaml").read_text(encoding="utf-8")
        tracker = (root / ".agents/daik-tracker.md").read_text(encoding="utf-8")
        agents = (root / ".daik/daik-AGENTS.md.template").read_text(encoding="utf-8")
        self.assertIn("Implement the smallest change", workflow)
        self.assertIn("## GitHub Issues tracker mapping", tracker)
        self.assertIn("## Issue-driven development", agents)

    def test_reinit_with_different_selection_is_rejected(self) -> None:
        root = self.make_workspace()
        self.run_daik(root, "site", "init", "--lang", "ja", "--wet-run")
        workflow = root / ".agents/daik-workflow.yaml"
        original = workflow.read_text(encoding="utf-8")

        result = self.run_daik(
            root, "site", "init", "--lang", "en", "--wet-run", expected_returncode=2
        )

        self.assertIn("different language or pack selection", result.stderr)
        self.assertEqual(workflow.read_text(encoding="utf-8"), original)

    def test_packs_command_lists_builtin_packs(self) -> None:
        root = self.make_workspace()

        result = self.run_daik(root, "site", "packs")

        self.assertIn("daik.workflow.standard", result.stdout)
        self.assertIn("daik.tracker.github-issues", result.stdout)
        self.assertIn("daik.tracker.beads", result.stdout)

    def test_beads_tracker_pack_is_deployed(self) -> None:
        root = self.make_workspace()

        self.run_daik(root, "site", "init", "--tracker", "beads", "--wet-run")

        config = (root / ".daik/config.yaml").read_text(encoding="utf-8")
        tracker = (root / ".agents/daik-tracker.md").read_text(encoding="utf-8")
        self.assertIn("pack: daik.tracker.beads", config)
        self.assertNotIn("adapter:", config)
        self.assertNotIn("command: bd", config)
        self.assertIn("## Beads tracker mapping", tracker)
        self.assertIn("issue.add_dependency", tracker)
        self.assertIn("<<DAIK:TRACKER_TOOL>>", tracker)
        self.assertTrue((root / ".daik/beads-spec.md").is_file())
        self.assertTrue(
            (root / ".agents/skills/daik-check-beads-compatibility/SKILL.md").is_file()
        )
        (root / "AGENTS.md").write_text(
            "Read .agents/daik-workflow.yaml, .agents/daik-tracker.md, and "
            ".agents/daik-worker.md.\n",
            encoding="utf-8",
        )
        tracker_path = root / ".agents/daik-tracker.md"
        tracker_path.write_text(
            tracker.replace("<<DAIK:TRACKER_TOOL>>", "Use the configured Beads MCP server."),
            encoding="utf-8",
        )
        result = self.run_daik(root, "site", "validate")
        self.assertIn("Validation passed", result.stdout)
        doctor = self.run_daik(root, "site", "doctor")
        self.assertIn("daik-check-beads-compatibility skill", doctor.stdout)
        self.assertIn("Doctor passed", doctor.stdout)

    def test_external_pack_is_discovered_and_capabilities_are_checked(self) -> None:
        root = self.make_workspace()
        external = root / "external-packs/custom"
        (external / "workflow").mkdir(parents=True)
        (external / "workflow/ja.md").write_text("# Custom\n", encoding="utf-8")
        (external / "workflow/en.md").write_text("# Custom\n", encoding="utf-8")
        (external / "pack.yaml").write_text(
            """\
schema_version: 1
id: example.workflow.custom
key: custom
kind: workflow
version: 1
name:
  ja: カスタム
  en: Custom
languages:
  - ja
  - en
requires:
  - issue.unsupported
contributions:
  workflow:
    ja: workflow/ja.md
    en: workflow/en.md
""",
            encoding="utf-8",
        )

        listing = self.run_daik(
            root, "site", "packs", "--template-dir", str(root / "external-packs")
        )
        self.assertIn("example.workflow.custom", listing.stdout)

        result = self.run_daik(
            root,
            "site",
            "init",
            "--workflow",
            "custom",
            "--template-dir",
            str(root / "external-packs"),
            expected_returncode=2,
        )
        self.assertIn("issue.unsupported", result.stderr)
        self.assertFalse((root / ".agents").exists())


if __name__ == "__main__":
    unittest.main()

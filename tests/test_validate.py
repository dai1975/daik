from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


DAIK = Path(__file__).resolve().parents[1] / "daik"


class ValidateTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run_daik("site", "init", "--lang", "en", "--wet-run")

    def run_daik(
        self,
        *arguments: str,
        expected_returncode: int = 0,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
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

    def complete_user_setup(self) -> None:
        (self.root / "AGENTS.md").write_text(
            "Read .agents/daik-workflow.md and .agents/daik-tracker.md.\n",
            encoding="utf-8",
        )
        tracker = self.root / ".agents/daik-tracker.md"
        tracker.write_text(
            tracker.read_text(encoding="utf-8").replace(
                "<<DAIK:TRACKER_TOOL>>", "the configured GitHub tool"
            ),
            encoding="utf-8",
        )

    def test_fresh_site_reports_required_user_setup(self) -> None:
        result = self.run_daik("site", "validate", expected_returncode=1)

        self.assertIn("ERROR AGENTS.md: required file is missing", result.stdout)
        self.assertIn("unresolved <<DAIK:...>> placeholder", result.stdout)
        self.assertIn("Validation failed: 2 error(s)", result.stdout)

    def test_completed_site_passes_with_customization_info(self) -> None:
        self.complete_user_setup()

        result = self.run_daik("site", "validate")

        self.assertIn("Validation passed: 0 error(s)", result.stdout)
        self.assertIn("INFO .agents/daik-tracker.md", result.stdout)

    def test_invalid_positive_integer_is_an_error(self) -> None:
        self.complete_user_setup()
        config = self.root / ".agents/daik-config.yaml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                "max_concurrent_agents: 1", "max_concurrent_agents: 0"
            ),
            encoding="utf-8",
        )

        result = self.run_daik("site", "validate", expected_returncode=1)

        self.assertIn("agent.max_concurrent_agents must be a positive integer", result.stdout)

    def test_tracker_must_provide_every_workflow_action(self) -> None:
        self.complete_user_setup()
        tracker = self.root / ".agents/daik-tracker.md"
        tracker.write_text(
            tracker.read_text(encoding="utf-8").replace(
                '    - "issue.complete"\n', ""
            ),
            encoding="utf-8",
        )

        result = self.run_daik("site", "validate", expected_returncode=1)

        self.assertIn("does not provide workflow actions: issue.complete", result.stdout)

    def test_modified_daik_owned_file_is_an_error(self) -> None:
        self.complete_user_setup()
        spec = self.root / ".agents/daik-workflow-spec.md"
        spec.write_text(spec.read_text(encoding="utf-8") + "modified\n", encoding="utf-8")

        result = self.run_daik("site", "validate", expected_returncode=1)

        self.assertIn("daik-owned file differs from its recorded template", result.stdout)

    def test_manifest_pack_must_match_documents(self) -> None:
        self.complete_user_setup()
        manifest_path = self.root / ".daik/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["packs"][1]["id"] = "example.workflow.other"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = self.run_daik("site", "validate", expected_returncode=1)

        self.assertIn("selected workflow pack does not match workflow_pack", result.stdout)

    def test_doctor_checks_local_runtime(self) -> None:
        self.complete_user_setup()
        (self.root / "backend/.git").mkdir(parents=True)

        result = self.run_daik("site", "doctor")

        self.assertIn("INFO git: git version", result.stdout)
        self.assertIn("INFO workspaces: workspace directory is writable", result.stdout)
        self.assertIn("found 1 Git checkout(s) outside workspaces", result.stdout)
        self.assertIn("Doctor passed: 0 error(s)", result.stdout)

    def test_doctor_fails_when_git_is_unavailable(self) -> None:
        self.complete_user_setup()
        environment = dict(os.environ)
        environment["PATH"] = ""

        result = self.run_daik(
            "site", "doctor", expected_returncode=1, environment=environment
        )

        self.assertIn("ERROR git: executable was not found on PATH", result.stdout)
        self.assertIn("Doctor failed:", result.stdout)


if __name__ == "__main__":
    unittest.main()

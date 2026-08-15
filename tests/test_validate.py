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
            "Read .agents/daik-workflow.yaml, .agents/daik-tracker.md, and "
            ".agents/daik-worker.md.\n",
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
        config = self.root / ".daik/config.yaml"
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

    def test_workflow_transition_target_must_exist(self) -> None:
        self.complete_user_setup()
        workflow = self.root / ".agents/daik-workflow.yaml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8").replace(
                "to: testing", "to: missing_state", 1
            ),
            encoding="utf-8",
        )

        result = self.run_daik("site", "validate", expected_returncode=1)

        self.assertIn(
            "states.implementation.transitions.ready_for_testing.to must name an existing state",
            result.stdout,
        )

    def test_workflow_requires_one_fallback_per_non_final_state(self) -> None:
        self.complete_user_setup()
        workflow = self.root / ".agents/daik-workflow.yaml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8").replace(
                "        otherwise: true", "        when: fallback", 1
            ),
            encoding="utf-8",
        )

        result = self.run_daik("site", "validate", expected_returncode=1)

        self.assertIn(
            "states.implementation.transitions must contain exactly one otherwise fallback",
            result.stdout,
        )

    def test_workflow_rejects_unreachable_state(self) -> None:
        self.complete_user_setup()
        workflow = self.root / ".agents/daik-workflow.yaml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8")
            + "\n  abandoned:\n    type: final\n    outcome: failure\n",
            encoding="utf-8",
        )

        result = self.run_daik("site", "validate", expected_returncode=1)

        self.assertIn("state 'abandoned' is unreachable from initial", result.stdout)

    def test_workflow_accepts_deterministic_program_state(self) -> None:
        self.complete_user_setup()
        config = self.root / ".daik/config.yaml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                "repositories:\n",
                "repositories:\n  backend:\n    path: backend\n    base: main\n",
            ),
            encoding="utf-8",
        )
        workflow = self.root / ".agents/daik-workflow.yaml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8")
            .replace("initial: implementation", "initial: automated_test")
            + """
  automated_test:
    type: program
    command:
      - make
      - test
    repository: backend
    timeout_seconds: 900
    transitions:
      succeeded:
        to: implementation
      failed:
        to: failed
      error:
        to: await_human
""",
            encoding="utf-8",
        )

        result = self.run_daik("site", "validate")

        self.assertIn("Validation passed: 0 error(s)", result.stdout)

    def test_program_transition_rejects_natural_language_selector(self) -> None:
        self.complete_user_setup()
        workflow = self.root / ".agents/daik-workflow.yaml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8")
            + """
  automated_test:
    type: program
    command:
      - make
      - test
    repository: backend
    timeout_seconds: 900
    transitions:
      succeeded:
        to: completed
        when: tests passed
      failed:
        to: failed
      error:
        to: await_human
""",
            encoding="utf-8",
        )

        result = self.run_daik("site", "validate", expected_returncode=1)

        self.assertIn(
            "states.automated_test.transitions.succeeded may contain only to",
            result.stdout,
        )

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

    def test_doctor_rejects_gh_without_issue_dependency_support(self) -> None:
        self.complete_user_setup()
        binary_directory = self.root / "bin"
        binary_directory.mkdir()
        gh = binary_directory / "gh"
        gh.write_text("#!/bin/sh\necho 'gh version 2.93.0 (test)'\n", encoding="utf-8")
        gh.chmod(0o755)
        environment = dict(os.environ)
        environment["PATH"] = str(binary_directory) + os.pathsep + environment["PATH"]

        result = self.run_daik(
            "site", "doctor", expected_returncode=1, environment=environment
        )

        self.assertIn(
            "ERROR tracker: github-gh requires gh >= 2.94.0 for Issue dependencies; found 2.93.0",
            result.stdout,
        )

    def test_doctor_accepts_minimum_github_gh_version(self) -> None:
        self.complete_user_setup()
        binary_directory = self.root / "bin"
        binary_directory.mkdir()
        gh = binary_directory / "gh"
        gh.write_text("#!/bin/sh\necho 'gh version 2.94.0 (test)'\n", encoding="utf-8")
        gh.chmod(0o755)
        environment = dict(os.environ)
        environment["PATH"] = str(binary_directory) + os.pathsep + environment["PATH"]

        result = self.run_daik("site", "doctor", environment=environment)

        self.assertIn(
            "INFO tracker: built-in GitHub gh tracker wrapper is configured (gh 2.94.0)",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from daiklib.broker_runs import BrokerRunLog, broker_run_status
from daiklib.workspaces import event


class BrokerRunLogTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.site = self.root / "site"
        self.site.mkdir()
        self.environment = patch.dict(
            os.environ, {"DAIK_STATE_HOME": str(self.root / "state")}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_records_and_summarizes_a_broker_run(self) -> None:
        log = BrokerRunLog(self.site, "watch", 2)
        log.record("work.submitted", issue="issue-1")
        log.record(
            "work.event",
            issue="issue-1",
            event=event(
                "workflow.transitioned",
                "issue-1",
                {"from": "implementation", "transition": "done", "to": "review"},
            ),
        )
        log.record("work.stopped", issue="issue-1", state="completed", attempts=1)
        log.finish("completed")

        status = broker_run_status(self.site, log.run_id)

        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["mode"], "watch")
        self.assertEqual(status["concurrency"], 2)
        self.assertEqual(status["work"][0]["status"], "stopped")
        self.assertEqual(status["work"][0]["state"], "completed")
        self.assertIn("broker-runs", log.directory.parts)
        self.assertEqual(log.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(log.metadata_path.stat().st_mode & 0o777, 0o600)

    def test_latest_selects_the_newest_run(self) -> None:
        first = BrokerRunLog(self.site, "run", 1)
        first.finish("completed")
        second = BrokerRunLog(self.site, "watch", 1)
        second.finish("failed")

        status = broker_run_status(self.site)

        self.assertEqual(status["broker_run_id"], second.run_id)
        self.assertEqual(status["status"], "failed")

    def test_reports_abandoned_running_process_as_interrupted(self) -> None:
        log = BrokerRunLog(self.site, "watch", 1)
        metadata = json.loads(log.metadata_path.read_text(encoding="utf-8"))
        metadata["pid"] = 2_147_483_647
        log.metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        status = broker_run_status(self.site, log.run_id)

        self.assertEqual(status["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import threading
import time
import unittest

from daiklib.broker import BrokerConflict, BrokerError
from daiklib.joints import JointError
from daiklib.watch import WorkWatcher


class FakeJoint:
    def __init__(self, issues: list[str], failures: int = 0):
        self.issues = issues
        self.failures = failures
        self.calls = 0

    def list_ready(self, limit: int, exclude=()) -> list[str]:
        self.calls += 1
        if self.calls <= self.failures:
            raise JointError("temporary tracker failure")
        return [issue for issue in self.issues if issue not in exclude][:limit]


class ConcurrentBroker:
    def __init__(self, owner: "BrokerFactory"):
        self.owner = owner

    def run(self, issue, emit):
        with self.owner.lock:
            self.owner.active += 1
            self.owner.max_active = max(self.owner.max_active, self.owner.active)
        time.sleep(0.05)
        with self.owner.lock:
            self.owner.active -= 1
        return "completed"


class BrokerFactory:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def __call__(self):
        return ConcurrentBroker(self)


class RetryingBroker:
    def __init__(self, failures: int, conflict: bool = False):
        self.failures = failures
        self.conflict = conflict
        self.calls = 0

    def run(self, issue, emit):
        self.calls += 1
        if self.conflict:
            raise BrokerConflict("claim lost")
        if self.calls <= self.failures:
            raise BrokerError("temporary failure")
        return "completed"


class WorkWatcherTests(unittest.TestCase):
    def watcher(self, factory, joint, emitted, sleeps, concurrency=1, retries=2):
        return WorkWatcher(
            factory,
            joint,
            concurrency=concurrency,
            interval_ms=1,
            max_retries=retries,
            retry_initial_ms=10,
            retry_max_ms=15,
            emit=emitted.append,
            sleep=sleeps.append,
        )

    def test_once_runs_ready_work_concurrently(self) -> None:
        factory = BrokerFactory()
        joint = FakeJoint(["issue-1", "issue-2"])
        emitted = []

        result = self.watcher(factory, joint, emitted, [], concurrency=2).run(once=True)

        self.assertEqual(result, 0)
        self.assertEqual(joint.calls, 1)
        self.assertEqual(factory.max_active, 2)
        self.assertEqual(
            [item["data"]["issue"] for item in emitted if item["kind"] == "work.submitted"],
            ["issue-1", "issue-2"],
        )

    def test_retries_work_with_capped_exponential_backoff(self) -> None:
        broker = RetryingBroker(failures=2)
        sleeps = []
        emitted = []

        result = self.watcher(lambda: broker, FakeJoint(["issue-1"]), emitted, sleeps).run(
            once=True
        )

        self.assertEqual(result, 0)
        self.assertEqual(broker.calls, 3)
        self.assertEqual(sleeps, [0.01, 0.015])
        self.assertEqual(
            [item["kind"] for item in emitted].count("work.retrying"), 2
        )

    def test_claim_conflict_is_skipped_without_retry(self) -> None:
        broker = RetryingBroker(failures=0, conflict=True)
        emitted = []

        result = self.watcher(lambda: broker, FakeJoint(["issue-1"]), emitted, []).run(
            once=True
        )

        self.assertEqual(result, 0)
        self.assertEqual(broker.calls, 1)
        self.assertIn("work.skipped", [item["kind"] for item in emitted])

    def test_exhausted_work_retry_makes_once_fail(self) -> None:
        broker = RetryingBroker(failures=3)
        emitted = []

        result = self.watcher(
            lambda: broker, FakeJoint(["issue-1"]), emitted, [], retries=1
        ).run(once=True)

        self.assertEqual(result, 1)
        self.assertEqual(broker.calls, 2)
        failed = [item for item in emitted if item["kind"] == "work.failed"]
        self.assertEqual(failed[0]["data"]["attempts"], 2)

    def test_retries_polling_before_a_successful_cycle(self) -> None:
        sleeps = []
        emitted = []
        joint = FakeJoint([], failures=1)

        result = self.watcher(BrokerFactory(), joint, emitted, sleeps).run(once=True)

        self.assertEqual(result, 0)
        self.assertEqual(joint.calls, 2)
        self.assertEqual(sleeps, [0.01])
        self.assertIn("poll.retrying", [item["kind"] for item in emitted])


if __name__ == "__main__":
    unittest.main()

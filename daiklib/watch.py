"""Polling and concurrent execution for the Agent Work Broker."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
import threading
import time
from typing import Any, Callable

from daiklib.broker import Broker, BrokerConflict, BrokerError
from daiklib.tracker_wrapper import TrackerWrapperError, TrackerWrapper


class WatchError(RuntimeError):
    pass


class WorkWatcher:
    def __init__(
        self,
        broker_factory: Callable[[], Broker],
        wrapper: TrackerWrapper,
        concurrency: int,
        interval_ms: int,
        max_retries: int,
        retry_initial_ms: int,
        retry_max_ms: int,
        emit: Callable[[dict[str, Any]], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.broker_factory = broker_factory
        self.wrapper = wrapper
        self.concurrency = concurrency
        self.interval = interval_ms / 1000
        self.max_retries = max_retries
        self.retry_initial = retry_initial_ms / 1000
        self.retry_max = retry_max_ms / 1000
        self.emit = emit
        self.sleep = sleep
        self._emit_lock = threading.Lock()

    def _record(self, kind: str, **data: Any) -> None:
        if self.emit:
            with self._emit_lock:
                self.emit({"schema": "daik.broker-event.v1", "kind": kind, "data": data})

    def _run_issue(self, issue: str) -> str:
        attempt = 0
        while True:
            try:
                state = self.broker_factory().run(
                    issue, lambda item: self._record("work.event", issue=issue, event=item)
                )
            except BrokerConflict as error:
                self._record("work.skipped", issue=issue, reason=str(error))
                return "skipped"
            except BrokerError as error:
                if attempt >= self.max_retries:
                    self._record(
                        "work.failed", issue=issue, attempts=attempt + 1, error=str(error)
                    )
                    return "failed"
                delay = min(self.retry_initial * (2 ** min(attempt, 62)), self.retry_max)
                attempt += 1
                self._record(
                    "work.retrying",
                    issue=issue,
                    attempt=attempt,
                    delay_ms=round(delay * 1000),
                    error=str(error),
                )
                self.sleep(delay)
                continue
            self._record("work.stopped", issue=issue, state=state, attempts=attempt + 1)
            return state

    def run(self, once: bool = False) -> int:
        active: dict[Future[str], str] = {}
        active_issues: set[str] = set()
        suppressed_issues: set[str] = set()
        poll_failures = 0
        failed = False
        polled_once = False
        with ThreadPoolExecutor(
            max_workers=self.concurrency, thread_name_prefix="daik-broker"
        ) as executor:
            while True:
                finished = [future for future in active if future.done()]
                for future in finished:
                    issue = active.pop(future)
                    active_issues.remove(issue)
                    try:
                        work_result = future.result()
                        if work_result in {"failed", "skipped"}:
                            suppressed_issues.add(issue)
                            failed = work_result == "failed" or failed
                    except Exception as error:  # Defensive boundary around worker threads.
                        failed = True
                        self._record("work.failed", issue=issue, attempts=1, error=str(error))

                if once and polled_once:
                    if active:
                        wait(active, return_when=FIRST_COMPLETED)
                        continue
                    return 1 if failed else 0

                available = self.concurrency - len(active)
                if available > 0:
                    try:
                        issues = self.wrapper.list_ready(
                            available, sorted(active_issues | suppressed_issues)
                        )
                    except TrackerWrapperError as error:
                        if poll_failures >= self.max_retries:
                            raise WatchError(
                                f"ready-work polling failed after {poll_failures + 1} attempts: {error}"
                            ) from error
                        delay = min(
                            self.retry_initial * (2 ** min(poll_failures, 62)),
                            self.retry_max,
                        )
                        poll_failures += 1
                        self._record(
                            "poll.retrying",
                            attempt=poll_failures,
                            delay_ms=round(delay * 1000),
                            error=str(error),
                        )
                        self.sleep(delay)
                        continue
                    poll_failures = 0
                    polled_once = True
                    for issue in issues:
                        if issue in active_issues:
                            continue
                        self._record("work.submitted", issue=issue)
                        active[executor.submit(self._run_issue, issue)] = issue
                        active_issues.add(issue)

                if once:
                    if active:
                        wait(active, return_when=FIRST_COMPLETED)
                        continue
                    return 1 if failed else 0
                if active and len(active) >= self.concurrency:
                    wait(active, timeout=self.interval, return_when=FIRST_COMPLETED)
                else:
                    self.sleep(self.interval)

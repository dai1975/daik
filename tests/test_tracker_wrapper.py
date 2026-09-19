from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

from daiklib.tracker_wrapper import TrackerWrapper, TrackerWrapperError


class TrackerWrapperRedactionTests(unittest.TestCase):
    def test_secret_is_redacted_from_invalid_response_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            secret = "tracker-secret-marker"
            wrapper = TrackerWrapper(
                Path(temporary),
                [
                    sys.executable,
                    "-c",
                    "import os,sys; print(os.environ['TOKEN'], file=sys.stderr)",
                ],
                environment={"TOKEN": secret},
                secrets=(secret,),
            )

            with self.assertRaises(TrackerWrapperError) as caught:
                wrapper.call("work.list_ready")

            self.assertNotIn(secret, str(caught.exception))
            self.assertIn("[REDACTED]", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

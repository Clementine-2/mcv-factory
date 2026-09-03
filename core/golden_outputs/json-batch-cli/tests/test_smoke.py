from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

import json_batch_cli


class SmokeTest(unittest.TestCase):
    def test_main_runs(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            json_batch_cli.main([])
        self.assertIn("Project scaffold ready", stream.getvalue())

    def test_version_is_defined(self) -> None:
        self.assertEqual(json_batch_cli.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()

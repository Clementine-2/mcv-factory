from __future__ import annotations

import unittest

import text_normalizer_lib


class LibrarySmokeTest(unittest.TestCase):
    def test_import_and_status(self) -> None:
        self.assertEqual(text_normalizer_lib.scaffold_status(), "text_normalizer_lib scaffold ready")

    def test_version(self) -> None:
        self.assertEqual(text_normalizer_lib.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()

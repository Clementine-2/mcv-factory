from __future__ import annotations

import unittest

from project_factory.tools import resolve_executable


class OwnedToolsTests(unittest.TestCase):
    def test_owned_uv_is_preferred_over_path(self) -> None:
        found = resolve_executable("uv")
        self.assertIsNotNone(found)
        self.assertIn("uv010", found.replace("\\", "/").casefold())

    def test_owned_npm_wrapper_is_portable(self) -> None:
        found = resolve_executable("npm")
        self.assertIsNotNone(found)
        self.assertIn("npm1092", found.replace("\\", "/").casefold())
        text = open(found, encoding="utf-8", errors="replace").read()
        self.assertIn("%~dp0", text)
        self.assertNotIn("D:\\10_Work", text)

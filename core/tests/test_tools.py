from __future__ import annotations

import unittest

from project_factory.tools import owned_provider_dirs, resolve_executable


class OwnedToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        # The owned toolchain (core/.tools: npm1092, uv010, …) is produced by
        # the installer build, not by a fresh clone. On CI / sparse checkouts
        # it is absent, so these installer-scenario tests skip themselves.
        if not owned_provider_dirs():
            self.skipTest("factory-owned toolchain (core/.tools) not present in this checkout")

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
        # The resolved wrapper must stay relocatable: it must not bake in any
        # absolute build-machine path. Use a neutral sentinel for the check.
        self.assertNotIn("C:\\BuildMachine", text)

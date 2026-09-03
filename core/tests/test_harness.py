from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from project_factory.harness import (
    HarnessError,
    default_harness_ids,
    load_harness_registry,
    materialize_harness_contracts,
    resolve_harnesses,
    verify_harness_contracts,
)


class HarnessRegistryTests(unittest.TestCase):
    def test_default_registry_declares_codex_and_claude_without_runtime_claim(self) -> None:
        registry = load_harness_registry()
        self.assertEqual(default_harness_ids(registry), ("codex", "claude"))
        self.assertEqual(registry["codex"].context_file, "AGENTS.md")
        self.assertEqual(registry["claude"].context_file, "CLAUDE.md")

    def test_unknown_harness_is_rejected(self) -> None:
        with self.assertRaisesRegex(HarnessError, "Unknown harness adapter"):
            resolve_harnesses(("does-not-exist",))


class HarnessMaterializationTests(unittest.TestCase):
    def test_context_files_are_byte_identical_to_canonical_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            specs = resolve_harnesses(("codex", "claude"))
            report = materialize_harness_contracts(root, "# Contract\n\nSame truth.\n", specs)
            canonical = (root / ".project/contract/agent-contract.md").read_bytes()
            self.assertEqual((root / "AGENTS.md").read_bytes(), canonical)
            self.assertEqual((root / "CLAUDE.md").read_bytes(), canonical)
            self.assertEqual(report["status"], "PARTIALLY_VERIFIED")
            self.assertFalse(any(claim["status"] == "VERIFIED" and claim["id"].endswith("-runtime") for claim in report["claims"]))

    def test_tampered_harness_context_fails_parity_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            specs = resolve_harnesses(("codex", "claude"))
            report = materialize_harness_contracts(root, "# Contract\n", specs)
            lock = {
                "canonical_contract": report["canonical_contract"],
                "adapters": report["adapters"],
            }
            (root / "CLAUDE.md").write_text("# Diverged\n", encoding="utf-8")
            checked = verify_harness_contracts(root, lock)
            self.assertEqual(checked["status"], "FAILED")
            self.assertTrue(any("claude" in failure.casefold() for failure in checked["failures"]))

    def test_single_harness_materializes_only_its_context_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            specs = resolve_harnesses(("codex",))
            report = materialize_harness_contracts(root, "# Contract\n", specs)
            self.assertTrue((root / "AGENTS.md").is_file())
            self.assertFalse((root / "CLAUDE.md").exists())
            self.assertEqual(set(report["adapters"]), {"codex"})


if __name__ == "__main__":
    unittest.main()

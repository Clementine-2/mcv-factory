from __future__ import annotations

import unittest

from project_factory.requirements_matrix import apply_matrix_overrides, build_requirement_matrix
from project_factory.semantic import run_semantic_intake


class RequirementMatrixTests(unittest.TestCase):
    def test_matrix_exposes_deterministic_intent_and_profile_preview(self) -> None:
        matrix = build_requirement_matrix("做一个 Python 命令行工具，不能覆盖原文件，要求性能好。")
        payload = matrix.to_dict()
        rows = {row["id"]: row for row in payload["rows"]}
        self.assertEqual(payload["readiness"], "USABLE")
        self.assertEqual(rows["work_products"]["value"], ["cli"])
        self.assertIn("python", rows["technology_required"]["value"])
        self.assertEqual(payload["profile"]["id"], "python-cli")

    def test_confirmed_overrides_are_revalidated_and_can_change_profile(self) -> None:
        matrix = build_requirement_matrix("Build a Python CLI.")
        adapter = apply_matrix_overrides(
            matrix,
            {
                "purpose": "Build a Python library for text normalization.",
                "work_products": ["library"],
                "technology_required": ["python"],
                "hard_constraints": ["Must never overwrite source files"],
                "targets": ["windows"],
            },
        )
        intake = run_semantic_intake("User-confirmed matrix", adapter)
        self.assertEqual(intake.validation.readiness_status, "USABLE")
        self.assertEqual(intake.blueprint["work_products"][0]["kind"], "library")
        self.assertEqual(intake.receipt["adapter"]["trust_class"], "user-confirmed")
        matrix2 = build_requirement_matrix("User-confirmed matrix", adapter)
        self.assertEqual(matrix2.profile["id"], "python-library")

    def test_matrix_never_bypasses_schema(self) -> None:
        matrix = build_requirement_matrix("Build a Python CLI.")
        adapter = apply_matrix_overrides(matrix, {"work_products": ["Bad Kind With Spaces"]})
        intake = run_semantic_intake("User-confirmed matrix", adapter)
        self.assertEqual(intake.validation.structure_status, "INVALID")


if __name__ == "__main__":
    unittest.main()

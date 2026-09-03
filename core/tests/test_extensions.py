from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
DECLARATIVE = ROOT / "fixtures" / "extensions" / "team-standard" / "extension.yaml"
TRUSTED = ROOT / "fixtures" / "extensions" / "trusted-lab" / "extension.yaml"

from project_factory.extensions import (
    ExtensionError,
    ExtensionRuntime,
    apply_extension_plan,
    assert_runtime_matches_lock,
    collect_extension_migration_targets,
    load_extension_manifest,
    load_extension_runtime,
    load_extension_set,
    materialize_extension_artifacts,
    plan_add_extension,
    plan_extension_state,
    verify_extension_receipt,
)
from project_factory.factory import generate_project, restore_verify_project_zip, write_project_manifest
from project_factory.ownership import (
    collect_managed_file_hashes,
    managed_paths_from_lock,
    write_factory_overlay_manifest,
)
from project_factory.registry import load_registry, select_profile
from project_factory.upgrade import apply_upgrade, plan_upgrade, rollback_upgrade


def apply_add(state: Path, manifest: Path, *, trust_code: bool = False) -> None:
    plan = plan_add_extension(state, manifest, trust_code=trust_code)
    apply_extension_plan(state, plan, confirm_plan_sha256=plan.plan_sha256)


def python_cli_blueprint() -> dict:
    return {
        "schema_version": "0.1",
        "project": {"purpose": "test extension profile"},
        "work_products": [{"kind": "cli"}],
        "technology": {"required": ["python"]},
    }


class ExtensionManifestTests(unittest.TestCase):
    def test_declarative_manifest_is_valid_and_code_free(self) -> None:
        manifest = load_extension_manifest(DECLARATIVE)
        self.assertEqual(manifest.mode, "declarative")
        self.assertIsNone(manifest.code)
        self.assertEqual(manifest.id, "team-standard")

    def test_declarative_extension_cannot_add_executable_provider(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(DECLARATIVE.parent, root / "ext")
            path = root / "ext" / "extension.yaml"
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            doc["contributes"]["registry"]["providers"] = [
                {
                    "id": "team-standard.bad-provider",
                    "version": "1",
                    "capability": "project_scaffolding",
                    "executable": "anything",
                }
            ]
            path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            with self.assertRaisesRegex(ExtensionError, "may not add executable Providers"):
                load_extension_manifest(path)

    def test_registry_ids_must_be_namespaced(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(DECLARATIVE.parent, root / "ext")
            path = root / "ext" / "extension.yaml"
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            doc["contributes"]["registry"]["profiles"][0]["id"] = "python-cli"
            path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            with self.assertRaisesRegex(ExtensionError, "must be namespaced"):
                load_extension_manifest(path)

    def test_artifact_source_cannot_escape_extension_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(DECLARATIVE.parent, root / "ext")
            (root / "outside.md").write_text("outside", encoding="utf-8")
            path = root / "ext" / "extension.yaml"
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            doc["contributes"]["project_artifacts"][0]["source"] = "../outside.md"
            path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            with self.assertRaises(ExtensionError):
                load_extension_manifest(path)


class ExtensionSetSafetyTests(unittest.TestCase):
    def test_trusted_code_requires_explicit_registration_trust(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "extensions.json"
            with self.assertRaisesRegex(ExtensionError, "explicit trust_code"):
                plan_add_extension(state, TRUSTED)

    def test_apply_requires_exact_plan_hash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "extensions.json"
            plan = plan_add_extension(state, DECLARATIVE)
            with self.assertRaisesRegex(ExtensionError, "confirmation hash"):
                apply_extension_plan(state, plan, confirm_plan_sha256="wrong")
            self.assertFalse(state.exists())

    def test_stale_extension_set_plan_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "extensions.json"
            plan = plan_add_extension(state, DECLARATIVE)
            state.write_text(json.dumps({"schema_version": "0.1", "factory_api": "1", "extensions": []}), encoding="utf-8")
            with self.assertRaisesRegex(ExtensionError, "changed after DryRun"):
                apply_extension_plan(state, plan, confirm_plan_sha256=plan.plan_sha256)

    def test_disable_and_remove_only_change_state_not_extension_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "extensions.json"
            apply_add(state, DECLARATIVE)
            source_hash = DECLARATIVE.read_bytes()
            disable = plan_extension_state(state, "team-standard", action="DISABLE")
            result = apply_extension_plan(state, disable, confirm_plan_sha256=disable.plan_sha256)
            self.assertFalse(load_extension_set(state)["extensions"][0]["enabled"])
            self.assertFalse(result["package_or_source_deleted"])
            enable = plan_extension_state(state, "team-standard", action="ENABLE")
            apply_extension_plan(state, enable, confirm_plan_sha256=enable.plan_sha256)
            remove = plan_extension_state(state, "team-standard", action="REMOVE")
            result = apply_extension_plan(state, remove, confirm_plan_sha256=remove.plan_sha256)
            self.assertEqual(load_extension_set(state)["extensions"], [])
            self.assertFalse(result["package_or_source_deleted"])
            self.assertEqual(DECLARATIVE.read_bytes(), source_hash)

    def test_manifest_mutation_after_registration_blocks_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(DECLARATIVE.parent, root / "ext")
            manifest = root / "ext" / "extension.yaml"
            state = root / "extensions.json"
            apply_add(state, manifest)
            manifest.write_text(manifest.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
            with self.assertRaisesRegex(ExtensionError, "changed after registration"):
                load_extension_runtime(state)

    def test_metadata_registration_does_not_load_trusted_code(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "extensions.json"
            with mock.patch("project_factory.extensions._load_entry_point") as loader:
                plan = plan_add_extension(state, TRUSTED, trust_code=True)
                apply_extension_plan(state, plan, confirm_plan_sha256=plan.plan_sha256)
                loader.assert_not_called()


class ExtensionRuntimeTests(unittest.TestCase):
    def test_declarative_profile_extends_registry_without_code_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "extensions.json"
            apply_add(state, DECLARATIVE)
            runtime = load_extension_runtime(state)
            registry = load_registry(extension_runtime=runtime)
            self.assertIn("team-standard.python-cli", registry.profiles)
            self.assertEqual(select_profile(python_cli_blueprint(), registry).id, "team-standard.python-cli")
            self.assertEqual(runtime.formula_adapters, {})

    def test_trusted_entry_point_loads_exact_distribution_and_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "extensions.json"
            apply_add(state, TRUSTED, trust_code=True)
            runtime = load_extension_runtime(state)
            self.assertIn("trusted-lab.audit-v1", runtime.formula_adapters)
            self.assertIn("trusted-lab.migration", runtime.migration_hooks)
            receipt = runtime.receipt()["extensions"][0]
            self.assertEqual(receipt["distribution"], "project-factory-trusted-lab")
            self.assertEqual(receipt["distribution_version"], "2.0.0")

    def test_same_version_trusted_code_drift_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(TRUSTED.parent, root / "ext")
            manifest = root / "ext" / "extension.yaml"
            state = root / "extensions.json"
            apply_add(state, manifest, trust_code=True)
            result = generate_project("做一个 Python CLI 工具。", "trusted-drift", root / "out", extension_set=state)
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            prior = lock["extensions"][0]["distribution_sha256"]
            code = root / "ext" / "plugin_site" / "trusted_lab_extension" / "__init__.py"
            code.write_text(code.read_text(encoding="utf-8") + "\n# same-version code drift\n", encoding="utf-8")
            runtime = load_extension_runtime(state)
            current = runtime.receipt()["extensions"][0]["distribution_sha256"]
            self.assertNotEqual(prior, current)
            with self.assertRaisesRegex(ExtensionError, "distribution_sha256 differs from Project Lock"):
                assert_runtime_matches_lock(runtime, lock["extensions"])
            with self.assertRaisesRegex(Exception, "distribution_sha256 differs from Project Lock"):
                restore_verify_project_zip(result.project_zip, extension_set=state)

    def test_wrong_distribution_version_blocks_before_code_load(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(TRUSTED.parent, root / "ext")
            manifest = root / "ext" / "extension.yaml"
            doc = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            doc["code"]["distribution_version"] = "9.9.9"
            manifest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            state = root / "extensions.json"
            apply_add(state, manifest, trust_code=True)
            with self.assertRaisesRegex(ExtensionError, "expected '9.9.9'"):
                load_extension_runtime(state)

    def test_code_migration_hook_cannot_escape_extension_namespace(self) -> None:
        runtime = ExtensionRuntime()
        runtime.extensions = ()
        runtime.migration_hooks["evil.migration"] = lambda *args: {"src/main.py": "bad"}
        # Synthetic locked extension makes the hook eligible.
        runtime.extension_versions = lambda: {"evil": "2.0.0"}  # type: ignore[method-assign]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ExtensionError, "outside its namespace"):
                collect_extension_migration_targets(
                    Path(td), {"extensions": [{"id": "evil", "version": "1.0.0"}]}, runtime
                )


class ExtensionGenerationTests(unittest.TestCase):
    def test_declarative_extension_generates_and_records_skill_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "extensions.json"
            apply_add(state, DECLARATIVE)
            result = generate_project("做一个 Python CLI 工具。", "declarative-cli", root / "out", extension_set=state)
            self.assertEqual(result.profile.profile_id, "team-standard.python-cli")
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["extensions"][0]["id"], "team-standard")
            skill = result.project_root / ".project/extensions/team-standard/skills/review.md"
            self.assertTrue(skill.is_file())
            contract = (result.project_root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn(".project/extensions/team-standard/skills/review.md", contract)
            self.assertEqual(restore_verify_project_zip(result.project_zip, extension_set=state)["status"], "VERIFIED")

    def test_extension_project_requires_matching_extension_set_for_factory_reverification(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "extensions.json"
            apply_add(state, DECLARATIVE)
            result = generate_project("做一个 Python CLI 工具。", "requires-ext", root / "out", extension_set=state)
            with self.assertRaisesRegex(Exception, "does not match Project Lock"):
                restore_verify_project_zip(result.project_zip)

    def test_trusted_extension_changes_profile_provider_and_formula_without_core_edit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "extensions.json"
            apply_add(state, TRUSTED, trust_code=True)
            result = generate_project("做一个 Python CLI 工具。", "trusted-cli", root / "out", extension_set=state)
            self.assertEqual(result.profile.profile_id, "trusted-lab.python-cli")
            self.assertEqual(result.provider.provider_id, "trusted-lab.uv")
            self.assertTrue(any("trusted-lab" in item for item in result.decision_record["trace"]))
            self.assertEqual(restore_verify_project_zip(result.project_zip, extension_set=state)["status"], "VERIFIED")

    def test_extension_artifact_tamper_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "extensions.json"
            apply_add(state, DECLARATIVE)
            runtime = load_extension_runtime(state)
            project = root / "project"
            project.mkdir()
            receipt = materialize_extension_artifacts(project, runtime)
            target = project / receipt["artifacts"][0]["path"]
            target.write_text("tampered", encoding="utf-8")
            self.assertEqual(verify_extension_receipt(project, receipt)["status"], "FAILED")


class ExtensionMigrationIntegrationTests(unittest.TestCase):
    def test_trusted_extension_version_migration_is_scoped_and_rollbackable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "extensions.json"
            apply_add(state, TRUSTED, trust_code=True)
            result = generate_project("做一个 Python CLI 工具。", "extension-migrate", root / "out", extension_set=state)
            project = result.project_root
            version_file = project / ".project/extensions/trusted-lab/version.txt"
            version_file.write_text("1.0.0\n", encoding="utf-8")
            receipt_path = project / ".project/extensions.lock.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["extensions"][0]["version"] = "1.0.0"
            for artifact in receipt["artifacts"]:
                if artifact["path"].endswith("/version.txt"):
                    from project_factory.extensions import sha256_file
                    artifact["sha256"] = sha256_file(version_file)
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            lock_path = project / "project.lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["extensions"][0]["version"] = "1.0.0"
            for artifact in lock["extension_artifacts"]:
                if artifact["path"].endswith("/version.txt"):
                    from project_factory.extensions import sha256_file
                    artifact["sha256"] = sha256_file(version_file)
            lock["managed_files"] = collect_managed_file_hashes(project, managed_paths_from_lock(lock))
            lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            write_factory_overlay_manifest(project, list(managed_paths_from_lock(lock)) + ["project.lock.json"])
            write_project_manifest(project)

            plan = plan_upgrade(project, extension_set=state)
            self.assertEqual(plan.status, "READY")
            ext_changes = [item for item in plan.changes if "trusted-lab" in item.path]
            self.assertEqual([item.path for item in ext_changes], [".project/extensions/trusted-lab/version.txt"])
            self.assertTrue(all(item.path.startswith(".project/extensions/trusted-lab/") for item in ext_changes))

            applied = apply_upgrade(project, confirm_plan_sha256=plan.plan_sha256, extension_set=state)
            self.assertEqual(version_file.read_text(encoding="utf-8"), "2.0.0\n")
            upgraded_lock = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertEqual(upgraded_lock["extensions"][0]["version"], "2.0.0")

            rolled = rollback_upgrade(
                project,
                Path(applied["rollback_bundle"]),
                confirm_bundle_sha256=applied["rollback_bundle_sha256"],
            )
            self.assertEqual(rolled["status"], "ROLLED_BACK")
            self.assertEqual(version_file.read_text(encoding="utf-8"), "1.0.0\n")


if __name__ == "__main__":
    unittest.main()

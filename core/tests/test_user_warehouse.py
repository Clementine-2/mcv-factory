from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from project_factory.generation import _load_user_scaffolds
from project_factory.registry import load_registry


class UserWarehouseTests(unittest.TestCase):
    def test_default_load_ignores_user_warehouse(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "profiles.yaml").write_text(
                yaml.safe_dump(
                    {
                        "schema_version": "0.1",
                        "profiles": [
                            {
                                "id": "user-should-not-load",
                                "version": "0.1",
                                "priority": 1,
                                "match": {"work_products_any": ["user-extra"]},
                                "capabilities": ["project_scaffolding"],
                                "provider_preferences": {"project_scaffolding": ["uv"]},
                                "scaffold_recipe": "uv-typer-app",
                                "verification_recipe": "python-cli",
                                "materialization": "minimal",
                            }
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"PROJECT_FACTORY_USER_WAREHOUSE": str(root), "PROJECT_FACTORY_LOAD_USER_WAREHOUSE": "0"}, clear=False):
                registry = load_registry()
            self.assertNotIn("user-should-not-load", registry.profiles)

    def test_flag_merges_user_profile_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "profiles.yaml").write_text(
                yaml.safe_dump(
                    {
                        "schema_version": "0.1",
                        "profiles": [
                            {
                                "id": "user-extra-cli",
                                "version": "0.1",
                                "priority": 1,
                                "match": {"work_products_any": ["user-extra-cli"]},
                                "capabilities": ["project_scaffolding"],
                                "provider_preferences": {"project_scaffolding": ["uv"]},
                                "scaffold_recipe": "uv-typer-app",
                                "verification_recipe": "python-cli",
                                "materialization": "minimal",
                            }
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            env = {
                "PROJECT_FACTORY_LOAD_USER_WAREHOUSE": "1",
                "PROJECT_FACTORY_USER_WAREHOUSE": str(root),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                registry = load_registry()
            self.assertIn("user-extra-cli", registry.profiles)
            self.assertIn("python-cli", registry.profiles)

    def test_bad_user_yaml_does_not_take_down_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "profiles.yaml").write_text("not: [valid: yaml: ::", encoding="utf-8")
            env = {
                "PROJECT_FACTORY_LOAD_USER_WAREHOUSE": "1",
                "PROJECT_FACTORY_USER_WAREHOUSE": str(root),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                registry = load_registry()
            self.assertIn("python-cli", registry.profiles)

    def test_user_plugin_scaffold_is_loaded_when_flag_on(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plugins = Path(temp) / "plugins"
            plugins.mkdir()
            (plugins / "demo.py").write_text(
                "SCAFFOLD_ID = 'user-demo-scaffold'\n"
                "def scaffold(*args, **kwargs):\n"
                "    return 'ok'\n",
                encoding="utf-8",
            )
            env = {
                "PROJECT_FACTORY_LOAD_USER_WAREHOUSE": "1",
                "PROJECT_FACTORY_USER_WAREHOUSE": str(temp),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                loaded = _load_user_scaffolds()
            self.assertIn("user-demo-scaffold", loaded)
            self.assertEqual(loaded["user-demo-scaffold"](), "ok")

    def test_user_plugin_not_loaded_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plugins = Path(temp) / "plugins"
            plugins.mkdir()
            (plugins / "demo.py").write_text(
                "SCAFFOLD_ID = 'user-demo-scaffold'\ndef scaffold(*args, **kwargs):\n    return 'ok'\n",
                encoding="utf-8",
            )
            env = {
                "PROJECT_FACTORY_LOAD_USER_WAREHOUSE": "0",
                "PROJECT_FACTORY_USER_WAREHOUSE": str(temp),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                loaded = _load_user_scaffolds()
            self.assertEqual(loaded, {})

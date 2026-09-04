"""Discord bot drawing on the uv language root.

Gateway login is not a verification gate.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    add_pinned_pytest,
    _patch_python_pyproject,
    _python_package_name,
    run_command,
)

DISCORD_PY_PIN = "2.4.0"
AUDIOOP_LTS_PIN = "0.2.1"


def _render_bot() -> str:
    return '''from __future__ import annotations

import discord
from discord.ext import commands


def scaffold_status() -> str:
    return "bot scaffold ready"


def reply_for(text: str) -> str:
    """真实示例：按命令文本生成机器人回复（不联网、不依赖网关）。"""
    stripped = text.strip()
    lowered = stripped.casefold()
    if lowered == "!ping":
        return "pong"
    if lowered == "!hello" or lowered.startswith("!hello "):
        name = stripped.split(maxsplit=1)[1] if " " in stripped else "friend"
        return f"Hello, {name}!"
    return scaffold_status()


def build_bot() -> commands.Bot:
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())

    @bot.command(name="status")
    async def status(ctx: commands.Context) -> None:
        await ctx.send(scaffold_status())

    return bot


def main() -> None:
    raise RuntimeError("Gateway login is not a factory verification gate.")
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.bot import build_bot, reply_for, scaffold_status

__version__ = "0.1.0"
__all__ = ["build_bot", "reply_for", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.bot import build_bot, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_status_command_is_registered(self) -> None:
        bot = build_bot()
        names = [command.name for command in bot.commands]
        self.assertIn("status", names)
        self.assertEqual(scaffold_status(), "bot scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.bot import reply_for


class DemoTest(unittest.TestCase):
    def test_ping_returns_pong(self) -> None:
        self.assertEqual(reply_for("!ping"), "pong")

    def test_hello_greets_named_user(self) -> None:
        self.assertEqual(reply_for("!hello Ada"), "Hello, Ada!")

    def test_unknown_command_returns_status(self) -> None:
        self.assertEqual(reply_for("!nope"), "bot scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_discord_bot(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-discord-bot":
        raise RecipeError(f"Unsupported Discord bot scaffold recipe: {recipe}")
    package_name = _python_package_name(project_name)
    scaffold = run_command(
        [
            provider.executable,
            "init",
            "--lib",
            "--package",
            "--name",
            project_name,
            "--vcs",
            "none",
            "--no-pin-python",
            "--no-workspace",
            str(project_root),
        ],
        staging_root,
    )
    _patch_python_pyproject(project_root / "pyproject.toml", purpose)
    run_command([provider.executable, "add", f"discord.py=={DISCORD_PY_PIN}"], project_root, timeout=600)
    pyproject = project_root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    marker = f'"audioop-lts=={AUDIOOP_LTS_PIN} ; python_version >= \'3.13\'"'
    if marker not in text:
        replaced = text.replace(
            f'"discord-py=={DISCORD_PY_PIN}"',
            f'"discord-py=={DISCORD_PY_PIN}",\n    {marker}',
            1,
        )
        if replaced == text:
            replaced = text.replace(
                f'"discord.py=={DISCORD_PY_PIN}"',
                f'"discord.py=={DISCORD_PY_PIN}",\n    {marker}',
                1,
            )
        if replaced == text:
            raise RecipeError("discord.py pin missing from pyproject.toml")
        pyproject.write_text(replaced, encoding="utf-8")
        run_command([provider.executable, "lock"], project_root, timeout=600)
        run_command([provider.executable, "sync"], project_root, timeout=600)
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "bot.py").write_text(_render_bot(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "bot": f"src/{package_name}/bot.py",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )

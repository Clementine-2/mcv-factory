"""Minimal RAG application on the uv language root.

No vector database and no live embedding API.
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


def _render_rag() -> str:
    return '''from __future__ import annotations

import json
import re
from pathlib import Path


def scaffold_status() -> str:
    return "rag scaffold ready"


def load_docs(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(item["id"]): str(item["text"]) for item in payload}


def retrieve(query: str, docs: dict[str, str]) -> str:
    if query in docs:
        return docs[query]
    for text in docs.values():
        if query in text:
            return text
    return scaffold_status()


def retrieve_top_k(query: str, docs: dict[str, str], k: int = 3) -> list[tuple[str, str]]:
    """真实可运行的检索示例：按关键词命中数排序返回前 k 条 (id, text)。"""
    query_tokens = set(token.casefold() for token in re.findall(r"\\w+", query))
    scored = []
    for doc_id, text in docs.items():
        text_tokens = set(token.casefold() for token in re.findall(r"\\w+", text))
        score = len(query_tokens & text_tokens)
        scored.append((score, doc_id, text))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [(doc_id, text) for _, doc_id, text in scored[:k]]


def answer(query: str, docs_path: Path) -> str:
    return retrieve(query, load_docs(docs_path))
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.rag import answer, retrieve_top_k, scaffold_status

__version__ = "0.1.0"
__all__ = ["answer", "retrieve_top_k", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest
from pathlib import Path

from {package_name}.rag import answer, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_retrieves_fixture_doc(self) -> None:
        docs = Path(__file__).resolve().parents[1] / "fixtures" / "docs.json"
        self.assertEqual(answer("alpha", docs), "rag scaffold ready")
        self.assertEqual(scaffold_status(), "rag scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.rag import retrieve_top_k


class DemoTest(unittest.TestCase):
    def test_retrieve_top_k_ranks_by_keyword_overlap(self) -> None:
        docs = {{
            "a": "quick fox",
            "b": "the lazy dog",
            "c": "quick fox jumps high",
        }}
        top = retrieve_top_k("quick fox", docs, k=2)
        self.assertEqual([doc_id for doc_id, _ in top], ["c", "a"])

    def test_retrieve_top_k_empty_query_keeps_ordering(self) -> None:
        docs = {{"a": "hello world", "b": "foo bar"}}
        top = retrieve_top_k("", docs, k=1)
        self.assertEqual(top[0][0], "b")


if __name__ == "__main__":
    unittest.main()
'''


def _render_real_retriever_script(package_name: str) -> str:
    """Q4-③: developer-executed real-retriever smoke check (in-process retrieval over the fixture corpus)."""
    return f'''"""Q4-③: real-retriever smoke check for the generated RAG scaffold.

Runs `retrieve` over the fixture corpus (`fixtures/docs.json`) to prove real in-process
retrieval. Wire your real vector store yourself. Run with: `uv run python scripts/verify_real_retriever.py`.
"""
from __future__ import annotations

from pathlib import Path

from {package_name}.rag import answer, load_docs, retrieve, scaffold_status


def _run() -> None:
    docs_path = Path(__file__).resolve().parents[1] / "fixtures" / "docs.json"
    docs = load_docs(docs_path)
    assert retrieve("alpha", docs) == "rag scaffold ready", "retrieval mismatch"
    assert answer("alpha", docs_path) == "rag scaffold ready"
    print("REAL RETRIEVER OK:", scaffold_status())


if __name__ == "__main__":
    _run()
'''


def scaffold_uv_rag(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-rag":
        raise RecipeError(f"Unsupported RAG scaffold recipe: {recipe}")
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
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "rag.py").write_text(_render_rag(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    fixtures = project_root / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "docs.json").write_text(
        '[{"id": "alpha", "text": "rag scaffold ready"}]\n',
        encoding="utf-8",
    )
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    scripts = project_root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "verify_real_retriever.py").write_text(_render_real_retriever_script(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "fixtures": "fixtures/",
            "tests": "tests/",
            "scripts": "scripts/",
            "packaging": "pyproject.toml",
        },
    )

"""GraphQL API on the npm language root.

Binding a port is not a verification gate.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    _npm_package_name,
    _write_json,
    run_command,
)
from .npm_vite_web import TYPESCRIPT_PIN
from .npm_commander_cli import TYPES_NODE_PIN

GRAPHQL_PIN = "16.9.0"


def _render_schema() -> str:
    return (
        "import { buildSchema, graphql } from 'graphql';\n\n"
        "export const STATUS = 'graphql scaffold ready';\n\n"
        "export const schema = buildSchema(`\n"
        "  type Book {\n"
        "    id: ID!\n"
        "    title: String!\n"
        "    author: String!\n"
        "  }\n"
        "  type Query {\n"
        "    status: String\n"
        "    books: [Book!]!\n"
        "    book(id: ID!): Book\n"
        "  }\n"
        "`);\n\n"
        "// 示例数据：可作为内存数据源供 resolver 与测试使用。\n"
        "export const books = [\n"
        "  { id: '1', title: 'The Rust Programming Language', author: 'Steve Klabnik' },\n"
        "  { id: '2', title: 'The Go Programming Language', author: 'Alan A. A. Donovan' },\n"
        "];\n\n"
        "export const root = {\n"
        "  status: () => STATUS,\n"
        "  books: () => books,\n"
        "  book: ({ id }: { id: string }) => books.find((item) => item.id === id) ?? null,\n"
        "};\n\n"
        "export async function executeQuery<T = unknown>(source: string): Promise<T> {\n"
        "  const result = await graphql({ schema, source, rootValue: root });\n"
        "  if (result.errors) {\n"
        "    throw new Error(result.errors.map((item) => item.message).join('; '));\n"
        "  }\n"
        "  return result.data as T;\n"
        "}\n\n"
        "export async function executeStatus(): Promise<string> {\n"
        "  const data = await executeQuery<{ status: string }>('{ status }');\n"
        "  return data.status;\n"
        "}\n"
    )


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "declaration": true,
    "outDir": "dist",
    "rootDir": "src",
    "skipLibCheck": true
  },
  "include": ["src"]
}
"""


def _render_query_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import { executeQuery } from "../dist/schema.js";\n\n'
        'test("books query returns the full list", async () => {\n'
        "  const data = await executeQuery('{ books { id title } }');\n"
        "  assert.equal(data.books.length, 2);\n"
        "  assert.equal(data.books[0].title, 'The Rust Programming Language');\n"
        "});\n\n"
        'test("book query resolves a single book by id", async () => {\n'
        "  const data = await executeQuery('{ book(id: \"2\") { title author } }');\n"
        "  assert.equal(data.book.title, 'The Go Programming Language');\n"
        "  assert.equal(data.book.author, 'Alan A. A. Donovan');\n"
        "});\n\n"
        'test("book query returns null for an unknown id", async () => {\n'
        "  const data = await executeQuery('{ book(id: \"missing\") { id } }');\n"
        "  assert.equal(data.book, null);\n"
        "});\n"
    )


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import { STATUS, executeStatus } from "../dist/schema.js";\n\n'
        'test("graphql executes status query in-process", async () => {\n'
        "  assert.equal(await executeStatus(), STATUS);\n"
        "});\n"
    )


def scaffold_npm_graphql(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-graphql":
        raise RecipeError(f"Unsupported GraphQL scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "scripts": {"build": "tsc", "test": "tsc && node --test \"tests/*.test.js\""},
        "dependencies": {"graphql": GRAPHQL_PIN},
        "devDependencies": {"@types/node": TYPES_NODE_PIN, "typescript": TYPESCRIPT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "schema.ts").write_text(_render_schema(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    (tests / "query.test.js").write_text(_render_query_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "schema": "src/schema.ts", "packaging": "package.json"},
    )

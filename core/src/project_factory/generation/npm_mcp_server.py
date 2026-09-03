"""Official MCP TypeScript SDK on the npm language root.

The Factory generates MCP servers; it is not an MCP Host.
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

MCP_SDK_PIN = "1.12.1"
ZOD_PIN = "3.24.2"
TYPES_NODE_PIN = "22.13.10"


def _render_server() -> str:
    return (
        "import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';\n"
        "import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';\n\n"
        "export const STATUS = 'mcp server scaffold ready';\n\n"
        "export function createServer(): McpServer {\n"
        "  const server = new McpServer({ name: 'scaffold-mcp', version: '0.1.0' });\n"
        "  server.tool('echo_purpose', 'Return scaffold status so a host can sanity-check this server.', {}, async () => ({\n"
        "    content: [{ type: 'text' as const, text: STATUS }],\n"
        "  }));\n"
        "  return server;\n"
        "}\n\n"
        "export async function main(): Promise<void> {\n"
        "  const server = createServer();\n"
        "  const transport = new StdioServerTransport();\n"
        "  await server.connect(transport);\n"
        "}\n\n"
        "if (process.argv[1] && process.argv[1].endsWith('server.js')) {\n"
        "  main();\n"
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


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import { Client } from "@modelcontextprotocol/sdk/client/index.js";\n'
        'import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";\n'
        'import { STATUS, createServer } from "../dist/server.js";\n\n'
        'test("in-memory host can call echo_purpose", async () => {\n'
        "  const server = createServer();\n"
        "  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();\n"
        "  await server.connect(serverTransport);\n"
        "  const client = new Client({ name: 'scaffold-test', version: '0.0.1' });\n"
        "  await client.connect(clientTransport);\n"
        "  const tools = await client.listTools();\n"
        "  assert.equal(tools.tools.some((tool) => tool.name === 'echo_purpose'), true);\n"
        "  const result = await client.callTool({ name: 'echo_purpose', arguments: {} });\n"
        "  const text = result.content[0] && result.content[0].text;\n"
        "  assert.equal(text, STATUS);\n"
        "  await client.close();\n"
        "});\n"
    )


def scaffold_npm_mcp_server(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-mcp-server":
        raise RecipeError(f"Unsupported TypeScript MCP scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "bin": {"scaffold-mcp": "./dist/server.js"},
        "scripts": {"build": "tsc", "test": "tsc && node --test tests/smoke.test.js"},
        "dependencies": {"@modelcontextprotocol/sdk": MCP_SDK_PIN, "zod": ZOD_PIN},
        "devDependencies": {"@types/node": TYPES_NODE_PIN, "typescript": TYPESCRIPT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "server.ts").write_text(_render_server(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "server": "src/server.ts", "packaging": "package.json"},
    )

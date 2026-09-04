# MCV Factory (基地车工厂)

> A Windows desktop "project factory" that turns a high-level requirement into a
> verified, evidence-backed software project. It pairs a Fluent/WPF front end
> with an isolated Python "Factory Core" that generates, verifies and recovers
> project scaffolding.

MCV Factory (基地车工厂) — named after the base vehicle MCV from
Command & Conquer: Red Alert, code "Project Factory" in the codebase — is a
**human-first** tool: the CLI / UI collect intent, the Core kernel produces a
project drawing, and every claim about the generated project is backed by an
evidence artifact rather than asserted.

- **Factory Core version:** `0.14.30`
- **Shell:** UX5.1 — Windows 11 Fluent (WPF / .NET, WPF-UI 4.3.0)
- **License:** [MIT](./LICENSE)

---

## Table of contents

- [What it is](#what-it-is)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Build & run (Windows)](#build--run-windows)
- [The Python bridge](#the-python-bridge)
- [Security model](#security-model)
- [Contributing](#contributing)
- [License](#license)

---

## What it is

MCV Factory takes a requirement (free text or a guided form), reasons about
it, and emits a project scaffold plus a set of **verification claims**. Each
claim is checked against real artifacts, and anything that looks like a secret
is redacted before it is ever persisted or sent to an external service.

Two parts work together:

1. **Factory Core** (`core/`) — a Python kernel (`project-factory-blueprint-kernel`)
   that does normalization, semantic reasoning, blueprint generation, verification
   suites and recovery. It is invoked over a JSON bridge.
2. **User Shell** (`shell/` + `backend/`) — a self-contained Windows WPF
   application (FluentWindow, Mica, NavigationView) that talks to the Core
   through a long-lived Python backend process.

---

## Architecture

```
┌─────────────────────────────┐      JSON over stdin/stdout        ┌──────────────────────────────┐
│  WPF Shell (shell/)         │ ───────────────────────────────▶  │  Python backend (backend/)    │
│  FluentWindow / Mica / NV   │      line-delimited `id` match     │  resident process bridge      │
└─────────────────────────────┘ ◀───────────────────────────────  └───────────────┬──────────────┘
                                                                                   │ invokes
                                                                                   ▼
                                                                          ┌────────────────────────────┐
                                                                          │  Factory Core (core/src)    │
                                                                          │  normalize → reason →       │
                                                                          │  generate → verify → recover│
                                                                          └────────────────────────────┘
```

- The shell launches **one** resident Python process and exchanges JSON
  requests/responses, matched by a per-line `id`. (This replaced the older
  per-call subprocess model to remove UI stutter.)
- The Core is fully isolated: it runs in its own venv and never modifies system
  Python. Optional AI assistance reads credentials from an **environment
  variable name** and never persists them.

---

## Repository layout

```
ProjectFactory/
├── core/                     # Factory Core (Python kernel)
│   ├── pyproject.toml        # project-factory-blueprint-kernel 0.14.30
│   ├── requirements.txt      # jsonschema==4.26.0, PyYAML==6.0.3
│   ├── src/project_factory/  # kernel source (package = src layout)
│   ├── tests/                # test suite
│   ├── docs/ schemas/ scripts/ fixtures/ golden_outputs/ compatibility/
├── shell/                    # WPF / .NET desktop client (ProjectFactory.Workbench)
│   ├── App.xaml(.cs) MainWindow.xaml(.cs) app.manifest
│   ├── Models/ Services/ Views/ Assets/
│   └── ProjectFactory.Workbench.csproj
├── backend/                  # Python bridge that the shell drives
│   └── project_factory_bridge.py (availability, gui_catalog, module_store, …)
├── installer/                # NSIS 3.12 installer source (BUILD_INSTALLER.*, *.nsi)
├── tools/                    # QA / lifecycle verification scripts
├── factory_resources/        # Resource universe (YAML / Markdown catalogs)
├── bootstrap_windows.py      # Windows first-run bootstrap
├── hot_upgrade_launch.py     # In-place upgrade / launch helper
├── THIRD_PARTY_NOTICES.md    # Third-party license summary
├── LICENSE                   # MIT
├── README.md  CONTRIBUTING.md  SECURITY.md  CODE_OF_CONDUCT.md  .gitignore
```

---

## Prerequisites

The desktop build targets **Windows 10 / 11**.

| Component        | Version            | Notes                                            |
|------------------|--------------------|--------------------------------------------------|
| .NET SDK         | 9.0.x (pinned)     | For building/publishing the WPF shell (targets `net9.0-windows`) |
| WPF-UI (NuGet)   | 4.3.0 (pinned)     | Fluent controls; pulled by NuGet during build    |
| Python           | 64-bit 3.11+       | Used only to create the isolated Core venv       |
| NSIS             | 3.12 (Modern UI 2) | Only needed to build the installer               |

Python runtime dependencies (installed into the isolated venv, never system-wide):

```
jsonschema==4.26.0
PyYAML==6.0.3
```

---

## Build & run (Windows)

### 1. Factory Core (Python)

```powershell
cd core
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
# Smoke test:
.\.venv\Scripts\python -m project_factory --help
```

### 2. WPF shell

```powershell
cd shell
dotnet build -c Release
# Or produce a self-contained, portable build:
dotnet publish -c Release -r win-x64 --self-contained true -o publish_win64
```

### 3. Bridge + launch

The shell expects the Python backend next to the installed app. For local runs,
`bootstrap_windows.py` prepares the isolated Core venv; `hot_upgrade_launch.py`
handles in-place upgrade/launch. The installer source under `installer/`
produces a per-user `ProjectFactory` install under
`%LOCALAPPDATA%\Programs\ProjectFactory`.

> The public build scripts that orchestrate the full Windows installer live under
> `installer/` (NSIS). They validate pinned toolchain archives by hash before use.

---

## The Python bridge

`backend/project_factory_bridge.py` is a **resident** process: the shell writes
one JSON request per line (each with a unique `id`) and reads responses matched
by that `id`. This keeps the UI responsive and avoids spawning a Python
interpreter on every action.

Example request (one line):

```json
{"id": 1, "action": "status"}
```

---

## Security model

- **No hardcoded secrets.** API keys / tokens are read from an environment
  variable *name*; the actual value is never written to disk by the Core.
- **Secret redaction.** The Core redacts credential material
  (`sk-…`, `ghp_…`, `AKIA…`, `Bearer …`, `api_key=…`, …) before persisting or
  sending text to any external service. See `core/src/project_factory/normalizer.py`.
- **Isolated runtime.** The Core runs in its own venv; it does not touch system
  Python packages.
- Generated project templates use development-only defaults (e.g. a sample
  `POSTGRES_PASSWORD: app` inside a scaffolded `docker-compose` drawing) — these
  are illustrative and not credentials for MCV Factory itself.

Please report vulnerabilities per [SECURITY.md](./SECURITY.md).

---

## Contributing

Thanks for your interest! See [CONTRIBUTING.md](./CONTRIBUTING.md) for the
developer setup, how to run the tests, and the PR process. By contributing you
agree your contributions are licensed under the MIT License.

---

## License

Released under the [MIT License](./LICENSE).

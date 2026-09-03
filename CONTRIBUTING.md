# Contributing to Project Factory

Thanks for helping improve Project Factory! This document covers the local
developer setup, how to run the tests, and the pull-request workflow.

## Code of conduct

This project adheres to a [Code of Conduct](./CODE_OF_CONDUCT.md). By
participating you are expected to uphold it.

## Getting started (Windows)

Project Factory is primarily developed and built on Windows 10 / 11.

1. Install the pinned toolchain:
   - .NET SDK **10.0.400**
   - 64-bit **Python 3.11+**
   - **NSIS 3.12** (only if you build the installer)
2. Clone the repository.
3. Set up the isolated Python Core venv:
   ```powershell
   cd core
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```
4. Build the WPF shell:
   ```powershell
   cd shell
   dotnet build -c Release
   ```

## Repository map

| Path                | What lives there                                  |
|---------------------|---------------------------------------------------|
| `core/`             | Factory Core Python kernel (package `src` layout) |
| `shell/`            | WPF / .NET desktop client                         |
| `backend/`          | Python bridge driven by the shell                 |
| `installer/`        | NSIS installer source                             |
| `tools/`            | QA / lifecycle verification scripts               |
| `factory_resources/`| Resource universe catalogs (YAML / Markdown)      |

## Running the tests

```powershell
cd core
.\.venv\Scripts\pip install pytest
.\.venv\Scripts\python -m pytest
```

The `tools/` directory contains lifecycle / build-gate verification scripts used
to validate a full Windows build.

## Before you open a pull request

- Keep the **isolated runtime** contract: the Core must not modify system Python.
- Do **not** add hardcoded credentials. Read secrets from an environment variable
  *name*; never persist secret values.
- Run the relevant tests and, for shell changes, a `dotnet build -c Release`.
- Keep PRs focused. Describe the *why* in the description, not just the *what*.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](./LICENSE).

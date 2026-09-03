# Changelog

All notable changes to Project Factory are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.14.30] - 2026-09-03

First public open-source release, extracted from the internal repository.

### Added

- **Core** (`core/`): Python factory kernel `project-factory-blueprint-kernel`
  (v0.14.30) — human-first CLI, evidence-first generation, recovery, upgrades and
  bounded external integrations.
- **Shell** (`shell/`): .NET 9 / WPF Fluent desktop frontend (WPF-UI 4.3.0).
- **Backend bridge** (`backend/project_factory_bridge.py`): resident subprocess
  JSON-line protocol bridging the .NET shell and the Python Core.
- **Installer** (`installer/`): NSIS 3.12 Windows installer source.
- **Resources** (`factory_resources/`): bundled catalog and registry data.
- Documentation set under `core/docs/` (architecture, contracts, operations, quickstart).

### Notes

- This repository ships **source**; it does not vendor prebuilt binaries or wheels.
- Build the Core with `pip install ./core`; build the Shell with the .NET SDK
  (Windows-only). See `README.md` for build and run instructions.

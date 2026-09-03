# Third-Party Notices

UX5 source references/downloads third-party components during the Windows build. This source bundle does not vendor the WPF-UI NuGet binaries or the .NET SDK.

## WPF UI

- Project: WPF UI (`lepoco/wpfui`)
- Version pinned by UX5: 4.3.0
- License: MIT
- Role: Fluent Windows desktop controls, NavigationView, Mica/FluentWindow, icons and theming.

## .NET

- SDK pinned for reproducible Windows build: 10.0.400
- Build script validates the official SDK archive SHA512 before use.
- Published user application is self-contained win-x64.

## NSIS

- Version pinned: 3.12
- Modern UI 2 is used for the installer.
- Build script verifies the pinned NSIS portable archive SHA256 before compilation.

## Python dependencies

The isolated Core runtime installs pinned Python packages from the configured package source. It does not modify system Python packages.

## Project Factory Core

Project Factory Core is distributed as Python source under `core/` (package
`project-factory-blueprint-kernel`, version 0.14.30). Build and install it from
the repository root with:

    pip install ./core      # install the built package
    pip install -e ./core   # editable install for development

This source repository does not vendor a prebuilt Core wheel.

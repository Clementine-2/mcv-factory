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

The bundled Project Factory Core wheel is the unchanged 0.14.1 wheel from the previously verified baseline:

`12b347e3ea85392bd0181974aa1167208d2c04e90bb33cb4623d88219440c34b`

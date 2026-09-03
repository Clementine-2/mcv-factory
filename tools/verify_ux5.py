from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "shell" / "ProjectFactory.Workbench"

ERRORS: list[str] = []
CHECKS: list[dict[str, object]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})
    if not ok:
        ERRORS.append(f"{name}: {detail}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


# 1. XAML must be well-formed and x:Class must have matching code-behind.
xaml_files = sorted(SHELL.rglob("*.xaml"))
record("xaml-present", bool(xaml_files), f"count={len(xaml_files)}")
for path in xaml_files:
    try:
        tree = ET.parse(path)
        record(f"xml:{path.relative_to(ROOT)}", True)
    except Exception as exc:
        record(f"xml:{path.relative_to(ROOT)}", False, str(exc))
        continue
    cls = tree.getroot().attrib.get("{http://schemas.microsoft.com/winfx/2006/xaml}Class")
    if cls:
        codebehind = Path(str(path) + ".cs")
        record(
            f"codebehind:{path.relative_to(ROOT)}",
            codebehind.is_file(),
            f"x:Class={cls}; expected={codebehind.relative_to(ROOT) if codebehind.is_file() else codebehind}",
        )

# 2. Event handlers referenced in XAML must exist in its code-behind.
event_attrs = {
    "Click", "Loaded", "SizeChanged", "SelectionChanged", "Checked", "Unchecked",
    "LostFocus", "TextChanged", "Closing", "Closed", "Navigated", "Navigating",
    "PaneOpened", "PaneClosed", "ItemInvoked",
}
for path in xaml_files:
    codebehind = Path(str(path) + ".cs")
    if not codebehind.is_file():
        continue
    code = read(codebehind)
    tree = ET.parse(path)
    handlers: set[str] = set()
    for elem in tree.iter():
        for key, value in elem.attrib.items():
            local = key.split("}")[-1]
            if local in event_attrs and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
                handlers.add(value)
    missing = [h for h in sorted(handlers) if not re.search(rf"\b{re.escape(h)}\s*\(", code)]
    record(f"handlers:{path.relative_to(ROOT)}", not missing, "missing=" + ",".join(missing) if missing else f"count={len(handlers)}")

# 3. Formal UI path must not depend on Tk/ttkbootstrap/Pillow.
formal_text_paths = [*SHELL.rglob("*.cs"), *SHELL.rglob("*.xaml"), ROOT / "bootstrap_windows.py", ROOT / "installer" / "ProjectFactoryInstaller.nsi"]
forbidden_hits: list[str] = []
for path in formal_text_paths:
    text = read(path)
    for token in ("import tkinter", "from tkinter", "ttkbootstrap", "Pillow=="):
        if token.lower() in text.lower():
            # bootstrap self-test assertions intentionally mention old packages; do not count those.
            if path.name == "bootstrap_windows.py" and "assert" in next((ln for ln in text.splitlines() if token.lower() in ln.lower()), ""):
                continue
            forbidden_hits.append(f"{path.relative_to(ROOT)}:{token}")
record("no-tk-formal-ui", not forbidden_hits, "; ".join(forbidden_hits))

# 4. WPF project contract.
csproj = read(SHELL / "ProjectFactory.Workbench.csproj")
expected_contract = {
    "net10-windows": "<TargetFramework>net10.0-windows10.0.26100.0</TargetFramework>" in csproj,
    "use-wpf": "<UseWPF>true</UseWPF>" in csproj,
    "wpf-ui-4.3.0": 'PackageReference Include="WPF-UI" Version="4.3.0"' in csproj,
    "wpf-ui-di-4.3.0": 'PackageReference Include="WPF-UI.DependencyInjection" Version="4.3.0"' in csproj,
    "winexe": "<OutputType>WinExe</OutputType>" in csproj,
}
for name, ok in expected_contract.items():
    record(f"csproj:{name}", ok)

app_xaml = read(SHELL / "App.xaml")
record("font:cjk-primary", "Microsoft YaHei UI" in app_xaml)
record("font:segoe-fallback", "Segoe UI Variable Text" in app_xaml and "Segoe UI" in app_xaml)
record("font:theme-foreground", "TextFillColorPrimaryBrush" in app_xaml)
record("xml-lang-zh", 'xml:lang="zh-CN"' in app_xaml)
main_xaml = read(SHELL / "MainWindow.xaml")
record("fluent-window", "<ui:FluentWindow" in main_xaml)
record("mica", 'WindowBackdropType="Mica"' in main_xaml)
record("shell-application-icon", "<ApplicationIcon>" in csproj and "Assets\\app.ico" in csproj and (SHELL / "Assets" / "app.ico").is_file())
settings_cs = read(SHELL / "Services" / "ShellSettings.cs")
record("appearance-scale-mode", "ScaleMode" in settings_cs and "Uniform" in settings_cs and "Fill" in settings_cs and "ScaleBox" in settings_cs)
record("appearance-custom-background", "BackgroundImage" in settings_cs)
record("appearance-font-size", "FontSizeKey" in settings_cs)
record("appearance-corners", "CornerStyle" in settings_cs and "DoNotRound" in settings_cs)
record("navigation-view", "<ui:NavigationView" in main_xaml)
record("no-obsolete-page-tag", "PageTag=" not in main_xaml and "TargetPageTag=" not in main_xaml, "navigation is Type-based")
record("five-primary-destinations", main_xaml.count("<ui:NavigationViewItem ") == 5, f"count={main_xaml.count('<ui:NavigationViewItem ')}")

# 4b. WPF-UI 4.3.0 public API contract. The WPF UI Gallery has a project-local
# IWindow sample contract, but WPF-UI 4.3.0 itself does not expose Wpf.Ui.IWindow.
main_cs = read(SHELL / "MainWindow.xaml.cs")
app_cs = read(SHELL / "App.xaml.cs")
all_cs = "\n".join(read(p) for p in sorted(SHELL.rglob("*.cs")))
record("wpfui43-mainwindow-fluentwindow-only", "public partial class MainWindow : FluentWindow" in main_cs and "FluentWindow, IWindow" not in main_cs)
record("wpfui43-no-fake-iwindow-contract", not re.search(r"\binterface\s+IWindow\b", all_cs) and not re.search(r"\b:\s*[^\n{]*\bIWindow\b", all_cs), "Gallery IWindow must not leak into product source")
record("wpfui43-concrete-mainwindow-di", "services.AddSingleton<MainWindow>();" in app_cs and "AddSingleton<IWindow" not in app_cs)
record("wpfui43-navigation-service-api", "INavigationService navigationService" in main_cs and "navigationService.SetNavigationControl(RootNavigationView);" in main_cs)
record("wpfui43-navigation-typed-events", "navigationService.SetNavigationControl(RootNavigationView);" in main_cs and "PaneOpenedEventArgs" not in main_cs)
record("shell-scale-viewbox", "<Viewbox" in main_xaml and 'x:Name="ScaleBox"' in main_xaml)
record("shell-no-global-ime-disable", "SetIsInputMethodEnabled(this, false)" not in main_cs and "SetIsInputMethodSuspended(this, true)" not in main_cs)
record("page-viewport-bind", "PageViewport.Bind" in read(SHELL / "Views" / "SettingsPage.xaml.cs") and 'x:Name="RootScroll"' in read(SHELL / "Views" / "SettingsPage.xaml"))
record("wpfui43-api-audit-evidence", (ROOT / "evidence" / "WPF_UI_4_3_API_AUDIT_20260830.md").is_file())

# 4c. Gate 5 (Hotfix 5A) — normal-close lifecycle contract.
# A custom HwndSource/WM_CLOSE hook previously intercepted WM_CLOSE, called
# Close(), then set handled=true. That prevented Process.CloseMainWindow() from
# completing the standard WPF close sequence and left the process alive past the
# 5s hard gate. OnExit + ProcessExit could also double-cleanup the DI container.
record("gate5-mainwindow-no-hwndsource-hook", not re.search(r"new\s+HwndSource|\.AddHook\s*\(|FromHwnd", main_cs),
       "custom WM_CLOSE hook (HwndSource/AddHook) removed; close handled by WPF FluentWindow message loop")
record("gate5-mainwindow-hook-removal-documented", "Gate 5 fix (Hotfix 5A)" in main_cs and "WM_CLOSE" in main_cs,
       "intentional removal explained in MainWindow.xaml.cs header comment")
record("gate5-mainwindow-fluentwindow-only", "public partial class MainWindow : FluentWindow" in main_cs and "FluentWindow, IWindow" not in main_cs)
record("gate5-app-shutdown-mode-on-mainwindow-close", "ShutdownMode = ShutdownMode.OnMainWindowClose" in app_cs)
record("gate5-app-mainwindowclosed-shutdown", "window.Closed += OnMainWindowClosed" in app_cs and "private async void OnMainWindowClosed" in app_cs and "Shutdown(0)" in app_cs)
record("gate5-app-cleanup-idempotent", "Interlocked.CompareExchange(ref _cleanupDone, 1, 0)" in app_cs, "OnExit + ProcessExit share Cleanup() without double-dispose")
record("gate5-app-bridge-grace-shutdown", "bridge.ShutdownAsync(" in app_cs and "_services.GetService<PythonBridgeClient>()" in app_cs)
bridge_cs = read(SHELL / "Services" / "PythonBridgeClient.cs")
record("gate5-bridge-client-shutdownasync", "public async Task ShutdownAsync(TimeSpan timeout)" in bridge_cs and "IAsyncDisposable" in bridge_cs,
       "PythonBridgeClient exposes ShutdownAsync + IAsyncDisposable")
record("gate5-lifecycle-hard-gate-test-present", (ROOT / "tools" / "test_lifecycle_gate5.py").is_file())
gate5_src = read(ROOT / "tools" / "test_lifecycle_gate5.py") if (ROOT / "tools" / "test_lifecycle_gate5.py").is_file() else ""
record("gate5-live-bridge-predicate", "live_bridge_observed" in gate5_src and ".pf_runtime" in gate5_src and "python.exe" in gate5_src)
record("gate5-live-bridge-required-for-pass", "live_bridge_observed" in gate5_src and "live_bridge_not_observed" in gate5_src)
record("gate5-fallback-never-converts-to-pass", "will NOT convert to PASS" in gate5_src and "EMERGENCY_CLEANUP" in gate5_src)

# 5. Visual design rule: static text must not be TextBox just for display.
# The only read-only TextBox is the diagnostic JSON console in Tools, which is intentional.
readonly_textboxes: list[str] = []
for path in SHELL.rglob("*.xaml"):
    text = read(path)
    if 'IsReadOnly="True"' in text:
        readonly_textboxes.append(path.relative_to(ROOT).as_posix())
record("readonly-textbox-scope", readonly_textboxes == ["shell/ProjectFactory.Workbench/Views/ToolsPage.xaml"], ",".join(readonly_textboxes))

# 6. Bridge and Core authority contract.
bridge = read(ROOT / "backend" / "project_factory_bridge.py")
for action in ("ping", "status", "analyze", "generate", "history", "check", "verify_zip"):
    record(f"bridge-action:{action}", f'"{action}"' in bridge or f"'{action}'" in bridge)
record("bridge-user-confirmed-matrix", "apply_matrix_overrides" in bridge)
record("bridge-core-generation", "generate_project" in bridge)

# 7. Bootstrap must be Core-only and bounded failover.
bootstrap = read(ROOT / "bootstrap_windows.py")
record("bootstrap-schema", 'BOOTSTRAP_SCHEMA = "ux5-runtime-1"' in bootstrap)
record("bootstrap-no-gui-runtime", '"ttkbootstrap==' not in bootstrap and '"Pillow==' not in bootstrap)
record("bootstrap-auto-failover", "source_failover_order" in bootstrap and "[AUTO-RETRY]" in bootstrap)
record("bootstrap-hard-timeout", "timeout=240" in bootstrap)

# 8. Installer safety and WPF entrypoint.
installer = read(ROOT / "installer" / "ProjectFactoryInstaller.nsi")
record("installer-brand-icon", "MUI_ICON" in installer and "app.ico" in installer)
record("installer-per-user", "RequestExecutionLevel user" in installer and 'InstallDir "$LOCALAPPDATA\\Programs\\ProjectFactory"' in installer)
record("installer-wpf-entrypoint", '$INSTDIR\\app\\ProjectFactory.exe' in installer)
record("installer-self-contained-publish", 'File /r "publish\\*.*"' in installer)
record("installer-no-whole-instdir-recursive-delete", 'RMDir /r "$INSTDIR"' not in installer)
record("installer-preserves-user-data", "%LOCALAPPDATA%\\ProjectFactory" in installer and "user project outputs" in installer)

# 9. Build gate must be parse-safe, always create logs, pin toolchains, and publish self-contained.
build = read(ROOT / "installer" / "BUILD_INSTALLER.ps1")
build_bat = read(ROOT / "installer" / "BUILD_INSTALLER.bat")
root_build_bat = read(ROOT / "BUILD_AND_RUN_FLUENT_INSTALLER.bat")
record("setup-name-ux51", "UX5.1.exe" in root_build_bat and "UX5.1.exe" in build and "UX5.1.exe" in installer)
record("build-dotnet-pinned", "$DotnetVersion = '10.0.400'" in build and "$ExpectedDotnetSha512" in build)
record("build-nsis-pinned", "$ExpectedNsisSha256 = '56581f90db321581c5381193d796fffcf2d24b2f8fed2160a6c6a3baa67f2c4f'" in build)
record("build-nuget-failover", "$NugetSources" in build and "Switching source" in build)
record("build-self-contained", "'--self-contained', 'true'" in build)
record("build-no-trim", "PublishTrimmed=false" in build)
record("build-log-directory", "$PhysicalLogDir = Join-Path $PhysicalInstallerRoot 'logs'" in build and "$Log = Join-Path $PhysicalLogDir 'build.log'" in build and "installer\\logs\\build.log" in root_build_bat)
record("build-parser-preflight", "System.Management.Automation.Language.Parser" in build_bat and "build-preflight.log" in build_bat)
record("build-log-dir-precedes-parser", build_bat.find('if not exist "%LOGDIR%" mkdir') != -1 and build_bat.find('if not exist "%LOGDIR%" mkdir') < build_bat.find("System.Management.Automation.Language.Parser"))
record("build-parser-precedes-main-script", build_bat.find("System.Management.Automation.Language.Parser") != -1 and build_bat.find("System.Management.Automation.Language.Parser") < build_bat.find('-File "%PF_BUILD_SCRIPT%"'))
record("build-log-folder-materialized", (ROOT / "installer" / "logs" / "README.txt").is_file())
record("build-fatal-catch", "function Write-Fatal" in build and "catch {" in build and "Write-Fatal $_" in build)
record("build-no-expand-archive", "Expand-Archive" not in build)
record("build-win11-tar-extractor", "Get-Command tar.exe" in build and "@('-xf', $ZipPath, '-C', $Destination)" in build)
record("build-zipfile-extractor-fallback", "System.IO.Compression.ZipFile" in build and "ExtractToDirectory($ZipPath, $Destination)" in build)
record("build-nsis-staging-extraction", "nsis-3.12-extract-staging" in build and "Move-Item -LiteralPath $stagedRoot -Destination $extractRoot" in build)
record("build-no-dead-subst-to-satisfy-static-gates", "satisfy static release gates" not in build.lower() and "dummy object" not in build.lower())
record("build-no-live-subst-implementation", "subst.exe" not in build.lower() and "Initialize-ShortBuildRoot" not in build and "Remove-ShortBuildRoot" not in build)
record("build-physical-path-model", "[BUILD-MODEL]" in build and "physical-path" in build and "$BundleRoot = $PhysicalBundleRoot.TrimEnd('\\')" in build)
record("build-all-workpaths-use-physical-root", "$InstallerRoot = Join-Path $BundleRoot 'installer'" in build and "$ShellProject = Join-Path $BundleRoot 'shell\\ProjectFactory.Workbench\\ProjectFactory.Workbench.csproj'" in build)
record("build-short-nuget-cache-resolver", "function Resolve-ProjectFactoryNugetCache" in build and "[NUGET-CACHE-PATH]" in build)
record("build-nuget-cache-auto-not-fixed-drive", "GetPathRoot($PhysicalRoot)" in build and ".projectfactory\\nuget-packages" in build)
record("build-nuget-cache-policy-logged", "[NUGET-CACHE-POLICY]" in build and "retain-across-builds" in build and "never deleted" in build)
record("build-nuget-cache-no-other-project-wipe", "$env:USERPROFILE" not in build.split("function Resolve-ProjectFactoryNugetCache", 1)[-1].split("function Download-WithFailover", 1)[0] and "global-packages" not in build.split("function Resolve-ProjectFactoryNugetCache", 1)[-1].split("function Download-WithFailover", 1)[0])
record("build-max-path-budget-gate", "[PATH-BUDGET]" in build and "$runtimeProbe.Length -ge 240" in build)
record("build-dotnet-managed-probe", "[DOTNET-PROBE]" in build and "Invoke-NativeCapture -FilePath $dotnet -ArgumentList @('--info')" in build)
record("build-owned-process-cleanup", "Stop-BundleOwnedBuildProcesses" in build and "[BUILD-CLEANUP]" in build)
record("build-no-global-longpath-policy-change", "LongPathsEnabled" not in build and "reg.exe" not in build.lower())
record("build-canonical-entry-is-root-bat", 'call "%~dp0installer\\BUILD_INSTALLER.bat"' in root_build_bat and (ROOT / "BUILD_AND_RUN_FLUENT_INSTALLER.bat").is_file())
record("build-script-emits-ready-and-sha", 'Write-Step "[READY] $rootSetup"' in build and 'Write-Step "[SHA256] $setupHash"' in build)
record("build-script-exits-with-code", "exit $exitCode" in build)

# PowerShell interpolation pitfall: unbraced $Name: inside strings is parsed like scoped/drive syntax.
# Legitimate scoped variables such as $env:PATH are excluded.
scoped_names = {"env", "global", "script", "local", "private", "using", "variable", "function"}
ambiguous_colon_refs = []
for match in re.finditer(r"(?<!\{)\$([A-Za-z_][A-Za-z0-9_]*)\:", build):
    if match.group(1).lower() not in scoped_names:
        line = build.count("\n", 0, match.start()) + 1
        ambiguous_colon_refs.append(f"{match.group(0)}@{line}")
record("build-no-ambiguous-variable-colon", not ambiguous_colon_refs, ",".join(ambiguous_colon_refs))

# --packages is a dotnet restore option, not a dotnet publish option.
publish_lines = [line for line in build.splitlines() if "$publishArgs = @('publish'" in line]
record("build-publish-no-packages-option", bool(publish_lines) and all("--packages" not in line for line in publish_lines), " | ".join(publish_lines))
record("build-restore-packages-cache", any("$restoreArgs = @('restore'" in line and "'--packages', $NugetCache" in line for line in build.splitlines()))
direct_native_calls = [line.strip() for line in build.splitlines() if re.search(r"&\s+\$[A-Za-z_]", line)]
record("build-single-native-call-site", direct_native_calls == ["$lines = @(& $FilePath @ArgumentList 2>&1)"], " | ".join(direct_native_calls))
record("build-no-tee-object-native-hazard", "Tee-Object" not in build)
record("build-native-command-wrapper", "function Invoke-NativeCapture" in build and "$ErrorActionPreference = 'Continue'" in build and "$ErrorActionPreference = $previousPreference" in build)
record("build-nuget-wrapper-failover", "Invoke-NativeLogged -FilePath $Dotnet -ArgumentList $restoreArgs" in build and "[NUGET-FAILED]" in build)
record("build-publish-native-wrapper", "Invoke-NativeLogged -FilePath $dotnet -ArgumentList $publishArgs" in build)
record("build-nsis-native-wrapper", "Invoke-NativeLogged -FilePath $makensis -ArgumentList @('/V4', 'ProjectFactoryInstaller.nsi')" in build)

# 10. Wheel identity.
wheel = ROOT / "wheel" / "project_factory_blueprint_kernel-0.14.22-py3-none-any.whl"
record("core-wheel-present", wheel.is_file())
if wheel.is_file():
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    record("core-wheel-sha256", digest == "e6916746cbbfed34d0a441ee46e1d6140da32bf754937ab43b0d49858e6dffa3", digest)

result = {
    "schema": "project-factory-ux5-static-verification/1",
    "status": "PASS" if not ERRORS else "FAIL",
    "checks": CHECKS,
    "failures": ERRORS,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(0 if not ERRORS else 1)

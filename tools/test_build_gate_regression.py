from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "installer" / "BUILD_INSTALLER.ps1"
BAT = ROOT / "installer" / "BUILD_INSTALLER.bat"
ROOT_BAT = ROOT / "BUILD_AND_RUN_FLUENT_INSTALLER.bat"
LOG_README = ROOT / "installer" / "logs" / "README.txt"

SCOPED_NAMES = {"env", "global", "script", "local", "private", "using", "variable", "function"}
checks: list[dict[str, object]] = []
failures: list[str] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})
    if not ok:
        failures.append(f"{name}: {detail}")


def ambiguous_colon_refs(text: str) -> list[str]:
    hits: list[str] = []
    for match in re.finditer(r"(?<!\{)\$([A-Za-z_][A-Za-z0-9_]*)\:", text):
        if match.group(1).lower() not in SCOPED_NAMES:
            line = text.count("\n", 0, match.start()) + 1
            hits.append(f"{match.group(0)}@{line}")
    return hits


ps1 = PS1.read_text(encoding="utf-8-sig")
bat = BAT.read_text(encoding="utf-8-sig")
root_bat = ROOT_BAT.read_text(encoding="utf-8-sig")

# Regression fixture for the exact Windows failure reported on 2026-08-30.
bad_fixture = 'Write-Step "[OK] Using installed .NET SDK $DotnetVersion: $($system.Source)"'
fixture_hits = ambiguous_colon_refs(bad_fixture)
record("regression-fixture-detects-variable-colon", fixture_hits == ["$DotnetVersion:@1"], repr(fixture_hits))

current_hits = ambiguous_colon_refs(ps1)
record("current-script-has-no-ambiguous-variable-colon", not current_hits, repr(current_hits))
record("current-script-braces-dotnet-version", "${DotnetVersion}:" in ps1)

publish_lines = [line.strip() for line in ps1.splitlines() if "$publishArgs = @('publish'" in line]
restore_lines = [line.strip() for line in ps1.splitlines() if "$restoreArgs = @('restore'" in line]
record("publish-command-found", len(publish_lines) == 1, repr(publish_lines))
record("publish-does-not-use-restore-only-packages-option", bool(publish_lines) and all("--packages" not in line for line in publish_lines), repr(publish_lines))
record("restore-keeps-explicit-package-cache", any("'--packages', $NugetCache" in line for line in restore_lines), repr(restore_lines))

mkdir_pos = bat.find('if not exist "%LOGDIR%" mkdir')
parser_pos = bat.find("System.Management.Automation.Language.Parser")
execute_pos = bat.find('-File "%PF_BUILD_SCRIPT%"')
record("batch-log-dir-created-before-parser", -1 not in (mkdir_pos, parser_pos) and mkdir_pos < parser_pos, f"mkdir={mkdir_pos}, parser={parser_pos}")
record("batch-parser-runs-before-main-script", -1 not in (parser_pos, execute_pos) and parser_pos < execute_pos, f"parser={parser_pos}, execute={execute_pos}")
record("batch-parser-does-not-rely-on-cmd-pipe-escape", "^| Out-Null" not in bat and "$null = [System.Management.Automation.Language.Parser]::ParseFile" in bat)
record("batch-copies-preflight-to-canonical-log-on-parse-failure", 'copy /y "%PREFLIGHT_LOG%" "%BUILD_LOG%"' in bat)
record("root-wrapper-points-to-canonical-log", "installer\\logs\\build.log" in root_bat)
record("log-directory-survives-zip", LOG_README.is_file(), str(LOG_README.relative_to(ROOT)))

# Regression for the real Win11 Hotfix 1 failure: Windows PowerShell 5.1
# Expand-Archive entered Microsoft.PowerShell.Archive cleanup and failed on
# sdk\10.0.400\.toolsetversion after the SDK hash had already verified.
record("no-powershell-expand-archive", "Expand-Archive" not in ps1)
record("windows-tar-primary-extractor", "Get-Command tar.exe" in ps1 and "@('-xf', $ZipPath, '-C', $Destination)" in ps1)
record("zipfile-fallback-extractor", "System.IO.Compression.ZipFile" in ps1 and "ExtractToDirectory($ZipPath, $Destination)" in ps1)
record("extraction-fallback-is-logged", "[EXTRACT-FAILED] Windows tar.exe" in ps1 and "[EXTRACT-OK]" in ps1)
record("dotnet-extraction-isolated", 'Expand-ZipReliable -ZipPath $zipPath -Destination $extractRoot -Label ".NET SDK $DotnetVersion x64"' in ps1)
record("nsis-extraction-isolated-staging", "nsis-3.12-extract-staging" in ps1 and "Move-Item -LiteralPath $stagedRoot -Destination $extractRoot" in ps1)


# Regression for the real Win11 Hotfix 2 failure: the portable SDK could be
# extracted and dotnet.exe existed, but the CLR dependency path presented to
# CreateFileW was 261 characters. That crosses legacy MAX_PATH (260).
hotfix2_log = ROOT / "evidence" / "WINDOWS_BUILD_HOTFIX2_20260830.log"
log_text = hotfix2_log.read_text(encoding="utf-8-sig") if hotfix2_log.is_file() else ""
path_match = re.search(r"CreateFileW\(([^)]+Microsoft\.NETCore\.App\.deps\.json)\)", log_text)
failing_path = path_match.group(1) if path_match else ""
record("hotfix2-evidence-present", hotfix2_log.is_file(), str(hotfix2_log.relative_to(ROOT)))
record("hotfix2-failure-path-captured", bool(failing_path), failing_path)
record("hotfix2-failure-crosses-max-path", len(failing_path) >= 260, f"length={len(failing_path)}")

record("no-dead-subst-dummy-to-satisfy-static-gates", "satisfy static release gates" not in ps1.lower() and "dummy object" not in ps1.lower())
record("no-live-subst-implementation", "subst.exe" not in ps1.lower() and "Initialize-ShortBuildRoot" not in ps1 and "Remove-ShortBuildRoot" not in ps1)
record("physical-path-build-model", "[BUILD-MODEL]" in ps1 and "physical-path" in ps1 and "$BundleRoot = $PhysicalBundleRoot.TrimEnd('\\')" in ps1)
record("all-build-paths-rooted-at-physical-bundle", "$InstallerRoot = Join-Path $BundleRoot 'installer'" in ps1 and "$ShellProject = Join-Path $BundleRoot" in ps1 and "$BundleRoot = $PhysicalBundleRoot.TrimEnd('\\')" in ps1)
record("short-nuget-cache-is-auto-and-scoped", "function Resolve-ProjectFactoryNugetCache" in ps1 and "[NUGET-CACHE-PATH]" in ps1 and ".projectfactory\\nuget-packages" in ps1)
record("nuget-cache-not-fixed-drive-letter", "GetPathRoot($PhysicalRoot)" in ps1 and "D:\\npk" not in ps1 and "C:\\Users\\" not in ps1)
record("nuget-cache-policy-retain-not-global-wipe", "[NUGET-CACHE-POLICY]" in ps1 and "retain-across-builds" in ps1)
record("nuget-packages-env-assigned", "$env:NUGET_PACKAGES = $NugetCache" in ps1)
record("max-path-budget-gate", "[PATH-BUDGET]" in ps1 and "$runtimeProbe.Length -ge 240" in ps1)
record("dotnet-managed-runtime-probe-before-restore", "[DOTNET-PROBE]" in ps1 and "Invoke-NativeCapture -FilePath $dotnet -ArgumentList @('--info')" in ps1 and ps1.find("Invoke-NativeCapture -FilePath $dotnet -ArgumentList @('--info')") < ps1.find("function Restore-Shell"))
record("owned-build-process-cleanup-in-finally", "Stop-BundleOwnedBuildProcesses" in ps1 and "[BUILD-CLEANUP]" in ps1)
record("does-not-mutate-global-long-path-policy", "LongPathsEnabled" not in ps1 and "reg.exe" not in ps1.lower())
record("canonical-entry-is-official-root-bat", 'call "%~dp0installer\\BUILD_INSTALLER.bat"' in root_bat)
record("build-script-emits-ready-setup-sha-and-exit", 'Write-Step "[READY] $rootSetup"' in ps1 and 'Write-Step "[SHA256] $setupHash"' in ps1 and "exit $exitCode" in ps1)

direct_native_calls = [line.strip() for line in ps1.splitlines() if re.search(r"&\s+\$[A-Za-z_]", line)]
record("single-direct-native-call-is-inside-wrapper", direct_native_calls == ["$lines = @(& $FilePath @ArgumentList 2>&1)"], repr(direct_native_calls))
record("native-output-no-tee-object-stop-hazard", "Tee-Object" not in ps1)
record("native-command-wrapper-owns-exit-code", "function Invoke-NativeCapture" in ps1 and "$ErrorActionPreference = 'Continue'" in ps1 and "$ErrorActionPreference = $previousPreference" in ps1)
record("nuget-failover-uses-native-wrapper", "Invoke-NativeLogged -FilePath $Dotnet -ArgumentList $restoreArgs" in ps1 and "[NUGET-FAILED]" in ps1)
record("publish-uses-native-wrapper", "Invoke-NativeLogged -FilePath $dotnet -ArgumentList $publishArgs" in ps1)
record("nsis-uses-native-wrapper", "Invoke-NativeLogged -FilePath $makensis -ArgumentList @('/V4', 'ProjectFactoryInstaller.nsi')" in ps1)

# A representative physical runtime leaf plus a drive-root Project Factory
# NuGet cache must keep substantial MAX_PATH headroom (Hotfix 2 failed at 261).
physical_runtime_leaf = r"D:\hf5c_r1\installer\.tooling\dotnet-10.0.400\shared\Microsoft.NETCore.App\10.0.11\Microsoft.NETCore.App.deps.json"
record("physical-runtime-path-has-headroom", len(physical_runtime_leaf) < 240, f"length={len(physical_runtime_leaf)}")
nuget_cache_example = r"D:\.projectfactory\nuget-packages"
record("short-nuget-cache-path-has-headroom", len(nuget_cache_example) < 120, f"length={len(nuget_cache_example)}")

# Regression for the real Win11 Hotfix 3 result: build infrastructure passed
# through restore and entered C#/WPF compilation, where a Gallery-only IWindow
# sample contract was incorrectly treated as a WPF-UI package API.
hotfix3_log = ROOT / "evidence" / "WINDOWS_BUILD_HOTFIX3_20260830.log"
h3 = hotfix3_log.read_text(encoding="utf-8-sig") if hotfix3_log.is_file() else ""
main_cs = (ROOT / "shell" / "ProjectFactory.Workbench" / "MainWindow.xaml.cs").read_text(encoding="utf-8-sig")
app_cs = (ROOT / "shell" / "ProjectFactory.Workbench" / "App.xaml.cs").read_text(encoding="utf-8-sig")
record("hotfix3-evidence-present", hotfix3_log.is_file(), str(hotfix3_log.relative_to(ROOT)))
record("hotfix3-short-path-real-pass", "[PATHMAP]" in h3 and "runtime probe length=106" in h3 and "[PATHMAP-CLEANUP] Removed temporary mapping" in h3)
record("hotfix3-dotnet-probe-real-pass", "Version:           10.0.400" in h3 and "[OK] Portable .NET SDK ready:" in h3)
record("hotfix3-nuget-failover-real-pass", "[NUGET-FAILED] Microsoft China" in h3 and "[NUGET-OK] NuGet.org" in h3)
record("hotfix3-reached-real-wpf-compile", "[BUILD 1/2] Publishing self-contained Win11 Fluent WPF shell." in h3)
prepatch = (ROOT / "evidence" / "HOTFIX3_MAINWINDOW_PREPATCH.cs.txt").read_text(encoding="utf-8-sig")
record("hotfix3-captured-iwindow-cs0246", "MainWindow.xaml.cs(9,49): error CS0246" in h3 and "FluentWindow, IWindow" in prepatch)
record("hotfix4-removes-gallery-iwindow-inheritance", "public partial class MainWindow : FluentWindow" in main_cs and "FluentWindow, IWindow" not in main_cs)
record("hotfix4-does-not-invent-iwindow-interface", "interface IWindow" not in main_cs and "AddSingleton<IWindow" not in app_cs)
record("hotfix4-api-audit-evidence-present", (ROOT / "evidence" / "WPF_UI_4_3_API_AUDIT_20260830.md").is_file())

# Regression for the real Win11 Hotfix 5A lifecycle gate: after the Hotfix 4
# candidate compiled and Setup installed UX5.0, a normal-close hard gate was
# required. The custom HwndSource/WM_CLOSE hook kept the process alive beyond 5s
# when Process.CloseMainWindow() was used, and OnExit/ProcessExit could
# double-cleanup the DI container.
main_cs5 = (ROOT / "shell" / "ProjectFactory.Workbench" / "MainWindow.xaml.cs").read_text(encoding="utf-8-sig")
app_cs5 = (ROOT / "shell" / "ProjectFactory.Workbench" / "App.xaml.cs").read_text(encoding="utf-8-sig")
bridge_cs5 = (ROOT / "shell" / "ProjectFactory.Workbench" / "Services" / "PythonBridgeClient.cs").read_text(encoding="utf-8-sig")
record("gate5-mainwindow-no-hwndsource-hook", not re.search(r"new\s+HwndSource|\.AddHook\s*\(|FromHwnd", main_cs5))
record("gate5-mainwindow-fix-comment-present", "Gate 5 fix (Hotfix 5A)" in main_cs5)
record("gate5-app-shutdown-mode-on-mainwindow-close", "ShutdownMode = ShutdownMode.OnMainWindowClose" in app_cs5)
record("gate5-app-idempotent-cleanup", "Interlocked.CompareExchange(ref _cleanupDone, 1, 0)" in app_cs5)
record("gate5-app-no-double-cleanup-path", "OnProcessExit" in app_cs5 and "OnExit" in app_cs5 and "Cleanup()" in app_cs5)
record("gate5-bridge-shutdownasync-exists", "public async Task ShutdownAsync(TimeSpan timeout)" in bridge_cs5)
gate5_test_src = (ROOT / "tools" / "test_lifecycle_gate5.py").read_text(encoding="utf-8-sig") if (ROOT / "tools" / "test_lifecycle_gate5.py").is_file() else ""
record("gate5-hard-gate-test-implements-predicate", (ROOT / "tools" / "test_lifecycle_gate5.py").is_file()
       and "gate5_normal_close_pass" in gate5_test_src
       and "app_exited_before_fallback" in gate5_test_src
       and "close_request_succeeded" in gate5_test_src)
record("gate5-live-bridge-required", "live_bridge_observed" in gate5_test_src and "live_bridge_not_observed" in gate5_test_src and ".pf_runtime" in gate5_test_src)
record("gate5-fallback-never-converts-to-pass", "will NOT convert to PASS" in gate5_test_src and "EMERGENCY_CLEANUP" in gate5_test_src)
record("gate5-hard-gate-doc-present", (ROOT / "04_NORMAL_CLOSE_HARD_GATE.md").is_file())

result = {
    "schema": "project-factory-ux5-build-gate-regression/1",
    "status": "PASS" if not failures else "FAIL",
    "checks": checks,
    "failures": failures,
    "limitations": [
        "This regression test does not execute Windows PowerShell, dotnet publish, WPF rendering, or NSIS.",
        "The target-Windows build/lifecycle gate remains required."
    ],
}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(0 if not failures else 1)

@echo off
setlocal
cd /d "%~dp0"

set "LOGDIR=%~dp0logs"
set "PREFLIGHT_LOG=%LOGDIR%\build-preflight.log"
set "BUILD_LOG=%LOGDIR%\build.log"
set "PF_BUILD_SCRIPT=%~dp0BUILD_INSTALLER.ps1"

if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
if not exist "%LOGDIR%" (
  echo [FATAL] Cannot create installer log directory: "%LOGDIR%"
  exit /b 91
)

> "%PREFLIGHT_LOG%" echo Project Factory UX5 build preflight
>> "%PREFLIGHT_LOG%" echo Script: %PF_BUILD_SCRIPT%

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$tokens=$null; $errors=$null; $null = [System.Management.Automation.Language.Parser]::ParseFile($env:PF_BUILD_SCRIPT,[ref]$tokens,[ref]$errors); if ($errors.Count -gt 0) { foreach ($e in $errors) { Write-Output ('[PARSE-ERROR] ' + $e.Message + ' @ line ' + $e.Extent.StartLineNumber + ', column ' + $e.Extent.StartColumnNumber) }; exit 90 }; Write-Output '[OK] PowerShell parser preflight passed.'" >> "%PREFLIGHT_LOG%" 2>&1
set "PRE_RC=%ERRORLEVEL%"
type "%PREFLIGHT_LOG%"
if not "%PRE_RC%"=="0" (
  copy /y "%PREFLIGHT_LOG%" "%BUILD_LOG%" >nul
  echo.
  echo Build preflight failed. Full log: installer\logs\build.log
  exit /b %PRE_RC%
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PF_BUILD_SCRIPT%"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Build failed. Full log: installer\logs\build.log
if "%RC%"=="0" echo Build completed. Full log: installer\logs\build.log
exit /b %RC%

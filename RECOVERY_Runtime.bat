@echo off
setlocal
cd /d "%~dp0"
echo Project Factory - Python Core runtime recovery
where py.exe >nul 2>nul
if %errorlevel%==0 (
  py.exe -3 "%~dp0bootstrap_windows.py" --prepare-only --source auto --connection direct
) else (
  python.exe "%~dp0bootstrap_windows.py" --prepare-only --source auto --connection direct
)
echo.
echo Recovery finished with exit code %errorlevel%.
pause
param(
    [Parameter(Mandatory=$true)][string]$TargetDir
)

$ErrorActionPreference = 'SilentlyContinue'

if ([string]::IsNullOrWhiteSpace($TargetDir)) { return }

$tgt = [System.IO.Path]::GetFullPath($TargetDir).TrimEnd('\')
if (-not (Test-Path -LiteralPath $tgt)) { return }

$myPid = $PID
$parentPid = 0
try {
    $parentPid = (Get-CimInstance Win32_Process -Filter "ProcessId = $PID" -ErrorAction SilentlyContinue).ParentProcessId
} catch { }

$all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
$owned = @($all | Where-Object {
    $pidNum = $_.ProcessId
    if ($pidNum -eq $myPid -or $pidNum -eq $parentPid) { return $false }
    $exe = [string]$_.ExecutablePath
    $cmd = [string]$_.CommandLine
    $isExcluded = $exe -and (
        $exe.EndsWith('powershell.exe', [System.StringComparison]::OrdinalIgnoreCase) -or
        $exe.EndsWith('pwsh.exe', [System.StringComparison]::OrdinalIgnoreCase) -or
        $exe.EndsWith('cmd.exe', [System.StringComparison]::OrdinalIgnoreCase) -or
        $exe.EndsWith('explorer.exe', [System.StringComparison]::OrdinalIgnoreCase) -or
        $exe.EndsWith('Uninstall.exe', [System.StringComparison]::OrdinalIgnoreCase)
    )
    if ($isExcluded) { return $false }
    $isInside = $exe -and $exe.StartsWith($tgt, [System.StringComparison]::OrdinalIgnoreCase)
    $isChild = $cmd -and ($cmd.IndexOf($tgt, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
    $isInside -or $isChild
})

foreach ($p in $owned) {
    try {
        $proc = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
        if ($proc -and -not $proc.HasExited) {
            if ($proc.MainWindowHandle -ne 0) {
                [void]$proc.CloseMainWindow()
                Start-Sleep -Milliseconds 400
            }
            if (-not $proc.HasExited) {
                Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            }
        }
    } catch { }
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
while ($sw.ElapsedMilliseconds -lt 3000) {
    $rem = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $pidNum = $_.ProcessId
        if ($pidNum -eq $myPid -or $pidNum -eq $parentPid) { return $false }
        $exe = [string]$_.ExecutablePath
        $exe -and $exe.StartsWith($tgt, [System.StringComparison]::OrdinalIgnoreCase) -and 
            (-not $exe.EndsWith('explorer.exe', [System.StringComparison]::OrdinalIgnoreCase)) -and
            (-not $exe.EndsWith('Uninstall.exe', [System.StringComparison]::OrdinalIgnoreCase)) -and
            (-not $exe.EndsWith('powershell.exe', [System.StringComparison]::OrdinalIgnoreCase)) -and
            (-not $exe.EndsWith('pwsh.exe', [System.StringComparison]::OrdinalIgnoreCase))
    })
    if ($rem.Count -eq 0) { break }
    Start-Sleep -Milliseconds 200
}

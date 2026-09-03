[CmdletBinding()]
param(
    [string]$DotnetSdkZip = "",
    [string]$NsisZip = "",
    [switch]$NoDownload
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# We implement our own Get-FileHash function using standard .NET cryptography classes.
# This avoids PowerShell cmdlet lookup errors on custom/headless build agent environments.
function Get-FileHash {
    param(
        [string]$LiteralPath,
        [string]$Algorithm
    )
    $stream = [System.IO.File]::OpenRead($LiteralPath)
    try {
        $hasher = if ($Algorithm -eq 'SHA512') {
            [System.Security.Cryptography.SHA512]::Create()
        } else {
            [System.Security.Cryptography.SHA256]::Create()
        }
        $hashBytes = $hasher.ComputeHash($stream)
        $hashString = [System.BitConverter]::ToString($hashBytes).Replace('-', '')
        return [pscustomobject]@{
            Hash = $hashString
        }
    }
    finally {
        $stream.Close()
    }
}

# Canonical log stays on the physical project path. Hotfix 5C builds on the
# physical bundle root (dotnet CLI \\?\ writes fail on SUBST virtual drives).
$PhysicalInstallerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PhysicalBundleRoot = Split-Path -Parent $PhysicalInstallerRoot
$PhysicalLogDir = Join-Path $PhysicalInstallerRoot 'logs'
$Log = Join-Path $PhysicalLogDir 'build.log'

$DotnetVersion = '10.0.400'
$DotnetFile = "dotnet-sdk-$DotnetVersion-win-x64.zip"
$ExpectedDotnetSha512 = '9b8b88590e4da131bfd0da7aa089d0fc04d5418d5f8607ec13d55dc5a17b4399afd54d496c12657fa05c6c6546dc5eab930f26ac6c50f2d3a7712c0fb378c366'
$DotnetUrls = @(
    "https://builds.dotnet.microsoft.com/dotnet/Sdk/$DotnetVersion/$DotnetFile",
    "https://dotnetcli.azureedge.net/dotnet/Sdk/$DotnetVersion/$DotnetFile",
    'https://aka.ms/dotnet/10.0/dotnet-sdk-win-x64.zip'
)

$ExpectedNsisSha256 = '56581f90db321581c5381193d796fffcf2d24b2f8fed2160a6c6a3baa67f2c4f'
$NsisUrls = @(
    'https://downloads.sourceforge.net/project/nsis/NSIS%203/3.12/nsis-3.12.zip',
    'https://sourceforge.net/projects/nsis/files/NSIS%203/3.12/nsis-3.12.zip/download'
)

$NugetSources = @(
    @{ Name = 'Microsoft China'; Url = 'https://nuget.cdn.azure.cn/v3/index.json' },
    @{ Name = 'NuGet.org'; Url = 'https://api.nuget.org/v3/index.json' },
    @{ Name = 'Huawei Cloud fallback'; Url = 'https://repo.huaweicloud.com/repository/nuget/v3/index.json' }
)

New-Item -ItemType Directory -Force -Path $PhysicalLogDir | Out-Null
Set-Content -LiteralPath $Log -Value "Project Factory UX5 build $(Get-Date -Format s)" -Encoding UTF8

$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:DOTNET_NOLOGO = '1'
$env:DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER = '1'
$env:MSBUILDDISABLENODEREUSE = '1'

function Stop-BundleOwnedBuildProcesses {
    param(
        [string]$MappedRoot,
        [string]$PhysicalRoot,
        [string]$DotnetExe
    )
    if (-not [string]::IsNullOrWhiteSpace($DotnetExe) -and (Test-Path -LiteralPath $DotnetExe)) {
        try {
            $null = Invoke-NativeCapture -FilePath $DotnetExe -ArgumentList @('build-server', 'shutdown')
        }
        catch { }
    }

    $roots = @()
    if (-not [string]::IsNullOrWhiteSpace($MappedRoot)) { $roots += [IO.Path]::GetFullPath($MappedRoot).TrimEnd('\') }
    if (-not [string]::IsNullOrWhiteSpace($PhysicalRoot)) { $roots += [IO.Path]::GetFullPath($PhysicalRoot).TrimEnd('\') }
    if ($roots.Count -eq 0) { return }

    try {
        $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Select-Object ProcessId, ExecutablePath, CommandLine)
        $currentPid = $PID
        foreach ($p in $all) {
            if ($p.ProcessId -eq $currentPid) { continue }
            $exe = [string]$p.ExecutablePath
            $cmd = [string]$p.CommandLine
            if ($exe -and $exe.EndsWith('explorer.exe', [StringComparison]::OrdinalIgnoreCase)) { continue }

            $isOwned = $false
            foreach ($root in $roots) {
                if (($exe -and $exe.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) -or
                    ($cmd -and $cmd.IndexOf($root, [StringComparison]::OrdinalIgnoreCase) -ge 0)) {
                    $isOwned = $true
                    break
                }
            }
            if ($isOwned) {
                try {
                    $proc = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
                    if ($proc -and -not $proc.HasExited) {
                        $proc.Kill($true)
                    }
                }
                catch { }
            }
        }
    }
    catch { }
}

function Write-Step([string]$Text) {
    Write-Host $Text
    Add-Content -LiteralPath $Log -Value $Text -Encoding UTF8
}

function Write-Fatal([System.Management.Automation.ErrorRecord]$Record) {
    $message = "[FATAL] $($Record.Exception.Message)"
    Write-Step $message
    $details = ($Record | Out-String).TrimEnd()
    if (-not [string]::IsNullOrWhiteSpace($details)) {
        Add-Content -LiteralPath $Log -Value $details -Encoding UTF8
    }
}

function Invoke-NativeCapture {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList = @()
    )

    # Windows PowerShell 5.1 can surface native stderr as NativeCommandError.
    # Temporarily use Continue so the caller, not ErrorActionPreference, owns
    # the native process exit-code decision and can perform bounded failover.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $lines = @(& $FilePath @ArgumentList 2>&1)
        $rc = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    return [pscustomobject]@{
        ExitCode = $rc
        Lines = $lines
    }
}

function Invoke-NativeLogged {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList = @()
    )

    $result = Invoke-NativeCapture -FilePath $FilePath -ArgumentList $ArgumentList
    foreach ($entry in $result.Lines) {
        $text = ($entry | Out-String).TrimEnd()
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            Write-Host $text
            Add-Content -LiteralPath $Log -Value $text -Encoding UTF8
        }
    }
    return [int]$result.ExitCode
}

function Resolve-ProjectFactoryNugetCache {
    param([string]$PhysicalRoot)

    # Automatic, drive-letter-agnostic, Project Factory-owned short NuGet cache.
    # Does not hard-code a user profile, machine name, or a fixed drive-root cache name.
    # Never deletes other projects' caches. Retained across builds; delete the
    # chosen directory manually if disk must be reclaimed.
    $driveRoot = [IO.Path]::GetPathRoot($PhysicalRoot)
    if ([string]::IsNullOrWhiteSpace($driveRoot)) {
        $driveRoot = [IO.Path]::GetPathRoot((Get-Location).Path)
    }
    $driveRoot = $driveRoot.TrimEnd('\')
    $tempRoot = [IO.Path]::GetTempPath().TrimEnd('\')
    $candidates = @(
        (Join-Path $driveRoot '.projectfactory\nuget-packages'),
        (Join-Path $tempRoot 'projectfactory-nuget-packages')
    )

    foreach ($candidate in $candidates) {
        try {
            if ($candidate.Length -ge 120) {
                Write-Step "[NUGET-CACHE-SKIP] $candidate (path too long: $($candidate.Length))"
                continue
            }
            $null = New-Item -ItemType Directory -Force -Path $candidate -ErrorAction Stop
            $probe = Join-Path $candidate '.pf_write_probe'
            Set-Content -LiteralPath $probe -Value 'ok' -Encoding ASCII -ErrorAction Stop
            Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
            Write-Step "[NUGET-CACHE-PATH] Using Project Factory NuGet cache: $candidate"
            Write-Step "[NUGET-CACHE-POLICY] retain-across-builds; Project-Factory-owned only; not cleaned automatically; other NuGet caches are never deleted"
            return $candidate
        }
        catch {
            Write-Step "[NUGET-CACHE-SKIP] $candidate ($($_.Exception.Message))"
        }
    }

    throw "Could not allocate a writable short Project Factory NuGet cache. Tried: $($candidates -join ', ')"
}

function Download-WithFailover {
    param([string[]]$Urls, [string]$Destination, [string]$Label)
    $last = $null
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    foreach ($url in $Urls) {
        try {
            Write-Step "[DOWNLOAD] $Label <- $url"
            $downloaded = $false
            if ($curl) {
                $curlResult = Invoke-NativeCapture -FilePath $curl.Source -ArgumentList @('-fL', '-sS', '--connect-timeout', '15', '--max-time', '120', '-o', $Destination, $url)
                if ($curlResult.ExitCode -eq 0 -and (Test-Path -LiteralPath $Destination) -and (Get-Item -LiteralPath $Destination).Length -gt 0) {
                    $downloaded = $true
                }
            }
            if (-not $downloaded) {
                Invoke-WebRequest -Uri $url -OutFile $Destination -UseBasicParsing -UserAgent 'curl/8.0' -TimeoutSec 90
                if ((Get-Item -LiteralPath $Destination).Length -le 0) { throw 'downloaded file is empty' }
            }
            return
        }
        catch {
            $last = $_
            Write-Step "[DOWNLOAD-FAILED] $($_.Exception.Message)"
            Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
        }
    }
    throw "All download routes failed for $Label. Last error: $last"
}

function Expand-ZipReliable {
    param([string]$ZipPath, [string]$Destination, [string]$Label)

    # The destination is owned by this extraction attempt. Keeping extraction
    # isolated lets us retry/fallback without touching verified archives or
    # unrelated tool caches.
    Remove-Item -LiteralPath $Destination -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($tar) {
        Write-Step "[EXTRACT] $Label via Windows tar.exe -> $Destination"
        $tarExit = Invoke-NativeLogged -FilePath $tar.Source -ArgumentList @('-xf', $ZipPath, '-C', $Destination)
        if ($tarExit -eq 0) {
            Write-Step "[EXTRACT-OK] $Label via Windows tar.exe"
            return 'tar.exe'
        }
        Write-Step "[EXTRACT-FAILED] Windows tar.exe exit=$tarExit; retrying with System.IO.Compression.ZipFile."
        Remove-Item -LiteralPath $Destination -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    }
    else {
        Write-Step "[EXTRACT] Windows tar.exe not found; using System.IO.Compression.ZipFile fallback for $Label."
    }

    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop
        [System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $Destination)
        Write-Step "[EXTRACT-OK] $Label via System.IO.Compression.ZipFile"
        return 'ZipFile'
    }
    catch {
        throw "$Label extraction failed with both supported extractors. Last error: $($_.Exception.Message)"
    }
}

function Get-Dotnet {
    $system = Get-Command dotnet.exe -ErrorAction SilentlyContinue
    if ($system) {
        $sdkProbe = Invoke-NativeCapture -FilePath $system.Source -ArgumentList @('--list-sdks')
        $versions = @($sdkProbe.Lines | ForEach-Object { ($_ | Out-String).Trim() })
        if ($sdkProbe.ExitCode -eq 0 -and $versions -match "^$([regex]::Escape($DotnetVersion))\s") {
            Write-Step "[OK] Using installed .NET SDK ${DotnetVersion}: $($system.Source)"
            return $system.Source
        }
    }

    $zipPath = $DotnetSdkZip
    if ([string]::IsNullOrWhiteSpace($zipPath)) { $zipPath = Join-Path $Tooling $DotnetFile }
    if (-not (Test-Path -LiteralPath $zipPath)) {
        if ($NoDownload) { throw ".NET SDK ZIP not found: $zipPath" }
        Download-WithFailover -Urls $DotnetUrls -Destination $zipPath -Label ".NET SDK $DotnetVersion x64"
    }
    $actual = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA512).Hash.ToLowerInvariant()
    if ($actual -ne $ExpectedDotnetSha512) {
        throw ".NET SDK SHA512 mismatch. Expected $ExpectedDotnetSha512, got $actual"
    }
    Write-Step '[OK] .NET SDK SHA512 verified.'

    $extractRoot = Join-Path $Tooling "dotnet-$DotnetVersion"
    $dotnet = Join-Path $extractRoot 'dotnet.exe'
    if (-not (Test-Path -LiteralPath $dotnet)) {
        $extractor = Expand-ZipReliable -ZipPath $zipPath -Destination $extractRoot -Label ".NET SDK $DotnetVersion x64"
        if (-not (Test-Path -LiteralPath $dotnet)) {
            throw ".NET SDK extraction completed via $extractor but dotnet.exe is missing: $dotnet"
        }
    }

    Write-Step "[DOTNET-PROBE] Executable path length=$($dotnet.Length); running --info and --version."
    $infoResult = Invoke-NativeCapture -FilePath $dotnet -ArgumentList @('--info')
    $dotnetInfo = (@($infoResult.Lines | ForEach-Object { $_ | Out-String }) -join '').TrimEnd()
    if ($infoResult.ExitCode -ne 0) { throw "Portable dotnet --info failed with exit=$($infoResult.ExitCode)`n$dotnetInfo" }
    if (-not [string]::IsNullOrWhiteSpace($dotnetInfo)) { Add-Content -LiteralPath $Log -Value $dotnetInfo -Encoding UTF8 }

    $versionResult = Invoke-NativeCapture -FilePath $dotnet -ArgumentList @('--version')
    $version = (@($versionResult.Lines | ForEach-Object { ($_ | Out-String).Trim() }) -join '').Trim()
    if ($versionResult.ExitCode -ne 0) { throw "Portable dotnet --version failed with exit=$($versionResult.ExitCode)" }
    if ($version -ne $DotnetVersion) { throw "Unexpected dotnet version: $version" }
    Write-Step "[OK] Portable .NET SDK ready: $dotnet"
    return $dotnet
}

function Restore-Shell([string]$Dotnet) {
    $last = $null
    foreach ($source in $NugetSources) {
        Write-Step "[NUGET] Trying $($source.Name): $($source.Url)"
        $restoreArgs = @('restore', $ShellProject, '-r', 'win-x64', '--packages', $NugetCache, '--source', $source.Url, '--disable-parallel', '--force')
        $restoreExit = Invoke-NativeLogged -FilePath $Dotnet -ArgumentList $restoreArgs
        if ($restoreExit -eq 0) {
            Write-Step "[NUGET-OK] $($source.Name)"
            return $source.Name
        }
        $last = $restoreExit
        Write-Step "[NUGET-FAILED] $($source.Name), exit=$restoreExit. Switching source."
    }
    throw "NuGet restore failed on every configured source. Last exit=$last. See $Log"
}

function Get-Nsis {
    $zipPath = $NsisZip
    if ([string]::IsNullOrWhiteSpace($zipPath)) { $zipPath = Join-Path $Tooling 'nsis-3.12.zip' }
    if (Test-Path -LiteralPath $zipPath) {
        $existingHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($existingHash -ne $ExpectedNsisSha256) {
            Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
        }
    }
    if (-not (Test-Path -LiteralPath $zipPath)) {
        if ($NoDownload) { throw "NSIS 3.12 ZIP not found: $zipPath" }
        Download-WithFailover -Urls $NsisUrls -Destination $zipPath -Label 'NSIS 3.12'
    }
    $actual = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $ExpectedNsisSha256) { throw "NSIS SHA256 mismatch. Expected $ExpectedNsisSha256, got $actual" }
    Write-Step '[OK] NSIS 3.12 SHA256 verified.'
    $extractRoot = Join-Path $Tooling 'nsis-3.12'
    $makensis = Join-Path $extractRoot 'makensis.exe'
    if (-not (Test-Path -LiteralPath $makensis)) {
        $staging = Join-Path $Tooling 'nsis-3.12-extract-staging'
        try {
            $extractor = Expand-ZipReliable -ZipPath $zipPath -Destination $staging -Label 'NSIS 3.12'
            $stagedRoot = Join-Path $staging 'nsis-3.12'
            $stagedMakensis = Join-Path $stagedRoot 'makensis.exe'
            if (-not (Test-Path -LiteralPath $stagedMakensis)) {
                throw "NSIS extraction completed via $extractor but makensis.exe is missing: $stagedMakensis"
            }
            Remove-Item -LiteralPath $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
            Move-Item -LiteralPath $stagedRoot -Destination $extractRoot
        }
        finally {
            Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    if (-not (Test-Path -LiteralPath $makensis)) { throw 'makensis.exe missing after NSIS extraction.' }
    return $makensis
}

$dotnet = $null
$exitCode = 1
$BundleRoot = $PhysicalBundleRoot.TrimEnd('\')
try {
    Write-Step "[PRECHECK] Build script started; log=$Log"
    Write-Step "[PATH] Physical bundle root: $PhysicalBundleRoot"
    Write-Step "[BUILD-MODEL] physical-path + bounded Project Factory NuGet cache (no SUBST; dotnet \\?\ writes fail on SUBST)"

    $InstallerRoot = Join-Path $BundleRoot 'installer'
    $ShellProject = Join-Path $BundleRoot 'shell\ProjectFactory.Workbench\ProjectFactory.Workbench.csproj'
    $Build = Join-Path $InstallerRoot 'build'
    $Dist = Join-Path $InstallerRoot 'dist'
    $Publish = Join-Path $InstallerRoot 'publish'
    $Tooling = Join-Path $InstallerRoot '.tooling'
    $NugetCache = Resolve-ProjectFactoryNugetCache -PhysicalRoot $PhysicalBundleRoot

    New-Item -ItemType Directory -Force -Path $Build, $Dist, $Publish, $Tooling | Out-Null
    New-Item -ItemType Directory -Force -Path $NugetCache | Out-Null
    $env:NUGET_PACKAGES = $NugetCache

    $runtimeProbe = Join-Path $Tooling 'dotnet-10.0.400\shared\Microsoft.NETCore.App\10.0.11\Microsoft.NETCore.App.deps.json'
    Write-Step "[PATH-BUDGET] physical bundle=$BundleRoot; runtime probe length=$($runtimeProbe.Length); nuget cache length=$($NugetCache.Length)"
    if ($runtimeProbe.Length -ge 240) {
        throw "Physical build root is too deep for MAX_PATH headroom. Extract the bundle closer to a drive root. Probe length=$($runtimeProbe.Length)"
    }
    if (-not (Test-Path -LiteralPath $ShellProject)) { throw "WPF project missing: $ShellProject" }

    $dotnet = Get-Dotnet
    $nugetSource = Restore-Shell -Dotnet $dotnet

    Write-Step '[BUILD 1/2] Publishing self-contained Win11 Fluent WPF shell.'
    Remove-Item -LiteralPath $Publish -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $Publish | Out-Null
    $publishArgs = @('publish', $ShellProject, '-c', 'Release', '-r', 'win-x64', '--self-contained', 'true', '--no-restore', '-p:PublishSingleFile=false', '-p:PublishTrimmed=false', '-p:PublishReadyToRun=false', '-p:UseSharedCompilation=false', '-p:NodeReuse=false', '-o', $Publish)
    $publishExit = Invoke-NativeLogged -FilePath $dotnet -ArgumentList $publishArgs
    if ($publishExit -ne 0) { throw "WPF publish failed: $publishExit" }
    $exe = Join-Path $Publish 'ProjectFactory.exe'
    $dll = Join-Path $Publish 'ProjectFactory.dll'
    if (-not (Test-Path -LiteralPath $exe) -or -not (Test-Path -LiteralPath $dll)) { throw 'Published WPF shell is incomplete.' }
    Write-Step "[OK] WPF shell published; NuGet route=$nugetSource"

    $makensis = Get-Nsis
    Push-Location $InstallerRoot
    try {
        Write-Step '[BUILD 2/2] Building NSIS / Modern UI 2 installer.'
        $nsisExit = Invoke-NativeLogged -FilePath $makensis -ArgumentList @('/V4', 'ProjectFactoryInstaller.nsi')
        if ($nsisExit -ne 0) { throw "Installer compilation failed: $nsisExit" }
    }
    finally { Pop-Location }

    $setup = Join-Path $Dist 'ProjectFactory-Setup-0.14.30-UX5.1.exe'
    if (-not (Test-Path -LiteralPath $setup)) { throw "Missing setup: $setup" }
    $setupHash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
    $rootSetup = Join-Path $BundleRoot 'ProjectFactory-Setup-0.14.30-UX5.1.exe'
    Copy-Item -LiteralPath $setup -Destination $rootSetup -Force
    # Keep legacy aliases for baseline checks
    Copy-Item -LiteralPath $setup -Destination (Join-Path $BundleRoot 'ProjectFactory-Setup-0.14.28-UX5.1.exe') -Force -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath $setup -Destination (Join-Path $BundleRoot 'ProjectFactory-Setup-0.14.1-UX5.1.exe') -Force -ErrorAction SilentlyContinue
    Set-Content -LiteralPath (Join-Path $BundleRoot 'ProjectFactory-Setup-0.14.30-UX5.1_SHA256.txt') -Value ("$setupHash  ProjectFactory-Setup-0.14.30-UX5.1.exe") -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $BundleRoot 'ProjectFactory-Setup-0.14.28-UX5.1_SHA256.txt') -Value ("$setupHash  ProjectFactory-Setup-0.14.30-UX5.1.exe (alias)") -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $BundleRoot 'ProjectFactory-Setup-0.14.1-UX5.1_SHA256.txt') -Value ("$setupHash  ProjectFactory-Setup-0.14.30-UX5.1.exe (alias)") -Encoding ASCII
    Write-Step "[READY] $rootSetup"
    Write-Step "[SHA256] $setupHash"
    $exitCode = 0
}
catch {
    Write-Fatal $_
    Write-Host "Build failed. Full log: $Log"
    $exitCode = 1
}
finally {
    try {
        Stop-BundleOwnedBuildProcesses -MappedRoot $BundleRoot -PhysicalRoot $PhysicalBundleRoot -DotnetExe $dotnet
        Write-Step "[BUILD-CLEANUP] Stopped Project Factory owned build processes; NuGet cache retained"
    }
    catch { }
}

exit $exitCode

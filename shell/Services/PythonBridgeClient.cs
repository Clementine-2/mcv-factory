using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;

namespace ProjectFactory.Workbench.Services;

public sealed class PythonBridgeClient : IAsyncDisposable, IDisposable
{
    private readonly string _installRoot;
    private readonly string _pythonExe;
    private readonly string _bridgeScript;
    private readonly string _logPath;
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly ConcurrentDictionary<int, Process> _activeProcesses = new();
    private readonly CancellationTokenSource _shutdownCts = new();
    private IntPtr _jobHandle = IntPtr.Zero;
    private bool _disposed;

    // F5: resident backend process — one long-lived python.exe reused for every call
    // instead of cold-starting a new process per bridge invocation (the root cause of UI lag).
    private readonly SemaphoreSlim _residentGate = new(1, 1);
    private Process? _residentProcess;
    private StreamWriter? _residentStdIn;
    private Task? _residentReader;
    private readonly ConcurrentDictionary<int, TaskCompletionSource<JsonElement>> _pending = new();
    private int _nextRequestId;

    public PythonBridgeClient()
    {
        _installRoot = ResolveInstallRoot();
        _pythonExe = Path.Combine(_installRoot, ".pf_runtime", "Scripts", "python.exe");
        _bridgeScript = Path.Combine(_installRoot, "backend", "project_factory_bridge.py");
        var logRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ProjectFactory", "logs");
        Directory.CreateDirectory(logRoot);
        _logPath = Path.Combine(logRoot, "bridge.log");

        if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            try
            {
                _jobHandle = CreateKillOnCloseJobObject();
            }
            catch (Exception ex)
            {
                Log($"WARN failed to initialize Windows JobObject: {ex.Message}");
            }
        }
    }

    public async Task<JsonElement> InvokeAsync(string action, object? payload = null, CancellationToken cancellationToken = default)
    {
        if (_disposed || _shutdownCts.IsCancellationRequested)
            throw new ObjectDisposedException(nameof(PythonBridgeClient), "基地车工厂 正在退出。");

        if (!File.Exists(_pythonExe))
            throw new FileNotFoundException("基地车工厂 私有 Python Core 运行时缺失。请运行安装器 Repair/重新安装。", _pythonExe);
        if (!File.Exists(_bridgeScript))
            throw new FileNotFoundException("基地车工厂 backend bridge 缺失。", _bridgeScript);

        using var timeoutCts = new CancellationTokenSource(TimeSpan.FromMinutes(6));
        using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token, timeoutCts.Token);
        var token = linkedCts.Token;

        // F5: lazily start (and reuse) a single long-lived backend process.
        await EnsureResidentProcessAsync(token).ConfigureAwait(false);

        var id = Interlocked.Increment(ref _nextRequestId);
        var tcs = new TaskCompletionSource<JsonElement>(TaskCreationOptions.RunContinuationsAsynchronously);
        _pending[id] = tcs;

        try
        {
            var request = JsonSerializer.Serialize(new { id, action, payload = payload ?? new { } }, JsonOptions);
            Log($"SEND id={id} action={action}");
            await _residentStdIn!.WriteLineAsync(request.AsMemory(), token).ConfigureAwait(false);
            await _residentStdIn.FlushAsync(token).ConfigureAwait(false);

            using (token.Register(() => tcs.TrySetCanceled()))
            {
                try
                {
                    return await tcs.Task.ConfigureAwait(false);
                }
                catch (OperationCanceledException) when (_shutdownCts.IsCancellationRequested)
                {
                    Log($"SHUTDOWN id={id} action={action}");
                    throw new OperationCanceledException("基地车工厂 正在退出，后台进程已终止。");
                }
                catch (OperationCanceledException)
                {
                    Log($"TIMEOUT id={id} action={action}");
                    throw new TimeoutException($"{action} 超过允许的最长执行时间，后台进程已终止。日志：{_logPath}");
                }
            }
        }
        finally
        {
            _pending.TryRemove(id, out _);
        }
    }

    public async Task ShutdownAsync(TimeSpan timeout)
    {
        if (_disposed) return;
        _disposed = true;

        try
        {
            _shutdownCts.Cancel();
        }
        catch { }

        var proc = _residentProcess;
        if (proc is not null)
        {
            // Signal EOF to the resident protocol by closing stdin; the bridge loop exits on its own.
            try { _residentStdIn?.Dispose(); } catch { }
            try { proc.StandardInput.Close(); } catch { }

            var sw = Stopwatch.StartNew();
            while (!proc.HasExited && sw.Elapsed < timeout)
                await Task.Delay(50).ConfigureAwait(false);
            if (!proc.HasExited)
            {
                try { proc.Kill(entireProcessTree: true); Log("SHUTDOWN force-killed resident bridge"); }
                catch (Exception ex) { Log($"SHUTDOWN kill resident failed: {ex.Message}"); }
            }
            else
            {
                Log($"SHUTDOWN resident exited code={proc.ExitCode}");
            }
        }

        // Any straggler processes (shouldn't happen with the resident model).
        foreach (var p in _activeProcesses.Values)
        {
            try { if (!p.HasExited) p.Kill(entireProcessTree: true); } catch { }
        }
        _activeProcesses.Clear();

        if (_jobHandle != IntPtr.Zero)
        {
            try { CloseHandle(_jobHandle); } catch { }
            _jobHandle = IntPtr.Zero;
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        try
        {
            _shutdownCts.Cancel();
        }
        catch { }

        var proc = _residentProcess;
        if (proc is not null)
        {
            try { _residentStdIn?.Dispose(); } catch { }
            try { proc.StandardInput.Close(); } catch { }
            if (!proc.HasExited)
            {
                try { proc.Kill(entireProcessTree: true); } catch { }
            }
        }
        foreach (var p in _activeProcesses.Values)
        {
            try { if (!p.HasExited) p.Kill(entireProcessTree: true); } catch { }
        }
        _activeProcesses.Clear();

        if (_jobHandle != IntPtr.Zero)
        {
            try { CloseHandle(_jobHandle); } catch { }
            _jobHandle = IntPtr.Zero;
        }

        try
        {
            _shutdownCts.Dispose();
        }
        catch { }
    }

    public async ValueTask DisposeAsync()
    {
        await ShutdownAsync(TimeSpan.FromSeconds(2)).ConfigureAwait(false);
        try
        {
            _shutdownCts.Dispose();
        }
        catch { }
    }

    private void TryAssignToJob(Process process)
    {
        if (_jobHandle != IntPtr.Zero && RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            try
            {
                if (!process.HasExited)
                {
                    AssignProcessToJobObject(_jobHandle, process.Handle);
                }
            }
            catch { }
        }
    }

    private static IntPtr CreateKillOnCloseJobObject()
    {
        var hJob = CreateJobObject(IntPtr.Zero, null);
        if (hJob == IntPtr.Zero) return IntPtr.Zero;

        var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            BasicLimitInformation = new JOBOBJECT_BASIC_LIMIT_INFORMATION
            {
                LimitFlags = 0x2000 // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            }
        };

        var length = (uint)Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
        var ptr = Marshal.AllocHGlobal((int)length);
        try
        {
            Marshal.StructureToPtr(info, ptr, false);
            if (!SetInformationJobObject(hJob, 9 /* JobObjectExtendedLimitInformation */, ptr, length))
            {
                CloseHandle(hJob);
                return IntPtr.Zero;
            }
        }
        finally
        {
            Marshal.FreeHGlobal(ptr);
        }

        return hJob;
    }

    private static string ResolveInstallRoot()
    {
        var overrideRoot = Environment.GetEnvironmentVariable("PROJECT_FACTORY_ROOT");
        if (!string.IsNullOrWhiteSpace(overrideRoot) && Directory.Exists(overrideRoot)) return Path.GetFullPath(overrideRoot);

        var current = new DirectoryInfo(AppContext.BaseDirectory);
        for (var i = 0; i < 8 && current is not null; i++, current = current.Parent)
        {
            if (Directory.Exists(Path.Combine(current.FullName, "backend")) && Directory.Exists(Path.Combine(current.FullName, "wheel")))
                return current.FullName;
        }
        // Installed layout is <root>\app\ProjectFactory.exe.
        var baseDir = new DirectoryInfo(AppContext.BaseDirectory);
        return baseDir.Parent?.FullName ?? AppContext.BaseDirectory;
    }

    private void Log(string line)
    {
        try { File.AppendAllText(_logPath, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {line}{Environment.NewLine}"); } catch { }
    }

    private static string Compact(string value)
    {
        var text = (value ?? "").Replace("\r", " ").Replace("\n", " ").Trim();
        return text.Length <= 280 ? text : text[..280] + "…";
    }

    // ---- F5: resident backend process ------------------------------------------------

    private async Task EnsureResidentProcessAsync(CancellationToken token)
    {
        if (_residentProcess is { HasExited: false } && _residentStdIn is not null)
            return;

        await _residentGate.WaitAsync(token).ConfigureAwait(false);
        try
        {
            // Re-check after acquiring the gate (another caller may have started it).
            if (_residentProcess is { HasExited: false } && _residentStdIn is not null)
                return;

            await DisposeResidentProcessAsync().ConfigureAwait(false);

            var psi = new ProcessStartInfo
            {
                FileName = _pythonExe,
                Arguments = $"\"{_bridgeScript}\"",
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                StandardOutputEncoding = new UTF8Encoding(false),
                StandardErrorEncoding = new UTF8Encoding(false),
                StandardInputEncoding = new UTF8Encoding(false),
                WorkingDirectory = _installRoot,
            };
            psi.Environment["PYTHONUTF8"] = "1";
            psi.Environment.Remove("PYTHONHOME");
            psi.Environment.Remove("PYTHONPATH");
            var runtimeScripts = Path.GetDirectoryName(_pythonExe) ?? "";
            var ownedUv = Path.Combine(_installRoot, "tools", "uv010", "bin");
            var ownedNpm = Path.Combine(_installRoot, "tools", "npm1092");
            var rest = psi.Environment.TryGetValue("PATH", out var path) ? path : Environment.GetEnvironmentVariable("PATH") ?? "";
            psi.Environment["PATH"] = ownedUv + ";" + ownedNpm + ";" + runtimeScripts + ";" + rest;

            var process = new Process { StartInfo = psi };
            Log("RESIDENT START");
            if (!process.Start())
                throw new InvalidOperationException("无法启动 基地车工厂 backend。");

            _residentProcess = process;
            _activeProcesses[process.Id] = process;
            _residentStdIn = process.StandardInput;
            _residentStdIn.NewLine = "\n";
            _residentStdIn.AutoFlush = true;

            TryAssignToJob(process);
            _residentReader = Task.Run(() => ReadResidentLoopAsync());
            _ = Task.Run(() => DrainStdErrAsync());
        }
        finally
        {
            _residentGate.Release();
        }
    }

    private async Task ReadResidentLoopAsync()
    {
        Exception? terminal = null;
        try
        {
            var reader = _residentProcess!.StandardOutput;
            string? line;
            while (!_shutdownCts.IsCancellationRequested && (line = await reader.ReadLineAsync().ConfigureAwait(false)) is not null)
            {
                line = line.Trim();
                if (line.Length == 0) continue;
                try
                {
                    using var doc = JsonDocument.Parse(line);
                    var root = doc.RootElement;
                    if (!root.TryGetProperty("id", out var idElem) || idElem.ValueKind != JsonValueKind.Number)
                    {
                        Log($"RESPONSE no-id: {Compact(line)}");
                        continue;
                    }
                    int id = (int)idElem.GetInt64();
                    bool ok = root.TryGetProperty("ok", out var okElem) && okElem.GetBoolean();
                    if (_pending.TryGetValue(id, out var tcs))
                    {
                        if (ok)
                        {
                            var result = root.TryGetProperty("result", out var r) ? r.Clone() : JsonDocument.Parse("null").RootElement.Clone();
                            Log($"RESPONSE id={id} ok");
                            tcs.TrySetResult(result);
                        }
                        else
                        {
                            var message = root.TryGetProperty("message", out var m) ? m.GetString() : null;
                            Log($"RESPONSE id={id} error={message}");
                            tcs.TrySetException(new InvalidOperationException(message ?? "Backend request failed."));
                        }
                    }
                    else
                    {
                        Log($"RESPONSE id={id} orphan");
                    }
                }
                catch (Exception ex)
                {
                    Log($"RESPONSE parse-error: {ex.Message} :: {Compact(line)}");
                }
            }
        }
        catch (Exception ex)
        {
            terminal = ex;
            Log($"READER fatal: {ex.Message}");
        }

        // Process ended or reader died: fail any still-pending requests so callers don't hang.
        foreach (var kvp in _pending)
        {
            try
            {
                kvp.Value.TrySetException(terminal is not null
                    ? new InvalidOperationException("Backend 连接中断。", terminal)
                    : new InvalidOperationException("Backend 连接中断（进程已退出）。"));
            }
            catch { }
        }
    }

    private async Task DrainStdErrAsync()
    {
        try
        {
            var reader = _residentProcess?.StandardError;
            if (reader is null) return;
            var buffer = new char[4096];
            while (!_shutdownCts.IsCancellationRequested)
            {
                var n = await reader.ReadAsync(buffer.AsMemory(), _shutdownCts.Token).ConfigureAwait(false);
                if (n == 0) break;
                Log("STDERR " + new string(buffer, 0, n).Replace("\r", " ").Replace("\n", " ").Trim());
            }
        }
        catch { }
    }

    private async Task DisposeResidentProcessAsync()
    {
        var proc = _residentProcess;
        _residentProcess = null;
        _residentStdIn = null;
        if (proc is null) return;
        try { try { proc.StandardInput.Close(); } catch { } } catch { }
        if (!proc.HasExited)
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromMilliseconds(300));
            try { await proc.WaitForExitAsync(cts.Token).ConfigureAwait(false); }
            catch (OperationCanceledException) { }
            if (!proc.HasExited) { try { proc.Kill(entireProcessTree: true); } catch { } }
        }
        _activeProcesses.TryRemove(proc.Id, out _);
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string? lpName);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(IntPtr hJob, int JobObjectInformationClass, IntPtr lpJobObjectInfo, uint cbJobObjectInfoLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct IO_COUNTERS
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryLimit;
        public UIntPtr PeakJobMemoryLimit;
    }
}


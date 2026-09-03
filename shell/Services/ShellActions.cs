using System.Diagnostics;
using System.IO;

namespace ProjectFactory.Workbench.Services;

public static class ShellActions
{
    public static void OpenPath(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return;
        var target = path!;
        if (File.Exists(target)) target = Path.GetDirectoryName(target) ?? target;
        if (!Directory.Exists(target)) return;
        Process.Start(new ProcessStartInfo("explorer.exe", $"\"{target}\"") { UseShellExecute = true });
    }

    public static void OpenLogs()
    {
        var root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ProjectFactory", "logs");
        Directory.CreateDirectory(root);
        OpenPath(root);
    }

    public static string FactoryExePath()
        => Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs",
            "ProjectFactory",
            "app",
            "ProjectFactory.exe");

    public static void LaunchFactory()
    {
        var exe = FactoryExePath();
        if (!File.Exists(exe)) return;
        Process.Start(new ProcessStartInfo(exe) { UseShellExecute = true, WorkingDirectory = Path.GetDirectoryName(exe) });
    }

    public static void RelaunchFactory()
    {
        var exe = FactoryExePath();
        if (!File.Exists(exe)) return;
        var quoted = exe.Replace("\"", "\\\"");
        Process.Start(new ProcessStartInfo
        {
            FileName = "cmd.exe",
            Arguments = "/c timeout /t 1 /nobreak >nul & start \"\" \"" + quoted + "\"",
            UseShellExecute = false,
            CreateNoWindow = true,
        });
        System.Windows.Application.Current?.Shutdown();
    }
}

using System.Threading;
using System.Windows;
using Microsoft.Extensions.DependencyInjection;
using ProjectFactory.Workbench.Services;
using ProjectFactory.Workbench.Views;
using Wpf.Ui;
using Wpf.Ui.DependencyInjection;

namespace ProjectFactory.Workbench;

public partial class App : Application
{
    private readonly ServiceProvider _services;
    // Gate 5 / Hotfix 5A: guard against double-cleanup if both OnExit and
    // ProcessExit fire (which can happen during normal close under some WPF
    // shutdown paths). 0 = not done, 1 = done.
    private int _cleanupDone;

    public App()
    {
        var services = new ServiceCollection();
        services.AddNavigationViewPageProvider();
        services.AddSingleton<INavigationService, NavigationService>();
        services.AddSingleton<PythonBridgeClient>();
        services.AddSingleton<ShellSettings>();
        services.AddSingleton<MainWindow>();
        services.AddSingleton<HomePage>();
        services.AddSingleton<CreatePage>();
        services.AddSingleton<ProjectsPage>();
        services.AddSingleton<ToolsPage>();
        services.AddSingleton<SettingsPage>();
        services.AddSingleton<ResourcesPage>();
        _services = services.BuildServiceProvider();
    }

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        ShutdownMode = ShutdownMode.OnMainWindowClose;
        AppDomain.CurrentDomain.ProcessExit += OnProcessExit;
        var settings = _services.GetRequiredService<ShellSettings>();
        var window = _services.GetRequiredService<MainWindow>();
        settings.Apply(window);
        MainWindow = window;
        window.Closed += OnMainWindowClosed;
        window.Show();
        window.Activate();
        window.Focus();
    }

    private async void OnMainWindowClosed(object? sender, EventArgs args)
    {
        // Give bridge child processes a grace period before Shutdown() is
        // called, so the PythonBridgeClient.ShutdownAsync path can complete
        // cleanly rather than being force-killed by process exit.
        var bridge = _services.GetService<PythonBridgeClient>();
        if (bridge != null)
        {
            try { await bridge.ShutdownAsync(TimeSpan.FromSeconds(2)).ConfigureAwait(false); }
            catch { }
        }
        try
        {
            if (Dispatcher != null && !Dispatcher.HasShutdownStarted)
            {
                Dispatcher.Invoke(() => Shutdown(0));
            }
            else
            {
                Shutdown(0);
            }
        }
        catch
        {
            Shutdown(0);
        }
    }

    private void OnProcessExit(object? sender, EventArgs e)
    {
        Cleanup();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        Cleanup();
        base.OnExit(e);
    }

    private void Cleanup()
    {
        // Idempotency guard: only the first caller proceeds.
        if (Interlocked.CompareExchange(ref _cleanupDone, 1, 0) != 0)
            return;

        try
        {
            var bridge = _services.GetService<PythonBridgeClient>();
            bridge?.Dispose();
        }
        catch { }

        try
        {
            _services.Dispose();
        }
        catch { }
    }
}


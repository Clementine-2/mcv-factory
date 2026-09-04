using System;
using System.Linq;
using System.Threading;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using Microsoft.Extensions.DependencyInjection;
using ProjectFactory.Workbench.Services;
using ProjectFactory.Workbench.Views;
using Wpf.Ui;
using Wpf.Ui.Controls;
using Wpf.Ui.DependencyInjection;

namespace ProjectFactory.Workbench;

public partial class App : Application
{
    private readonly ServiceProvider _services;
    // Gate 5 / Hotfix 5A: guard against double-cleanup if both OnExit and
    // ProcessExit fire (which can happen during normal close under some WPF
    // shutdown paths). 0 = not done, 1 = done.
    private int _cleanupDone;

    /// <summary>Active UI language code ("zh-CN", "zh-Hant" or "en-US").</summary>
    public static string CurrentLanguage { get; private set; } = "zh-CN";

    /// <summary>Resolve a UI string for the active language (code-behind helper).</summary>
    public static string L(string key)
    {
        if (Current?.TryFindResource(key) is string value)
            return value;
        return key;
    }

    /// <summary>Switch the UI language by swapping the merged strings dictionary.</summary>
    public static void SetLanguage(string language)
    {
        if (Current is not App app || string.IsNullOrWhiteSpace(language))
            return;
        CurrentLanguage = language;
        var uri = new Uri($"pack://application:,,,/Resources/Strings.{language}.xaml", UriKind.Absolute);
        var merged = app.Resources.MergedDictionaries;
        var previous = merged.FirstOrDefault(d => d.Source is not null && d.Source.OriginalString.Contains("/Strings.", StringComparison.Ordinal));
        if (previous is not null)
            merged.Remove(previous);
        merged.Add(new ResourceDictionary { Source = uri });
    }

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
        // Scroll fix: WPF-UI measures navigated pages with unbounded height, so a
        // page-level ScrollViewer grows to its content and never scrolls. Pinning
        // each page's height to the WPF-UI content frame (a Frame) restores a real,
        // scrollable viewport. See also App.xaml's CanContentScroll opt-out.
        EventManager.RegisterClassHandler(
            typeof(Page),
            FrameworkElement.LoadedEvent,
            new RoutedEventHandler(OnPageLoaded));
        var settings = _services.GetRequiredService<ShellSettings>();
        // Restore persisted language before any window content is resolved.
        if (!string.IsNullOrWhiteSpace(settings.Language))
            SetLanguage(settings.Language);
        var window = _services.GetRequiredService<MainWindow>();
        settings.Apply(window);
        MainWindow = window;
        window.Closed += OnMainWindowClosed;
        window.Show();
        window.Activate();
        window.Focus();
    }

    private static void OnPageLoaded(object sender, RoutedEventArgs e)
    {
        if (sender is not Page page)
            return;
        page.Dispatcher.BeginInvoke(
            new Action(() =>
            {
                var presenter = FindAncestor<NavigationViewContentPresenter>(page);
                if (presenter is { ActualHeight: > 0 } frame)
                    page.Height = frame.ActualHeight;
            }),
            DispatcherPriority.Loaded);
    }

    private static T? FindAncestor<T>(DependencyObject? current) where T : DependencyObject
    {
        while (current is not null)
        {
            if (current is T match)
                return match;
            current = VisualTreeHelper.GetParent(current);
        }
        return null;
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


using System.Windows;
using ProjectFactory.Workbench.Services;
using ProjectFactory.Workbench.Views;
using Wpf.Ui;
using Wpf.Ui.Controls;

namespace ProjectFactory.Workbench;

// Gate 5 fix (Hotfix 5A): The custom HwndSource/WM_CLOSE hook has been removed.
// WPF FluentWindow already handles WM_CLOSE correctly through the standard message
// loop. The previous hook intercepted WM_CLOSE, called Close(), then set handled=true,
// which prevented Process.CloseMainWindow() from completing the normal close sequence,
// causing the process to remain alive beyond 5 seconds.
public partial class MainWindow : FluentWindow
{
    private readonly ShellSettings _settings;

    public MainWindow(INavigationService navigationService, ShellSettings settings)
    {
        _settings = settings;
        InitializeComponent();
        navigationService.SetNavigationControl(RootNavigationView);
        Loaded += (_, _) =>
        {
            RootNavigationView.Navigate(typeof(HomePage));
            _settings.Apply(this);
        };
    }

    // A组(R2/2.6): 已移除 150ms 常驻 EnumWindows/SetParent 定时器（HideUacInputOverlay）。
    // 这里仅做响应式收边：窗口收窄到阈值以下时自动收起左导航，避免内容被挤压；
    // 不再触碰 ShellRoot 尺寸，因此不会与布局相互触发导致闪烁。
    private void MainWindow_OnSizeChanged(object sender, SizeChangedEventArgs e)
    {
        if (RootNavigationView is null) return;
        // F23: collapse the nav when the window gets too narrow, but re-expand it when the
        // user widens again (previously it only ever collapsed and never came back).
        if (e.NewSize.Width < 1100)
            RootNavigationView.IsPaneOpen = false;
        else
            RootNavigationView.IsPaneOpen = true;
    }

    // T43：统一非致命提示到 Snackbar。调用方已设置状态文本，这里仅做增强；
    // 任何异常（如 Snackbar API 差异）都被静默吞掉，不影响主流程。
    public void ShowAppSnackbar(string message)
    {
        try
        {
            var snackbar = new Snackbar(SnackbarPresenter);
            snackbar.Title = "提示";
            snackbar.Content = message;
            snackbar.Timeout = TimeSpan.FromMilliseconds(3000);
            snackbar.Show();
        }
        catch { }
    }
}

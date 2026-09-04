using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using Microsoft.Win32;
using ProjectFactory.Workbench.Services;

namespace ProjectFactory.Workbench.Views;

public partial class ToolsPage : Page
{
    private readonly PythonBridgeClient _bridge;
    private static readonly JsonSerializerOptions PrettyJson = new() { WriteIndented = true };

    public ToolsPage(PythonBridgeClient bridge)
    {
        _bridge = bridge;
        InitializeComponent();
    }

    private async void RefreshStatus_Click(object sender, RoutedEventArgs e)
        => await RunAsync(() => _bridge.InvokeAsync("status", new { deep = false }));

    private async void CheckProject_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFolderDialog { Title = "选择要检查的 Project Factory 项目" };
        if (dialog.ShowDialog() == true)
            await RunAsync(() => _bridge.InvokeAsync("check", new { project_root = dialog.FolderName }));
    }

    private async void VerifyZip_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog { Title = "选择要恢复验证的 Project Factory ZIP", Filter = "ZIP archive (*.zip)|*.zip" };
        if (dialog.ShowDialog() == true)
            await RunAsync(() => _bridge.InvokeAsync("verify_zip", new { zip_path = dialog.FileName }));
    }

    private async Task RunAsync(Func<Task<JsonElement>> action)
    {
        ToolProgress.Visibility = Visibility.Visible;
        ToolOutput.Text = App.L("Ms_Running");
        try
        {
            var result = await action();
            ToolOutput.Text = JsonSerializer.Serialize(result, PrettyJson);
        }
        catch (Exception ex)
        {
            ToolOutput.Text = "ERROR\n" + ex.Message;
        }
        finally
        {
            ToolProgress.Visibility = Visibility.Collapsed;
        }
    }

    private void OpenLogs_Click(object sender, RoutedEventArgs e) => ShellActions.OpenLogs();
}

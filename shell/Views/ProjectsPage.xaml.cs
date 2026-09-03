using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using ProjectFactory.Workbench.Services;
using Wpf.Ui.Controls;
using TextBlock = Wpf.Ui.Controls.TextBlock;

namespace ProjectFactory.Workbench.Views;

public partial class ProjectsPage : Page
{
    private readonly PythonBridgeClient _bridge;
    private DateTime _lastRefresh = DateTime.MinValue;

    public ProjectsPage(PythonBridgeClient bridge)
    {
        _bridge = bridge;
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            // F24: drop the one-shot _loaded guard (it made the page never refresh again after
            // the first visit). Re-load on navigation, but skip if we refreshed <30s ago so
            // bouncing between pages doesn't hammer the backend.
            await LoadHistoryAsync();
        };
    }

    private async void Refresh_Click(object sender, RoutedEventArgs e) => await LoadHistoryAsync(force: true);

    private async Task LoadHistoryAsync(bool force = false)
    {
        if (!force && (DateTime.Now - _lastRefresh).TotalSeconds < 30)
            return;
        _lastRefresh = DateTime.Now;

        HistoryProgress.Visibility = Visibility.Visible;
        HistoryPanel.Children.Clear();
        HistoryMessage.Text = "正在读取项目历史…";
        try
        {
            var result = await _bridge.InvokeAsync("history", new { limit = 80 });
            if (!result.TryGetProperty("items", out var items) || items.ValueKind != JsonValueKind.Array || items.GetArrayLength() == 0)
            {
                HistoryMessage.Text = "还没有项目。去“新建项目”说一句你想做什么。";
                return;
            }

            HistoryMessage.Text = $"最近 {items.GetArrayLength()} 个项目";
            foreach (var item in items.EnumerateArray())
                HistoryPanel.Children.Add(CreateProjectCard(item));
        }
        catch (Exception ex)
        {
            HistoryMessage.Text = "无法读取项目历史：" + ex.Message;
        }
        finally
        {
            HistoryProgress.Visibility = Visibility.Collapsed;
        }
    }

    private static Card CreateProjectCard(JsonElement item)
    {
        var name = JsonView.String(item, "project_name", "未命名项目");
        var profile = JsonView.String(item, "profile", "unknown");
        var status = HumanStatus(JsonView.String(item, "status", "UNKNOWN"));
        var timestamp = JsonView.String(item, "timestamp", "");
        var root = JsonView.String(item, "project_root", "");
        var zip = JsonView.String(item, "project_zip", "");

        var card = new Card { Padding = new Thickness(22), Margin = new Thickness(0, 0, 0, 12) };
        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition());
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var text = new StackPanel();
        text.Children.Add(new TextBlock { Text = name, FontSize = 17, FontWeight = FontWeights.SemiBold });
        text.Children.Add(new TextBlock
        {
            Text = $"{HumanProfile(profile)}  ·  {status}{(string.IsNullOrWhiteSpace(timestamp) ? "" : "  ·  " + timestamp)}",
            FontSize = 12,
            Opacity = 0.62,
            Margin = new Thickness(0, 5, 0, 0)
        });
        if (!string.IsNullOrWhiteSpace(root))
            text.Children.Add(new TextBlock { Text = root, FontSize = 12, Opacity = 0.56, Margin = new Thickness(0, 9, 0, 0), TextWrapping = TextWrapping.Wrap });
        grid.Children.Add(text);

        var actions = new StackPanel { Orientation = Orientation.Horizontal, VerticalAlignment = VerticalAlignment.Center };
        // F28: verify the project directory still exists before offering to open it; a moved or
        // deleted project shouldn't present a dead "打开" button.
        var rootExists = !string.IsNullOrWhiteSpace(root) && System.IO.Directory.Exists(root);
        var open = new Wpf.Ui.Controls.Button
        {
            Content = rootExists ? "打开项目" : "项目目录已不在",
            Appearance = ControlAppearance.Primary,
            Tag = root,
            Margin = new Thickness(8, 0, 0, 0),
            IsEnabled = rootExists,
        };
        open.Click += (_, _) => { if (rootExists) ShellActions.OpenPath(root); };
        actions.Children.Add(open);
        if (!string.IsNullOrWhiteSpace(zip))
        {
            // F28: open the folder that contains the ZIP (the "所在目录" wording) rather than the file itself.
            var zipDir = System.IO.Path.GetDirectoryName(zip);
            var zipButton = new Wpf.Ui.Controls.Button
            {
                Content = "打开 ZIP 所在目录",
                Appearance = ControlAppearance.Secondary,
                Tag = zipDir,
                Margin = new Thickness(8, 0, 0, 0),
            };
            zipButton.Click += (_, _) => ShellActions.OpenPath(zipButton.Tag?.ToString());
            actions.Children.Add(zipButton);
        }
        Grid.SetColumn(actions, 1);
        grid.Children.Add(actions);
        card.Content = grid;
        return card;
    }

    private static string HumanProfile(string profile) => profile switch
    {
        "python-cli" => "Python CLI",
        "python-library" => "Python Library",
        "node-library" => "Node Library",
        "browser-extension-js" => "Browser Extension",
        _ => profile,
    };

    private static string HumanStatus(string status) => status switch
    {
        "VERIFIED" => "已验证",
        "READY" => "就绪",
        "READY_WITH_WARNINGS" => "就绪（有提示）",
        "BLOCKED" => "已阻断",
        "UNKNOWN" => "未知",
        _ => status,
    };
}

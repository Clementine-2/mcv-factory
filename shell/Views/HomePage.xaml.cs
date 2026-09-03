using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using ProjectFactory.Workbench.Services;
using Wpf.Ui;

namespace ProjectFactory.Workbench.Views;

public partial class HomePage : Page
{
    private readonly PythonBridgeClient _bridge;
    private readonly INavigationService _navigation;
    private readonly CreatePage _createPage;
    private bool _profilesExpanded;
    private bool _statusRunning;
    private string _allProfilesText = "";
    private string _collapsedProfilesText = "";

    public HomePage(PythonBridgeClient bridge, INavigationService navigation, CreatePage createPage)
    {
        _bridge = bridge;
        _navigation = navigation;
        _createPage = createPage;
        InitializeComponent();
        // G3: re-check status both on first load and every time the page becomes visible again
        // (returning from 工具 after fixing a BLOCKED issue must refresh, not show stale text).
        Loaded += (_, _) => _ = RefreshStatusAsync();
        IsVisibleChanged += (_, _) => { if (IsVisible) _ = RefreshStatusAsync(); };
    }

    private async Task RefreshStatusAsync()
    {
        if (_statusRunning) return;
        _statusRunning = true;
        StatusProgress.Visibility = Visibility.Visible;
        try
        {
            var status = await _bridge.InvokeAsync("status");
            var state = JsonView.String(status, "status", "UNKNOWN");
            StatusHeadline.Text = state switch
            {
                "READY" => "已就绪，可以开始",
                "READY_WITH_WARNINGS" => "可以开始工作",
                "BLOCKED" => "需要先处理一个问题",
                _ => "状态需要确认",
            };
            if (status.TryGetProperty("ready_profiles", out var profiles) && profiles.ValueKind == JsonValueKind.Array)
            {
                _allProfilesText = HumanProfiles(profiles);
                var count = profiles.GetArrayLength();
                // Collapsed: first 3 + " 等 N 个" where N is the REMAINING count, not the total.
                var labels = profiles.EnumerateArray().Select(x => x.GetString() ?? "").Where(x => !string.IsNullOrWhiteSpace(x)).ToList();
                if (labels.Count > 4)
                {
                    var remaining = labels.Count - 3;
                    _collapsedProfilesText = string.Join("  ·  ", labels.Take(3)) + $"  ·  等 {remaining} 个";
                    ToggleProfilesButton.Visibility = Visibility.Visible;
                    ToggleProfilesButton.Content = "展开";
                    ReadyProfiles.Text = _collapsedProfilesText;
                    ReadyProfiles.MaxHeight = 48;
                    _profilesExpanded = false;
                }
                else
                {
                    _collapsedProfilesText = _allProfilesText;
                    _allProfilesText = HumanProfiles(profiles);
                    ToggleProfilesButton.Visibility = Visibility.Collapsed;
                    ReadyProfiles.Text = _allProfilesText;
                    ReadyProfiles.MaxHeight = double.PositiveInfinity;
                }
                ReadyProfilesHint.Text = count > 0 ? $"已就绪 {count} 种，不支持的类型会明确说明原因。" : "不支持的类型会明确说明原因，不会假装生成成功。";
            }
            else
                ReadyProfiles.Text = "暂未发现可用项目类型";

            var warnings = status.TryGetProperty("warnings", out var ws) && ws.ValueKind == JsonValueKind.Array ? ws.GetArrayLength() : 0;
            var failures = status.TryGetProperty("hard_failures", out var fs) && fs.ValueKind == JsonValueKind.Array ? fs.GetArrayLength() : 0;
            StatusDetail.Text = failures > 0
                ? $"有 {failures} 个阻断项。打开“工具”查看具体原因。"
                : warnings > 0
                    ? $"核心生成能力可用；另有 {warnings} 项可选集成或兼容性提示，不影响当前工作。"
                    : "核心生成与验证能力正常。";
            // G2: when there are blocking failures, offer a direct jump to 工具 so the user isn't stuck.
            StatusActionButton.Visibility = failures > 0 ? Visibility.Visible : Visibility.Collapsed;
        }
        catch (Exception ex)
        {
            StatusHeadline.Text = "无法读取运行状态";
            StatusDetail.Text = ex.Message;
            StatusActionButton.Visibility = Visibility.Collapsed;
        }
        finally
        {
            StatusProgress.Visibility = Visibility.Collapsed;
            _statusRunning = false;
        }
    }

    private static string HumanProfiles(JsonElement profiles)
    {
        var labels = profiles.EnumerateArray().Select(x => {
            var id = x.GetString() ?? "";
            return id switch
            {
                "python-cli" => "Python CLI",
                "python-library" => "Python Library",
                "node-library" => "Node Library",
                "browser-extension-js" => "Browser Extension",
                _ => System.Globalization.CultureInfo.CurrentCulture.TextInfo.ToTitleCase(id.Replace("-", " ").Replace("_", " "))
            };
        }).Where(x => !string.IsNullOrWhiteSpace(x));
        return string.Join("  ·  ", labels);
    }

    private void ToggleProfiles_Click(object sender, RoutedEventArgs e)
    {
        _profilesExpanded = !_profilesExpanded;
        if (_profilesExpanded)
        {
            ReadyProfiles.Text = _allProfilesText;
            ReadyProfiles.MaxHeight = 220;
            ReadyProfilesHint.Text = "已展开全部可用类型。";
            ToggleProfilesButton.Content = "收起";
        }
        else
        {
            ReadyProfiles.Text = _collapsedProfilesText;
            ReadyProfiles.MaxHeight = 48;
            var count = _allProfilesText.Split("  ·  ").Length;
            ReadyProfilesHint.Text = $"已就绪 {count} 种，不支持的类型会明确说明原因。";
            ToggleProfilesButton.Content = "展开";
        }
    }

    private void Create_Click(object sender, RoutedEventArgs e)
    {
        _createPage.StartFresh();
        _navigation.Navigate(typeof(CreatePage));
    }

    private void Projects_Click(object sender, RoutedEventArgs e) => _navigation.Navigate(typeof(ProjectsPage));

    private void Resources_Click(object sender, RoutedEventArgs e) => _navigation.Navigate(typeof(ResourcesPage));

    private void StatusAction_Click(object sender, RoutedEventArgs e) => _navigation.Navigate(typeof(ToolsPage));

    private void Template_Click(object sender, RoutedEventArgs e)
    {
        var tag = (sender as FrameworkElement)?.Tag?.ToString();
        var text = tag switch
        {
            "python-cli" => "做一个 Python CLI 工具。请优先保证安全、可测试、错误信息清晰，并保留以后扩展功能的空间。",
            "python-library" => "做一个可复用的 Python Library。需要清晰 API、自动化测试、wheel 和 sdist 构建，并方便长期维护。",
            "browser-extension" => "做一个浏览器扩展。先搭建可靠、可维护、可验证的基础项目结构，后续我再补充具体功能。",
            _ => "",
        };
        _createPage.StartFresh(text);
        _navigation.Navigate(typeof(CreatePage));
    }
}

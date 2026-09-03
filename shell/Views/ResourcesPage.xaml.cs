using System.Collections.ObjectModel;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using Microsoft.Win32;
using ProjectFactory.Workbench.Services;

namespace ProjectFactory.Workbench.Views;

public sealed class ResourceRow
{
    public string Label { get; set; } = "";
    public string Path { get; set; } = "";
    public string Id { get; set; } = "";
    public string Family { get; set; } = "";
    public string Version { get; set; } = "";
    public string Purpose { get; set; } = "";
    public string Status { get; set; } = "";
}

public sealed class ResourceGroup
{
    public string Label { get; set; } = "";
    public string Id { get; set; } = "";
    public ObservableCollection<ResourceRow> Versions { get; } = new();
}

public partial class ResourcesPage : Page
{
    private readonly PythonBridgeClient _bridge;
    private bool _ready;
    private readonly ObservableCollection<ResourceRow> _wheels = new();
    private readonly ObservableCollection<ResourceRow> _resources = new();
    private readonly ObservableCollection<ResourceRow> _tools = new();
    private readonly ObservableCollection<ResourceGroup> _groups = new();
    private readonly ObservableCollection<ResourceRow> _lines = new();
    private DateTime _lastRefresh = DateTime.MinValue;

    public ResourcesPage(PythonBridgeClient bridge)
    {
        _bridge = bridge;
        InitializeComponent();
        WheelList.ItemsSource = _wheels;
        ResourceList.ItemsSource = _resources;
        ToolList.ItemsSource = _tools;
        ModuleTree.ItemsSource = _groups;
        FactoryLineList.ItemsSource = _lines;
        Loaded += async (_, _) =>
        {
            _ready = true;
            await RefreshAsync();
        };
    }

    private async void Refresh_Click(object sender, RoutedEventArgs e) => await RefreshAsync(force: true);

    private async Task RefreshAsync(bool force = false)
    {
        // F22: cache guard — navigating into this page reloads every time it's shown, which
        // cold-starts the backend each time. Skip a re-load if we refreshed less than 30s ago
        // unless the user explicitly hit refresh (force).
        if (!force && (DateTime.Now - _lastRefresh).TotalSeconds < 30)
            return;
        _lastRefresh = DateTime.Now;

        // Try batch overview first (1 Process), fallback to per-section
        try
        {
            var ov = await _bridge.InvokeAsync("overview");
            if (ov.TryGetProperty("factory_version", out var fv))
                ActiveVersionText.Text = "当前核心组件：" + JsonView.String(fv, "version", "?");
            else if (ov.TryGetProperty("version", out var v))
                ActiveVersionText.Text = "当前核心组件：" + JsonView.String(v, "version", "?");

            // wheels from overview
            _wheels.Clear();
            if (ov.TryGetProperty("wheels", out var wheels))
            {
                AddWheelGroup(wheels, "live_wheels");
                if (wheels.TryGetProperty("store", out var store))
                {
                    if (store.TryGetProperty("auto_update", out var auto))
                        AutoUpdateBox.IsChecked = auto.ValueKind == JsonValueKind.True;
                    if (store.TryGetProperty("items", out var items) && items.ValueKind == JsonValueKind.Array)
                    {
                        foreach (var item in items.EnumerateArray())
                            _wheels.Add(new ResourceRow { Label = "仓库 · " + JsonView.String(item, "name"), Path = JsonView.String(item, "path") });
                    }
                }
                WheelStatus.Text = _wheels.Count == 0 ? "还没有核心组件包。" : $"共 {_wheels.Count} 颗核心组件包。选中后点热更新。";
            }

            // resources
            _resources.Clear();
            if (ov.TryGetProperty("resources", out var resources) && resources.TryGetProperty("items", out var ritems) && ritems.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in ritems.EnumerateArray())
                    _resources.Add(new ResourceRow { Label = JsonView.String(item, "name"), Path = JsonView.String(item, "path") });
                ResourceStatus.Text = JsonView.String(resources, "directory");
            }

            // tools
            _tools.Clear();
            if (ov.TryGetProperty("tools", out var tools) && tools.TryGetProperty("items", out var titems) && titems.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in titems.EnumerateArray())
                {
                    var owned = item.TryGetProperty("owned", out var flag) && flag.ValueKind == JsonValueKind.True;
                    _tools.Add(new ResourceRow { Label = (owned ? "本厂 · " : "PATH · ") + JsonView.String(item, "id") + "  钉 " + JsonView.String(item, "pinned") + "  现 " + JsonView.String(item, "version"), Path = JsonView.String(item, "path") });
                }
                ToolStatus.Text = JsonView.String(tools, "dirs");
            }

            // factory lines from overview catalog
            _lines.Clear();
            if (ov.TryGetProperty("factory_lines", out var flines) && flines.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in flines.EnumerateArray())
                    _lines.Add(new ResourceRow { Id = JsonView.String(item, "id"), Label = JsonView.String(item, "group") + " · " + JsonView.String(item, "label") + "  " + JsonView.String(item, "purpose"), Path = JsonView.String(item, "source") });
                FactoryLineStatus.Text = "共 " + _lines.Count + " 条产线。";
            }
            else if (ov.TryGetProperty("catalog", out var cat) && cat.TryGetProperty("factory_lines", out var fl2) && fl2.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in fl2.EnumerateArray())
                    _lines.Add(new ResourceRow { Id = JsonView.String(item, "id"), Label = JsonView.String(item, "group") + " · " + JsonView.String(item, "label") + "  " + JsonView.String(item, "purpose"), Path = JsonView.String(item, "source") });
                FactoryLineStatus.Text = "共 " + _lines.Count + " 条产线。";
            }

            // modules
            _groups.Clear();
            if (ov.TryGetProperty("modules", out var modules) && modules.TryGetProperty("groups", out var gitems) && gitems.ValueKind == JsonValueKind.Array)
            {
                foreach (var group in gitems.EnumerateArray())
                {
                    var bucket = new ResourceGroup { Id = JsonView.String(group, "id"), Label = JsonView.String(group, "label") + "  ·  " + JsonView.String(group, "kind") + "  " + JsonView.String(group, "group") };
                    if (group.TryGetProperty("versions", out var versions) && versions.ValueKind == JsonValueKind.Array)
                        foreach (var item in versions.EnumerateArray())
                            bucket.Versions.Add(new ResourceRow { Id = JsonView.String(item, "id"), Family = JsonView.String(item, "family", JsonView.String(group, "id")), Version = JsonView.String(item, "version", "catalog"), Purpose = SanitizePurpose(JsonView.String(item, "purpose")), Status = JsonView.String(item, "status", "catalog"), Path = JsonView.String(item, "url", JsonView.String(item, "path")), Label = JsonView.String(item, "version", "catalog") + "  [" + JsonView.String(item, "status", "catalog") + "]" });
                    _groups.Add(bucket);
                }
                ModuleStatus.Text = JsonView.String(modules, "directory") + "  ·  " + _groups.Count + " 组";
            }
            return;
        }
        catch { }

        // Fallback: per-section (old path, each independent)
        try
        {
            var ver = await _bridge.InvokeAsync("factory.version");
            ActiveVersionText.Text = "当前核心组件：" + JsonView.String(ver, "version", "?");
        }
        catch (Exception ex) { ActiveVersionText.Text = "内核版本读取失败：" + ex.Message; }

        // wheels
        try
        {
            var wheels = await _bridge.InvokeAsync("wheels.list");
            _wheels.Clear();
            AddWheelGroup(wheels, "live_wheels");
            if (wheels.TryGetProperty("store", out var store))
            {
                if (store.TryGetProperty("auto_update", out var auto))
                    AutoUpdateBox.IsChecked = auto.ValueKind == JsonValueKind.True;
                if (store.TryGetProperty("items", out var items) && items.ValueKind == JsonValueKind.Array)
                {
                    foreach (var item in items.EnumerateArray())
                        _wheels.Add(new ResourceRow
                        {
                            Label = "仓库 · " + JsonView.String(item, "name"),
                            Path = JsonView.String(item, "path"),
                        });
                }
            }
            WheelStatus.Text = _wheels.Count == 0 ? "还没有核心组件包。" : $"共 {_wheels.Count} 颗核心组件包。选中后点热更新。";
        }
        catch (Exception ex) { WheelStatus.Text = "核心组件加载失败：" + ex.Message; }

        // resources
        try
        {
            var resources = await _bridge.InvokeAsync("resources.list");
            _resources.Clear();
            if (resources.TryGetProperty("items", out var ritems) && ritems.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in ritems.EnumerateArray())
                    _resources.Add(new ResourceRow
                    {
                        Label = JsonView.String(item, "name"),
                        Path = JsonView.String(item, "path"),
                    });
            }
            ResourceStatus.Text = JsonView.String(resources, "directory");
        }
        catch (Exception ex) { ResourceStatus.Text = "资源加载失败：" + ex.Message; }

        // tools
        try
        {
            _tools.Clear();
            var tools = await _bridge.InvokeAsync("tools.list");
            if (tools.TryGetProperty("items", out var titems) && titems.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in titems.EnumerateArray())
                {
                    var owned = item.TryGetProperty("owned", out var flag) && flag.ValueKind == JsonValueKind.True;
                    _tools.Add(new ResourceRow
                    {
                        Label = (owned ? "本厂 · " : "PATH · ") + JsonView.String(item, "id") + "  钉 " + JsonView.String(item, "pinned") + "  现 " + JsonView.String(item, "version"),
                        Path = JsonView.String(item, "path"),
                    });
                }
            }
            ToolStatus.Text = JsonView.String(tools, "dirs");
        }
        catch (Exception ex) { ToolStatus.Text = "工具加载失败：" + ex.Message; }

        // factory lines (catalog.gui) — was “No module named 'gui_catalog'” before fix
        try
        {
            _lines.Clear();
            var catalog = await _bridge.InvokeAsync("catalog.gui");
            if (catalog.TryGetProperty("catalog", out var cat) && cat.TryGetProperty("factory_lines", out var flines) && flines.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in flines.EnumerateArray())
                    _lines.Add(new ResourceRow
                    {
                        Id = JsonView.String(item, "id"),
                        Label = JsonView.String(item, "group") + " · " + JsonView.String(item, "label") + "  " + JsonView.String(item, "purpose"),
                        Path = JsonView.String(item, "source"),
                    });
            }
            FactoryLineStatus.Text = "共 " + _lines.Count + " 条产线。";
        }
        catch (Exception ex) { FactoryLineStatus.Text = "项目类型加载失败：" + ex.Message; _lines.Clear(); }

        // modules
        try
        {
            _groups.Clear();
            var modules = await _bridge.InvokeAsync("modules.list");
            if (modules.TryGetProperty("groups", out var gitems) && gitems.ValueKind == JsonValueKind.Array)
            {
                foreach (var group in gitems.EnumerateArray())
                {
                    var bucket = new ResourceGroup
                    {
                        Id = JsonView.String(group, "id"),
                        Label = JsonView.String(group, "label") + "  ·  " + JsonView.String(group, "kind") + "  " + JsonView.String(group, "group"),
                    };
                    if (group.TryGetProperty("versions", out var versions) && versions.ValueKind == JsonValueKind.Array)
                    {
                        foreach (var item in versions.EnumerateArray())
                            bucket.Versions.Add(new ResourceRow
                            {
                                Id = JsonView.String(item, "id"),
                                Family = JsonView.String(item, "family", JsonView.String(group, "id")),
                                Version = JsonView.String(item, "version", "catalog"),
                                Purpose = SanitizePurpose(JsonView.String(item, "purpose")),
                                Status = JsonView.String(item, "status", "catalog"),
                                Path = JsonView.String(item, "url", JsonView.String(item, "path")),
                                Label = JsonView.String(item, "version", "catalog") + "  [" + JsonView.String(item, "status", "catalog") + "]",
                            });
                    }
                    _groups.Add(bucket);
                }
            }
            ModuleStatus.Text = JsonView.String(modules, "directory") + "  ·  " + _groups.Count + " 组";
        }
        catch (Exception ex) { ModuleStatus.Text = "模块加载失败：" + ex.Message; _groups.Clear(); }
    }

    private static string SanitizePurpose(string purpose)
    {
        if (string.IsNullOrWhiteSpace(purpose)) return "";
        var t = purpose.Trim();
        if (t.Equals("catalog", StringComparison.OrdinalIgnoreCase) || t.Equals("catlog", StringComparison.OrdinalIgnoreCase)) return "";
        return t;
    }

    private void AddWheelGroup(JsonElement wheels, string name)
    {
        if (!wheels.TryGetProperty(name, out var arr) || arr.ValueKind != JsonValueKind.Array) return;
        foreach (var item in arr.EnumerateArray())
            _wheels.Add(new ResourceRow
            {
                Label = "本机 · " + JsonView.String(item, "name"),
                Path = JsonView.String(item, "path"),
            });
    }

    private async void AutoUpdateChanged(object sender, RoutedEventArgs e)
    {
        if (!_ready) return;
        try
        {
            await _bridge.InvokeAsync("wheels.auto_update", new { enabled = AutoUpdateBox.IsChecked == true });
        }
        catch (Exception ex)
        {
            WheelStatus.Text = ex.Message;
        }
    }

    private async Task<bool> ApplySelectedWheelAsync()
    {
        if (WheelList.SelectedItem is not ResourceRow row || string.IsNullOrWhiteSpace(row.Path))
        {
            WheelStatus.Text = "先在列表里选一颗 wheel。";
            return false;
        }
        WheelStatus.Text = "正在热更新内核…";
        var result = await _bridge.InvokeAsync("wheels.apply", new { path = row.Path });
        WheelStatus.Text = "已热更新到 " + JsonView.String(result, "version") + "。可用「启动工厂」或桌面入口重新打开窗口。";
        ActiveVersionText.Text = "当前核心组件：" + JsonView.String(result, "version");
        return true;
    }

    private async void ApplyWheel_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            await ApplySelectedWheelAsync();
        }
        catch (Exception ex)
        {
            WheelStatus.Text = ex.Message;
        }
    }

    private async void ApplyAndRelaunch_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (!await ApplySelectedWheelAsync()) return;
            WheelStatus.Text = "内核已更新，正在重启窗口…";
            ShellActions.RelaunchFactory();
        }
        catch (Exception ex)
        {
            WheelStatus.Text = ex.Message;
        }
    }

    private void LaunchFactory_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            ShellActions.LaunchFactory();
            WheelStatus.Text = "已调用启动入口。如果窗口已打开，会再开一个；热更新后请用「热更新并重启窗口」。";
        }
        catch (Exception ex)
        {
            WheelStatus.Text = ex.Message;
        }
    }

    private async void ImportWheel_Click(object sender, RoutedEventArgs e)
    {
        var picker = new OpenFileDialog { Title = "导入 wheel", Filter = "Wheel|*.whl|所有文件|*.*" };
        if (picker.ShowDialog() != true) return;
        try
        {
            await _bridge.InvokeAsync("wheels.import", new { path = picker.FileName });
            await RefreshAsync();
        }
        catch (Exception ex)
        {
            WheelStatus.Text = ex.Message;
        }
    }

    private async void DownloadWheel_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            await _bridge.InvokeAsync("wheels.download", new { url = DownloadUrlBox.Text.Trim() });
            await RefreshAsync();
        }
        catch (Exception ex)
        {
            WheelStatus.Text = ex.Message;
        }
    }

    private async void ImportResource_Click(object sender, RoutedEventArgs e)
    {
        var picker = new OpenFileDialog { Title = "导入用户资源", Filter = "YAML/JSON/Python|*.yaml;*.yml;*.json;*.py|所有文件|*.*" };
        if (picker.ShowDialog() != true) return;
        try
        {
            var destHint = picker.FileName;
            if (picker.FileName.EndsWith(".py", StringComparison.OrdinalIgnoreCase))
            {
                var plugins = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ProjectFactory", "user_warehouse", "plugins");
                System.IO.Directory.CreateDirectory(plugins);
                var copied = System.IO.Path.Combine(plugins, System.IO.Path.GetFileName(picker.FileName));
                System.IO.File.Copy(picker.FileName, copied, true);
                ResourceStatus.Text = "插件已放到 " + copied + "。需要符合模块格式（含标识与构建入口）。";
            }
            else
            {
                await _bridge.InvokeAsync("resources.import", new { path = picker.FileName });
            }
            await RefreshAsync();
        }
        catch (Exception ex)
        {
            ResourceStatus.Text = ex.Message;
        }
    }

    private ResourceRow? SelectedModuleVersion()
    {
        if (ModuleTree.SelectedItem is ResourceRow row) return row;
        if (ModuleTree.SelectedItem is ResourceGroup group) return group.Versions.LastOrDefault();
        return null;
    }

    // F19: the module edit form is only enabled once a version is actually selected, so
    // users can't type into boxes that would be thrown away (the old behaviour left the
    // form always-editable and silently did nothing when nothing was selected).
    private void ModuleTree_Selected(object sender, RoutedPropertyChangedEventArgs<object> e)
    {
        var row = SelectedModuleVersion();
        if (row is null)
        {
            SetModuleFormEnabled(false);
            ModuleSelectedTitle.Text = "当前未选中任何模块版本；下面的表单在选中后才可编辑。";
            return;
        }
        SetModuleFormEnabled(true);
        ModuleSelectedTitle.Text = "当前选中：" + (string.IsNullOrWhiteSpace(row.Family) ? row.Id : row.Family) + " " + row.Version;
        ModuleNameBox.Text = string.IsNullOrWhiteSpace(row.Family) ? row.Id : row.Family;
        ModuleVersionBox.Text = row.Version;
        ModulePurposeBox.Text = row.Purpose;
        if (!string.IsNullOrWhiteSpace(row.Path)) ModuleUrlBox.Text = row.Path;
        ModuleStatus.Text = row.Label;
    }

    private void SetModuleFormEnabled(bool on)
    {
        ModuleNameBox.IsEnabled = on;
        ModuleVersionBox.IsEnabled = on;
        ModulePurposeBox.IsEnabled = on;
        ModuleUrlBox.IsEnabled = on;
        PreloadModuleButton.IsEnabled = on;
        SaveModuleButton.IsEnabled = on;
        DeleteModuleButton.IsEnabled = on;
    }

    private async void PreloadModule_Click(object sender, RoutedEventArgs e)
    {
        var row = SelectedModuleVersion();
        if (row is null || string.IsNullOrWhiteSpace(row.Path))
        {
            ModuleStatus.Text = "先在树里选一个模块版本。";
            return;
        }
        try
        {
            await _bridge.InvokeAsync("modules.download", new { id = string.IsNullOrWhiteSpace(row.Family) ? row.Id : row.Family, url = row.Path });
            ModuleStatus.Text = "已预载到仓库。";
            await RefreshAsync();
        }
        catch (Exception ex)
        {
            ModuleStatus.Text = ex.Message;
        }
    }

    private async void SaveModule_Click(object sender, RoutedEventArgs e)
    {
        var row = SelectedModuleVersion();
        if (row is null)
        {
            ModuleStatus.Text = "先选一个已预载的版本再改。";
            return;
        }
        try
        {
            await _bridge.InvokeAsync("modules.update", new
            {
                family = row.Family,
                version = row.Version,
                fields = new { label = ModuleNameBox.Text.Trim(), purpose = ModulePurposeBox.Text.Trim(), url = ModuleUrlBox.Text.Trim() },
            });
            ModuleStatus.Text = "已保存。目录内置项不能改。";
            await RefreshAsync();
        }
        catch (Exception ex)
        {
            ModuleStatus.Text = ex.Message;
        }
    }

    // F3: all destructive deletes require an explicit confirmation. Deleting is
    // best-effort but unrecoverable, so a modal Yes/No gate is mandatory.
    private static bool ConfirmDelete(string title, string detail)
    {
        return MessageBox.Show(detail, title, MessageBoxButton.YesNo, MessageBoxImage.Warning) == MessageBoxResult.Yes;
    }

    private async void DeleteModule_Click(object sender, RoutedEventArgs e)
    {
        var row = SelectedModuleVersion();
        if (row is null)
        {
            ModuleStatus.Text = "先选要删的版本。";
            return;
        }
        if (!ConfirmDelete("删除模块版本", $"确定删除模块版本：\n{row.Family} {row.Version}\n\n此操作不可撤销。"))
            return;
        try
        {
            await _bridge.InvokeAsync("modules.delete", new { family = row.Family, version = row.Version });
            ModuleStatus.Text = "已删除该版本。";
            await RefreshAsync();
        }
        catch (Exception ex)
        {
            ModuleStatus.Text = ex.Message;
        }
    }

    private async void DeleteWheel_Click(object sender, RoutedEventArgs e)
    {
        if (WheelList.SelectedItem is not ResourceRow row || string.IsNullOrWhiteSpace(row.Path))
        {
            WheelStatus.Text = "先选仓库里的一颗 wheel。";
            return;
        }
        if (row.Label.StartsWith("本机", StringComparison.Ordinal))
        {
            WheelStatus.Text = "不能删除本机运行时内核；只能删「仓库 ·」里的项。";
            return;
        }
        if (!ConfirmDelete("删除核心组件包", $"确定删除 wheel：\n{row.Path}\n\n此操作不可撤销。"))
            return;
        try
        {
            await _bridge.InvokeAsync("wheels.delete", new { path = row.Path });
            await RefreshAsync();
        }
        catch (Exception ex)
        {
            WheelStatus.Text = ex.Message;
        }
    }

    private async void DeleteResource_Click(object sender, RoutedEventArgs e)
    {
        if (ResourceList.SelectedItem is not ResourceRow row || string.IsNullOrWhiteSpace(row.Path))
        {
            ResourceStatus.Text = "先选要删的文件。";
            return;
        }
        if (!ConfirmDelete("删除用户资源", $"确定删除资源文件：\n{row.Path}\n\n此操作不可撤销。"))
            return;
        try
        {
            await _bridge.InvokeAsync("resources.delete", new { path = row.Path });
            await RefreshAsync();
        }
        catch (Exception ex)
        {
            ResourceStatus.Text = ex.Message;
        }
    }

    private async void DownloadModule_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            await _bridge.InvokeAsync("modules.download", new { url = ModuleUrlBox.Text.Trim() });
            await RefreshAsync();
        }
        catch (Exception ex)
        {
            ModuleStatus.Text = ex.Message;
        }
    }

    private async void ImportModule_Click(object sender, RoutedEventArgs e)
    {
        var picker = new OpenFileDialog { Title = "导入开源模块文件", Filter = "所有文件|*.*" };
        if (picker.ShowDialog() != true) return;
        try
        {
            await _bridge.InvokeAsync("modules.import", new { path = picker.FileName });
            await RefreshAsync();
        }
        catch (Exception ex)
        {
            ModuleStatus.Text = ex.Message;
        }
    }

    private void OpenResourceDir_Click(object sender, RoutedEventArgs e)
    {
        var dir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ProjectFactory", "user_warehouse");
        System.IO.Directory.CreateDirectory(dir);
        ShellActions.OpenPath(dir);
    }

    // F18: per-block search boxes filter the visible rows by name or path without a backend round-trip.
    private void ToolSearch_TextChanged(object sender, TextChangedEventArgs e) => SetListFilter(_tools, ToolSearch.Text);
    private void FactoryLineSearch_TextChanged(object sender, TextChangedEventArgs e) => SetListFilter(_lines, FactoryLineSearch.Text);
    private void WheelSearch_TextChanged(object sender, TextChangedEventArgs e) => SetListFilter(_wheels, WheelSearch.Text);
    private void ResourceSearch_TextChanged(object sender, TextChangedEventArgs e) => SetListFilter(_resources, ResourceSearch.Text);

    private static void SetListFilter(ObservableCollection<ResourceRow> src, string q)
    {
        var view = CollectionViewSource.GetDefaultView(src);
        if (string.IsNullOrWhiteSpace(q))
        {
            view.Filter = null;
            return;
        }
        var ql = q.ToLowerInvariant();
        view.Filter = o => o is ResourceRow r
            && ((r.Label ?? "").ToLowerInvariant().Contains(ql) || (r.Path ?? "").ToLowerInvariant().Contains(ql));
    }
}

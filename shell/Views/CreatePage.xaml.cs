using System.Text.Json;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using Microsoft.Win32;
using ProjectFactory.Workbench.Models;
using ProjectFactory.Workbench.Services;
using Wpf.Ui;
using Wpf.Ui.Controls;
using Button = Wpf.Ui.Controls.Button;
using CheckBox = System.Windows.Controls.CheckBox;
using ComboBox = System.Windows.Controls.ComboBox;
using TextBlock = System.Windows.Controls.TextBlock;
using WrapPanel = System.Windows.Controls.WrapPanel;

namespace ProjectFactory.Workbench.Views;

public partial class CreatePage : Page
{
    private readonly PythonBridgeClient _bridge;
    private readonly ShellSettings _settings;
    private readonly INavigationService _navigation;
    private JsonElement? _matrix;
    private JsonElement? _catalog;
    private readonly Dictionary<string, JsonElement> _selected = new();
    private readonly Dictionary<string, CheckBox> _moduleBoxes = new();
    private readonly Dictionary<string, string> _aliasToId = new(StringComparer.OrdinalIgnoreCase);
    private JsonElement _fieldsCache;
    private readonly Dictionary<string, HashSet<string>> _bodyCompatibility = new(StringComparer.OrdinalIgnoreCase);
    private bool _syncing;
    private string _resultRoot = "";
    private string _resultZip = "";

    public CreatePage(PythonBridgeClient bridge, ShellSettings settings, INavigationService navigation)
    {
        _bridge = bridge;
        _settings = settings;
        _navigation = navigation;
        InitializeComponent();
        OutputDirText.Text = _settings.DefaultOutputDirectory;
        Loaded += async (_, _) =>
        {
            await LoadCatalogAsync();
        };
    }

    public void StartFresh(string? requirement = null)
    {
        RequirementTextBox.Text = requirement ?? "";
        AnalyzeStatus.Text = App.L("Ms_C_AnalyzeStatus");
        _matrix = null;
        _selected.Clear();
        RefreshSelectedLabel();
        RefreshChips();
        SetStep(1);
        Dispatcher.BeginInvoke(new Action(() => RequirementTextBox.Focus()));
    }

    private void SetStep(int step)
    {
        DescribePanel.Visibility = step == 1 ? Visibility.Visible : Visibility.Collapsed;
        ReviewPanel.Visibility = step == 2 ? Visibility.Visible : Visibility.Collapsed;
        ResultPanel.Visibility = step == 3 ? Visibility.Visible : Visibility.Collapsed;
        if (step == 1)
            _ = LoadCatalogAsync();
        Step1Badge.Background = ThemeBrush(step >= 1 ? "AccentFillColorDefaultBrush" : "ControlFillColorDefaultBrush");
        Step2Badge.Background = ThemeBrush(step >= 2 ? "AccentFillColorDefaultBrush" : "ControlFillColorDefaultBrush");
        Step3Badge.Background = ThemeBrush(step >= 3 ? "AccentFillColorDefaultBrush" : "ControlFillColorDefaultBrush");
        Step1Text.Foreground = step >= 1 ? ThemeBrush("TextOnAccentFillColorPrimaryBrush", "TextFillColorPrimaryBrush") : ThemeBrush("TextFillColorSecondaryBrush");
        Step2Text.Foreground = step >= 2 ? ThemeBrush("TextOnAccentFillColorPrimaryBrush", "TextFillColorPrimaryBrush") : ThemeBrush("TextFillColorSecondaryBrush");
        Step3Text.Foreground = step >= 3 ? ThemeBrush("TextOnAccentFillColorPrimaryBrush", "TextFillColorPrimaryBrush") : ThemeBrush("TextFillColorSecondaryBrush");
        // F8: reset scroll to top on every step change so the page never looks "broken"
        // (the old behaviour left the user scrolled halfway down after switching steps).
        RootScroll?.ScrollToTop();
    }

    private static System.Windows.Media.Brush ThemeBrush(string key, string? fallbackKey = null)
    {
        if (Application.Current?.TryFindResource(key) is System.Windows.Media.Brush brush)
            return brush;
        if (fallbackKey is not null && Application.Current?.TryFindResource(fallbackKey) is System.Windows.Media.Brush fallback)
            return fallback;
        return System.Windows.Media.Brushes.White;
    }

    private async Task LoadCatalogAsync()
    {
        // A4(R2): 目录已加载则直接复用，避免每次回到 Step1 / 新建都冷启动一次 Python 进程。
        if (_catalog is not null) return;
        try
        {
            var result = await _bridge.InvokeAsync("catalog.gui");
            if (!result.TryGetProperty("catalog", out var catalog)) return;
            _catalog = catalog.Clone();
            RenderCatalog(catalog);
            if (catalog.TryGetProperty("field_options", out var fields))
            {
                FillExplained(WorkProductsBox, fields, "work_products");
                FillExplained(RequiredTechBox, fields, "languages");
                FillExplained(BodyBox, fields, "bodies");
                FillExplained(QualityBox, fields, "quality");
                FillExplained(PreferredTechBox, fields, "preferred");
                FillExplained(ProhibitedTechBox, fields, "prohibited");
                FillExplained(TargetsBox, fields, "targets");
                FillExplained(HardConstraintsBox, fields, "constraints");
                FillExplained(LifecycleBox, fields, "lifecycle");
                FillExplained(ScaleBox, fields, "scale");
                RenderModuleChecks(fields);
            }
            // T06：缓存 field_options 与车身兼容性，供动态门禁使用
            if (_catalog is JsonElement cat && cat.TryGetProperty("field_options", out var fopts))
                _fieldsCache = fopts.Clone();
            if (_catalog is JsonElement cat2 && cat2.TryGetProperty("body_compatibility", out var bc) && bc.ValueKind == JsonValueKind.Object)
            {
                _bodyCompatibility.Clear();
                foreach (var kv in bc.EnumerateObject())
                {
                    var set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                    if (kv.Value.ValueKind == JsonValueKind.Array)
                        foreach (var b in kv.Value.EnumerateArray())
                            if (b.ValueKind == JsonValueKind.String) set.Add(b.GetString()!);
                    _bodyCompatibility[kv.Name] = set;
                }
            }
            BindAiStrip();
        }
        catch (Exception ex)
        {
            AnalyzeStatus.Text = App.L("Ms_C_CatalogLoadFail") + ex.Message;
        }
    }

    private static IEnumerable<string> Strings(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out var arr) || arr.ValueKind != JsonValueKind.Array)
            yield break;
        foreach (var item in arr.EnumerateArray())
        {
            var text = item.ValueKind == JsonValueKind.String ? item.GetString() : item.ToString();
            if (!string.IsNullOrWhiteSpace(text)) yield return text!;
        }
    }

    private static void FillCombo(ComboBox box, IEnumerable<string> items)
    {
        box.Items.Clear();
        foreach (var item in items.Where(x => !string.IsNullOrWhiteSpace(x)).Distinct())
            box.Items.Add(item);
    }

    private static string SanitizePurpose(string purpose)
    {
        if (string.IsNullOrWhiteSpace(purpose)) return "";
        var t = purpose.Trim();
        if (t.Equals("catalog", StringComparison.OrdinalIgnoreCase) || t.Equals("catlog", StringComparison.OrdinalIgnoreCase)) return "";
        return t;
    }

    private void FillExplained(ComboBox box, JsonElement fields, string name)
    {
        var options = new List<CatalogOption>();
        if (fields.TryGetProperty(name, out var arr) && arr.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in arr.EnumerateArray())
            {
                var id = JsonView.String(item, "id");
                var label = JsonView.String(item, "label", id);
                var purpose = SanitizePurpose(JsonView.String(item, "purpose"));
                var source = SanitizePurpose(JsonView.String(item, "source"));
                // Empty purpose should not show "catalog" as source
                if (string.IsNullOrWhiteSpace(purpose) && (source.Equals("catalog", StringComparison.OrdinalIgnoreCase) || source.Equals("catlog", StringComparison.OrdinalIgnoreCase)))
                    source = "";
                var blurb = string.IsNullOrWhiteSpace(purpose) ? source : (string.IsNullOrWhiteSpace(source) ? purpose : purpose + "  " + App.L("Ms_C_Source") + source);
                // T06：数据驱动可用性标注（来自内核 registry，不硬编码业务清单）
                var available = item.TryGetProperty("available", out var av) ? av.ValueKind == JsonValueKind.True : true;
                var reason = "";
                if (!available)
                {
                    reason = item.TryGetProperty("reason", out var rr) ? (rr.ValueKind == JsonValueKind.String ? rr.GetString() ?? "" : "") : App.L("Ms_C_CannotGen");
                    if (!string.IsNullOrWhiteSpace(reason))
                        blurb = blurb + (string.IsNullOrWhiteSpace(blurb) ? "" : "  ") + "⚠ " + reason;
                }
                if (!string.IsNullOrWhiteSpace(id))
                {
                    _aliasToId[id] = id;
                    if (!string.IsNullOrWhiteSpace(label)) _aliasToId[label] = id;
                    var head = label.Split('·')[0].Trim();
                    if (!string.IsNullOrWhiteSpace(head)) _aliasToId[head] = id;
                }
                options.Add(new CatalogOption { Id = id, Title = string.IsNullOrWhiteSpace(label) ? id : label, Blurb = blurb, Available = available, Reason = reason });
            }
        }
        _syncing = true;
        box.ItemsSource = options;
        box.SelectedItem = null;
        _syncing = false;
        if (name is "work_products" or "bodies")
            SetItemContainerStyle(box);
    }

    private void SelectOption(ComboBox box, string id)
    {
        var mapped = MapToken(id);
        _syncing = true;
        if (box.ItemsSource is IEnumerable<CatalogOption> options)
            box.SelectedItem = options.FirstOrDefault(item => string.Equals(item.Id, mapped, StringComparison.OrdinalIgnoreCase));
        else
            box.SelectedItem = null;
        _syncing = false;
        ShowHint(box);
    }

    private void ShowHint(ComboBox box)
    {
        var blurb = (box.SelectedItem as CatalogOption)?.Blurb ?? "";
        if (box == RequiredTechBox) LanguageHint.Text = blurb;
        else if (box == BodyBox) BodyHint.Text = blurb;
        else if (box == QualityBox) QualityHint.Text = blurb;
        else if (box == WorkProductsBox) WorkProductHint.Text = blurb;
    }

    /// <summary>
    /// T06：让不可用的下拉项在界面上变灰且不可选。原因已拼进 Blurb，禁用项仍可读。
    /// 仅用于携带 Available 字段的下拉（工作产品 / 车身）。
    /// </summary>
    private static void SetItemContainerStyle(ComboBox box)
    {
        var style = new Style(typeof(ComboBoxItem));
        var dt = new DataTrigger { Binding = new Binding("Available") { Mode = BindingMode.OneWay }, Value = false };
        dt.Setters.Add(new Setter(UIElement.IsEnabledProperty, false));
        style.Triggers.Add(dt);
        box.ItemContainerStyle = style;
    }

    private static string BodyReason(string wp, string body) =>
        string.Format(App.L("Ms_C_NoLine"), wp, body);

    /// <summary>
    /// T06：根据当前选中的工作产品，动态收敛车身下拉——只保留内核真能解出的车身，
    /// 禁用其余并附人话原因；若当前车身因此变为不可用则清空选择。
    /// 未选工作产品时 fail-safe：车身全部放开（留给生成阶段校验）。
    /// </summary>
    private void ApplyBodyGating()
    {
        if (_fieldsCache.ValueKind == JsonValueKind.Undefined) return;
        if (!_fieldsCache.TryGetProperty("bodies", out var arr) || arr.ValueKind != JsonValueKind.Array) return;
        var wp = WorkProductsBox.SelectedItem as CatalogOption;
        _bodyCompatibility.TryGetValue(wp?.Id ?? "", out var compatible);
        var hasWp = wp is not null && compatible is not null;
        var options = new List<CatalogOption>();
        foreach (var item in arr.EnumerateArray())
        {
            var id = JsonView.String(item, "id");
            var label = JsonView.String(item, "label", id);
            var purpose = SanitizePurpose(JsonView.String(item, "purpose"));
            var source = SanitizePurpose(JsonView.String(item, "source"));
            var blurb = string.IsNullOrWhiteSpace(purpose) ? source : (string.IsNullOrWhiteSpace(source) ? purpose : purpose + "  " + App.L("Ms_C_Source") + source);
            var available = !hasWp || string.IsNullOrWhiteSpace(id) || compatible!.Contains(id, StringComparer.OrdinalIgnoreCase);
            var reason = "";
            if (!available)
            {
                reason = BodyReason(wp!.Id, id);
                blurb = blurb + (string.IsNullOrWhiteSpace(blurb) ? "" : "  ") + "⚠ " + reason;
            }
            options.Add(new CatalogOption { Id = id, Title = string.IsNullOrWhiteSpace(label) ? id : label, Blurb = blurb, Available = available, Reason = reason });
        }
        _syncing = true;
        BodyBox.ItemsSource = options;
        if (hasWp && BodyBox.SelectedItem is CatalogOption sel && !string.IsNullOrWhiteSpace(sel.Id) && !compatible!.Contains(sel.Id, StringComparer.OrdinalIgnoreCase))
            BodyBox.SelectedItem = null;
        _syncing = false;
        SetItemContainerStyle(BodyBox);
        ShowHint(BodyBox);
    }

    private string MapToken(string text)
    {
        var token = text.Trim();
        if (token.Contains('·')) token = token.Split('·')[0].Trim();
        if (_aliasToId.TryGetValue(token, out var id)) return id;
        return token;
    }

    private void RenderModuleChecks(JsonElement fields)
    {
        ModuleCheckHost.Children.Clear();
        _moduleBoxes.Clear();
        if (!fields.TryGetProperty("work_products", out var arr) || arr.ValueKind != JsonValueKind.Array) return;
        var groups = new Dictionary<string, WrapPanel>();
        foreach (var item in arr.EnumerateArray())
        {
            var group = JsonView.String(item, "group", App.L("Ms_C_Other"));
            if (!groups.TryGetValue(group, out var wrap))
            {
                ModuleCheckHost.Children.Add(new TextBlock { Text = group, FontWeight = FontWeights.SemiBold, Margin = new Thickness(0, 8, 0, 4) });
                wrap = new WrapPanel();
                groups[group] = wrap;
                ModuleCheckHost.Children.Add(wrap);
            }
            var id = JsonView.String(item, "id");
            // T06：数据驱动可用性标注——无产线的模块禁用并附人话原因
            var available = item.TryGetProperty("available", out var av) ? av.ValueKind == JsonValueKind.True : true;
            var reason = item.TryGetProperty("reason", out var rr) ? (rr.ValueKind == JsonValueKind.String ? rr.GetString() ?? "" : "") : "";
            var tip = JsonView.String(item, "purpose") + "\n" + App.L("Ms_C_Source") + JsonView.String(item, "source")
                      + (available ? "" : "\n⚠ " + (reason.Length > 0 ? reason : App.L("Ms_C_CannotGen")));
            var box = new CheckBox
            {
                Content = JsonView.String(item, "label", id),
                Tag = id,
                Margin = new Thickness(0, 0, 14, 6),
                ToolTip = tip,
                IsEnabled = available,
            };
            box.Checked += ModuleCheckChanged;
            box.Unchecked += ModuleCheckChanged;
            _moduleBoxes[id] = box;
            wrap.Children.Add(box);
        }
    }

    private void ModuleCheckChanged(object sender, RoutedEventArgs e)
    {
        if (_syncing) return;
        var first = _moduleBoxes.FirstOrDefault(kv => kv.Value.IsChecked == true).Key;
        if (!string.IsNullOrWhiteSpace(first))
            SelectOption(WorkProductsBox, first);
        _ = UpdateSelectionWarnings();
    }

    private void SyncModuleChecks(string csv)
    {
        _syncing = true;
        var set = csv.Replace('，', ',').Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToHashSet(StringComparer.OrdinalIgnoreCase);
        foreach (var kv in _moduleBoxes)
            kv.Value.IsChecked = set.Contains(kv.Key);
        _syncing = false;
        _ = UpdateSelectionWarnings();
    }

    /// <summary>
    /// Live, pre-flight selection advisor. Calls the Python bridge "advise" action and shows
    /// mutual-exclusion (red) / functional-overlap (amber) / tech-mismatch (amber) warnings while
    /// the user is still clicking — instead of surfacing a cryptic reject after Generate.
    /// F4: debounce + request sequencing so rapid clicks don't spawn a stampede of python.exe
    /// processes (each InvokeAsync cold-starts a new interpreter) and stale results can't clobber
    /// newer ones.
    /// </summary>
    private int _warnSeq;
    private async Task UpdateSelectionWarnings(bool debounce = true)
    {
        var mySeq = System.Threading.Interlocked.Increment(ref _warnSeq);
        try
        {
            if (debounce)
            {
                // Coalesce bursts of clicks into a single bridge call.
                await System.Threading.Tasks.Task.Delay(250);
                if (mySeq != _warnSeq) return; // a newer call already superseded us
            }
            var checkedIds = _moduleBoxes.Where(kv => kv.Value.IsChecked == true).Select(kv => kv.Key).ToArray();
            var techParts = new[] { ComboValue(RequiredTechBox), ComboValue(BodyBox) }
                .Where(x => !string.IsNullOrWhiteSpace(x)).ToArray();
            var result = await _bridge.InvokeAsync("advise", new { work_products = checkedIds, technology = techParts });
            if (mySeq != _warnSeq) return; // drop stale result from a superseded call
            if (result.ValueKind == JsonValueKind.Object && result.TryGetProperty("advice", out var advice)
                && advice.TryGetProperty("warnings", out var warnings) && warnings.ValueKind == JsonValueKind.Array
                && warnings.GetArrayLength() > 0)
            {
                var sb = new System.Text.StringBuilder();
                bool hasError = false;
                foreach (var item in warnings.EnumerateArray())
                {
                    var lvl = JsonView.String(item, "level");
                    var msg = JsonView.String(item, "msg");
                    if (lvl == "error") hasError = true;
                    sb.AppendLine("• " + msg);
                }
                SelectionWarning.Text = sb.ToString().Trim();
                SelectionWarningBorder.Visibility = Visibility.Visible;
                SelectionWarningBorder.BorderBrush = hasError
                    ? System.Windows.Media.Brushes.OrangeRed
                    : System.Windows.Media.Brushes.DarkGoldenrod;
                SelectionWarningBorder.Background = hasError
                    ? new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromArgb(30, 200, 40, 40))
                    : new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromArgb(30, 180, 140, 20));
                return;
            }
            SelectionWarningBorder.Visibility = Visibility.Collapsed;
        }
        catch
        {
            // Advisor is best-effort; never block the UI on a bridge hiccup.
            SelectionWarningBorder.Visibility = Visibility.Collapsed;
        }
    }

    private void ExplainedComboChanged(object sender, SelectionChangedEventArgs e)
    {
        if (sender is not ComboBox box) return;
        var opt = box.SelectedItem as CatalogOption;
        var blurb = opt?.Blurb ?? "";
        if (box == RequiredTechBox) LanguageHint.Text = blurb;
        else if (box == BodyBox) BodyHint.Text = blurb;
        else if (box == QualityBox) QualityHint.Text = blurb;
        else if (box == WorkProductsBox)
        {
            WorkProductHint.Text = blurb;
            if (!_syncing && opt is not null && _moduleBoxes.TryGetValue(opt.Id, out var check))
                check.IsChecked = true;
            ApplyBodyGating();
        }
        _ = UpdateSelectionWarnings();
    }

    private void BindAiStrip()
    {
        AiEnableBox.IsChecked = _settings.AiEnabled;
        CreateAiPresetBox.Items.Clear();
        if (_catalog is JsonElement catalog && catalog.TryGetProperty("ai_presets", out var presets) && presets.ValueKind == JsonValueKind.Array)
        {
            foreach (var preset in presets.EnumerateArray())
            {
                CreateAiPresetBox.Items.Add(new ComboBoxItem
                {
                    Content = JsonView.String(preset, "label"),
                    Tag = JsonView.String(preset, "endpoint") + "|" + JsonView.String(preset, "model") + "|" + JsonView.String(preset, "key_env"),
                });
            }
        }
        AiAssistStatus.Text = _settings.AiEnabled ? App.L("Ms_C_AiEnabledDesc") : App.L("Ms_C_AiDisabledDesc");
    }

    private void CreateAiChanged(object sender, RoutedEventArgs e)
    {
        _settings.AiEnabled = AiEnableBox.IsChecked == true;
        _settings.Save();
        AiAssistStatus.Text = _settings.AiEnabled ? App.L("Ms_C_AiEnabled") : App.L("Ms_C_AiDisabled");
    }

    private void CreateAiPresetChanged(object sender, SelectionChangedEventArgs e)
    {
        var tag = (CreateAiPresetBox.SelectedItem as ComboBoxItem)?.Tag?.ToString();
        if (string.IsNullOrWhiteSpace(tag)) return;
        var parts = tag.Split('|');
        if (parts.Length < 3) return;
        _settings.AiEndpoint = parts[0];
        _settings.AiModel = parts[1];
        _settings.AiKeyEnv = parts[2];
        _settings.Save();
        AiAssistStatus.Text = parts[0].Contains("11434")
            ? App.L("Ms_C_OllamaNoFill")
            : string.Format(App.L("Ms_C_PresetSelected"), (CreateAiPresetBox.SelectedItem as ComboBoxItem)?.Content, parts[2]);
    }

    private async void LoadOllamaModels_Click(object sender, RoutedEventArgs e)
    {
        AiAssistStatus.Text = App.L("Ms_C_OllamaLoading");
        try
        {
            var endpoint = string.IsNullOrWhiteSpace(_settings.AiEndpoint) ? "http://127.0.0.1:11434" : _settings.AiEndpoint;
            var result = await _bridge.InvokeAsync("ai.models", new { endpoint });
            if (result.TryGetProperty("models", out var models) && models.ValueKind == JsonValueKind.Array)
            {
                var names = models.EnumerateArray().Select(x => x.GetString() ?? "").Where(x => !string.IsNullOrWhiteSpace(x)).ToList();
                if (names.Count == 0)
                {
                    AiAssistStatus.Text = App.L("Ms_C_OllamaEmpty");
                    return;
                }
                CreateAiPresetBox.Items.Add(new ComboBoxItem { Content = App.L("Ms_C_LocalModels") + string.Join("、", names), Tag = endpoint + "|" + names[0] + "|" });
                _settings.AiEndpoint = endpoint;
                _settings.AiModel = names[0];
                _settings.AiKeyEnv = "";
                _settings.Save();
                AiAssistStatus.Text = string.Format(App.L("Ms_C_LoadedModels"), string.Join("、", names), names[0]);
            }
        }
        catch (Exception ex)
        {
            AiAssistStatus.Text = ex.Message;
        }
    }

    private void OpenSettings_Click(object sender, RoutedEventArgs e) => _navigation.Navigate(typeof(SettingsPage));

    private async void AiAssist_Click(object sender, RoutedEventArgs e)
    {
        if (!_settings.AiEnabled)
        {
            AiAssistStatus.Text = App.L("Ms_C_EnableAiFirst");
            return;
        }
        var requirement = RequirementTextBox.Text.Trim();
        if (requirement.Length < 4)
        {
            AiAssistStatus.Text = App.L("Ms_C_NeedIdea");
            return;
        }
        AiAssistStatus.Text = App.L("Ms_C_AiRewriting");
        try
        {
            var result = await _bridge.InvokeAsync("ai.assist", new { requirement, ai = _settings.AiPayload() });
            var text = JsonView.String(result, "text");
            if (!string.IsNullOrWhiteSpace(text))
                RequirementTextBox.Text = text;
            if (result.TryGetProperty("spec", out var spec) && spec.ValueKind == JsonValueKind.Object)
                ApplyImportedSpec(spec);
            AiAssistStatus.Text = App.L("Ms_C_AiRewritten");
        }
        catch (Exception ex)
        {
            AiAssistStatus.Text = App.L("Ms_C_AiRewriteFail") + ex.Message;
            try
            {
                // T07：AI 凭据缺失等同样走结构化、可复制的错误弹窗
                ErrorDialog.ShowError(ex.Message, Window.GetWindow(this));
            }
            catch
            {
                // 极端情况下弹窗不可用，状态文本已记录。
            }
        }
    }

    private async void ExportEmptyTemplate_Click(object sender, RoutedEventArgs e)
    {
        var picker = new SaveFileDialog { Title = App.L("Ms_C_ExportBlankTitle"), Filter = "YAML|*.yaml|JSON|*.json", FileName = "assembly-template.yaml" };
        if (picker.ShowDialog() != true) return;
        try
        {
            await _bridge.InvokeAsync("template.export", new { path = picker.FileName });
            AnalyzeStatus.Text = string.Format(App.L("Ms_C_ExportedBlank"), picker.FileName);
        }
        catch (Exception ex)
        {
            AnalyzeStatus.Text = App.L("Ms_C_ExportFail") + ex.Message;
        }
    }

    private void RenderCatalog(JsonElement catalog)
    {
        TemplatesHost.Children.Clear();
        CatalogHost.Children.Clear();
        if (catalog.TryGetProperty("templates", out var templates) && templates.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in templates.EnumerateArray())
            {
                var clone = item.Clone();
                var button = new Button
                {
                    // F12: render blurb inline (was only in ToolTip) so the blueprint stops
                    // looking "thin" — title + one-line description on the card itself.
                    Content = MakeBlueprintCard(JsonView.String(item, "title", App.L("Ms_C_Blueprint")), JsonView.String(item, "blurb", JsonView.String(item, "purpose", ""))),
                    Appearance = ControlAppearance.Primary,
                    Margin = new Thickness(0, 0, 8, 8),
                    Padding = new Thickness(12, 8, 12, 8),
                    HorizontalContentAlignment = HorizontalAlignment.Left,
                    ToolTip = BlueprintBlock(item),
                    Tag = JsonView.String(item, "id"),
                };
                button.Click += (_, _) => ToggleCatalogItem(clone, button);
                TemplatesHost.Children.Add(button);
            }
        }
        if (catalog.TryGetProperty("categories", out var categories) && categories.ValueKind == JsonValueKind.Array)
        {
            foreach (var category in categories.EnumerateArray())
            {
                CatalogHost.Children.Add(new TextBlock
                {
                    Text = JsonView.String(category, "title", App.L("Ms_C_Other")),
                    FontWeight = FontWeights.SemiBold,
                    Margin = new Thickness(0, 10, 0, 2),
                });
                var purpose = JsonView.String(category, "purpose");
                if (!string.IsNullOrWhiteSpace(purpose))
                    CatalogHost.Children.Add(new TextBlock { Text = purpose, FontSize = 12, Opacity = 0.62, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 6) });
                var wrap = new WrapPanel();
                if (category.TryGetProperty("items", out var items) && items.ValueKind == JsonValueKind.Array)
                {
                    foreach (var item in items.EnumerateArray())
                    {
                        var clone = item.Clone();
                        var button = new Button
                        {
                            // F12: category items also show their purpose inline instead of only in ToolTip.
                            Content = MakeBlueprintCard(JsonView.String(item, "label", item.ToString()), JsonView.String(item, "purpose", "")),
                            Appearance = ControlAppearance.Secondary,
                            Margin = new Thickness(0, 0, 8, 8),
                            Padding = new Thickness(10, 6, 10, 6),
                            HorizontalContentAlignment = HorizontalAlignment.Left,
                            ToolTip = JsonView.String(item, "purpose") + "\n" + App.L("Ms_C_Source") + JsonView.String(item, "source"),
                            Tag = JsonView.String(item, "id"),
                        };
                        button.Click += (_, _) => ToggleCatalogItem(clone, button);
                        wrap.Children.Add(button);
                    }
                }
                CatalogHost.Children.Add(wrap);
            }
        }
    }

    private void ToggleCatalogItem(JsonElement item, Button button)
    {
        var id = JsonView.String(item, "id");
        if (string.IsNullOrWhiteSpace(id)) return;
        // F1/F2: "空目录" is now a normal selectable option on step 1 — it stays
        // on this step, never wipes the user's typed requirement, and never jumps.
        if (item.TryGetProperty("blank", out var blank) && blank.ValueKind == JsonValueKind.True)
        {
            if (_selected.Remove("tpl-blank"))
            {
                button.Appearance = ControlAppearance.Primary;
            }
            else
            {
                _selected["tpl-blank"] = item;
                button.Appearance = ControlAppearance.Success;
                BlankProject_Click(button, new RoutedEventArgs());
            }
            SyncCatalogButtonAppearance();
            ApplySelectionAxes();
            RefreshSelectedLabel();
            RefreshChips();
            return;
        }
        // T40：蓝图不再写进需求文本框（避免污染用户自己的话），改由顶部标签 + 结构化字段承载。
        if (_selected.Remove(id))
        {
            button.Appearance = id.StartsWith("tpl-", StringComparison.Ordinal) ? ControlAppearance.Primary : ControlAppearance.Secondary;
        }
        else
        {
            _selected[id] = item;
            button.Appearance = ControlAppearance.Success;
            ApplySpecFromCatalogItem(item);
        }
        SyncCatalogButtonAppearance();
        ApplySelectionAxes();
        RefreshSelectedLabel();
        RefreshChips();
    }

    private static string BlueprintBlock(JsonElement item)
    {
        var products = item.TryGetProperty("work_products", out var arr) && arr.ValueKind == JsonValueKind.Array ? JsonView.Csv(arr) : "";
        return string.Format(App.L("Ms_C_BlueprintBlock"),
            JsonView.String(item, "id"),
            JsonView.String(item, "title", JsonView.String(item, "label")),
            JsonView.String(item, "purpose", JsonView.String(item, "demand")),
            products,
            JsonView.String(item, "language"),
            JsonView.String(item, "body"),
            JsonView.String(item, "repo", "single-package"));
    }

    // F12: build a compact card (title + one-line blurb) so blueprint buttons no longer
    // look "thin". The full detail stays available in the ToolTip (BlueprintBlock).
    private static System.Windows.FrameworkElement MakeBlueprintCard(string title, string blurb)
    {
        var panel = new StackPanel { MinWidth = 200, MaxWidth = 260 };
        panel.Children.Add(new TextBlock { Text = title, FontWeight = FontWeights.SemiBold, TextWrapping = TextWrapping.Wrap, FontSize = 13 });
        if (!string.IsNullOrWhiteSpace(blurb))
        {
            var blurbBlock = new TextBlock
            {
                Text = blurb,
                FontSize = 11,
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(0, 3, 0, 0),
            };
            if (Application.Current?.TryFindResource("TextFillColorSecondaryBrush") is System.Windows.Media.Brush b)
                blurbBlock.Foreground = b;
            panel.Children.Add(blurbBlock);
        }
        return panel;
    }

    private void ApplySpecFromCatalogItem(JsonElement item)
    {
        if (item.TryGetProperty("work_products", out var products) && products.ValueKind == JsonValueKind.Array)
            SyncModuleChecks(JsonView.Csv(products));
        var language = JsonView.String(item, "language");
        if (!string.IsNullOrWhiteSpace(language)) SelectOption(RequiredTechBox, language);
        var body = JsonView.String(item, "body");
        if (!string.IsNullOrWhiteSpace(body)) SelectOption(BodyBox, body);
        if (string.IsNullOrWhiteSpace(ProjectNameBox.Text))
            ProjectNameBox.Text = SuggestProjectName(JsonView.String(item, "title", JsonView.String(item, "label")), JsonView.String(item, "id"));
        // F16: only fill PurposeBox from the blueprint when the user hasn't already typed one,
        // so clicking a blueprint never silently wipes their own words.
        if (string.IsNullOrWhiteSpace(PurposeBox.Text))
            PurposeBox.Text = JsonView.String(item, "purpose", JsonView.String(item, "demand"));
    }

    // T40：蓝图不再以 DSL 文本写入需求框，故不再需要 AppendDemandLine / RemoveDemandLine。

    private void ApplySelectionAxes()
    {
        var products = new List<string>();
        foreach (var item in _selected.Values)
            if (item.TryGetProperty("work_products", out var arr) && arr.ValueKind == JsonValueKind.Array)
                products.AddRange(arr.EnumerateArray().Select(x => x.GetString() ?? "").Where(x => !string.IsNullOrWhiteSpace(x)));
        if (products.Count > 0)
        {
            SyncModuleChecks(string.Join(", ", products.Distinct()));
            SelectOption(WorkProductsBox, products[0]);
        }
        var languages = _selected.Values.Select(item => JsonView.String(item, "language")).Where(x => !string.IsNullOrWhiteSpace(x)).Distinct().ToList();
        if (languages.Count == 1) SelectOption(RequiredTechBox, languages[0]);
        var bodies = _selected.Values.Select(item => JsonView.String(item, "body")).Where(x => !string.IsNullOrWhiteSpace(x)).Distinct().ToList();
        if (bodies.Count == 1) SelectOption(BodyBox, bodies[0]);
        AnalyzeStatus.Text = App.L("Ms_C_AxesSummary");
    }

    private void RefreshSelectedLabel()
    {
        if (_selected.Count == 0)
        {
            SelectedModulesText.Text = App.L("Ms_C_NoBlueprint");
            RefreshSelectionMeta();
            return;
        }
        SelectedModulesText.Text = string.Format(App.L("Ms_C_SelectedCount"), _selected.Count) + string.Join("、", _selected.Values.Select(item => JsonView.String(item, "label", JsonView.String(item, "title"))));
        RefreshSelectionMeta();
    }

    // F14/F15: surface "what you'll get" as a persistent preview and flag conflicting
    // language/body selections inline, instead of burying it all in the ToolTip.
    private void RefreshSelectionMeta()
    {
        if (_selected.Count == 0)
        {
            SelectedPreviewText.Visibility = Visibility.Collapsed;
            SelectionConflictText.Visibility = Visibility.Collapsed;
            return;
        }
        var products = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var langs = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var bodies = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var repos = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var item in _selected.Values)
        {
            if (item.TryGetProperty("work_products", out var wp) && wp.ValueKind == JsonValueKind.Array)
                foreach (var x in wp.EnumerateArray()) if (x.ValueKind == JsonValueKind.String) products.Add(x.GetString()!);
            if (item.TryGetProperty("language", out var l) && !string.IsNullOrWhiteSpace(l.GetString())) langs.Add(l.GetString()!);
            if (item.TryGetProperty("body", out var b) && !string.IsNullOrWhiteSpace(b.GetString())) bodies.Add(b.GetString()!);
            if (item.TryGetProperty("repo", out var r) && !string.IsNullOrWhiteSpace(r.GetString())) repos.Add(r.GetString()!);
        }
        SelectedPreviewText.Text = string.Format(App.L("Ms_C_PreviewSummary"),
            products.Count == 0 ? App.L("Ms_C_NotSpecified") : string.Join("、", products),
            langs.Count == 0 ? App.L("Ms_C_NotSpecified") : string.Join("、", langs),
            bodies.Count == 0 ? App.L("Ms_C_NotSpecified") : string.Join("、", bodies),
            repos.Count == 0 ? App.L("Ms_C_NotSpecified") : string.Join("、", repos));
        SelectedPreviewText.Visibility = Visibility.Visible;

        var conflicts = new List<string>();
        if (langs.Count > 1) conflicts.Add(string.Format(App.L("Ms_C_ConflictLang"), string.Join("、", langs)));
        if (bodies.Count > 1) conflicts.Add(string.Format(App.L("Ms_C_ConflictBody"), string.Join("、", bodies)));
        if (conflicts.Count > 0)
        {
            SelectionConflictText.Text = "• " + string.Join("\n• ", conflicts);
            SelectionConflictText.Visibility = Visibility.Visible;
        }
        else
        {
            SelectionConflictText.Visibility = Visibility.Collapsed;
        }
    }

    // T40：把已选蓝图渲染成可删除的标签（Chip），不再污染需求文本框。
    private void RefreshChips()
    {
        SelectedChipHost.Children.Clear();
        SelectedChipHost.Visibility = _selected.Count == 0 ? Visibility.Collapsed : Visibility.Visible;
        foreach (var item in _selected.Values)
        {
            var id = JsonView.String(item, "id");
            var label = JsonView.String(item, "label", JsonView.String(item, "title", id));
            var chip = new Border
            {
                CornerRadius = new CornerRadius(14),
                Padding = new Thickness(10, 4, 6, 4),
                Margin = new Thickness(0, 0, 8, 8),
                Background = Application.Current?.TryFindResource("AccentFillColorDefaultBrush") is System.Windows.Media.Brush b ? b : System.Windows.Media.Brushes.SteelBlue,
                Cursor = System.Windows.Input.Cursors.Hand,
            };
            var panel = new StackPanel { Orientation = Orientation.Horizontal };
            panel.Children.Add(new TextBlock { Text = label, Foreground = System.Windows.Media.Brushes.White, FontSize = 12, VerticalAlignment = VerticalAlignment.Center });
            var close = new Button
            {
                Content = "✕",
                FontSize = 11,
                Padding = new Thickness(6, 0, 6, 0),
                Margin = new Thickness(6, 0, 0, 0),
                Appearance = ControlAppearance.Secondary,
                Foreground = System.Windows.Media.Brushes.White,
            };
            var localId = id;
            var localItem = item;
            close.Click += (_, _) =>
            {
                var btn = FindCatalogButton(localId);
                if (btn is not null) ToggleCatalogItem(localItem, btn);
                else
                {
                    _selected.Remove(localId);
                    SyncCatalogButtonAppearance();
                    ApplySelectionAxes();
                    RefreshSelectedLabel();
                    RefreshChips();
                }
            };
            panel.Children.Add(close);
            chip.Child = panel;
            SelectedChipHost.Children.Add(chip);
        }
    }

    // 同步所有蓝图按钮的选中外观（模板区与分类区可能存在同一 id 的两个按钮）。
    private void SyncCatalogButtonAppearance()
    {
        foreach (var host in new System.Collections.Generic.List<System.Windows.Controls.Panel> { TemplatesHost, CatalogHost })
            foreach (var child in host.Children)
                if (child is Button b && b.Tag is string id)
                    b.Appearance = _selected.ContainsKey(id)
                        ? ControlAppearance.Success
                        : (id.StartsWith("tpl-", StringComparison.Ordinal) ? ControlAppearance.Primary : ControlAppearance.Secondary);
    }

    private Button? FindCatalogButton(string id)
    {
        foreach (var host in new System.Collections.Generic.List<System.Windows.Controls.Panel> { TemplatesHost, CatalogHost })
            foreach (var child in host.Children)
                if (child is Button b && string.Equals(b.Tag as string, id, StringComparison.Ordinal))
                    return b;
        return null;
    }

    // F10: typing in the catalog search box hides non-matching blueprint buttons so the
    // 58-item catalog doesn't all have to be laid out at once (the categories are also
    // collapsed by default, which already keeps the common case to a handful of cards).
    private void CatalogSearch_TextChanged(object sender, TextChangedEventArgs e)
    {
        var q = (CatalogSearchBox.Text ?? "").Trim().ToLowerInvariant();
        FilterCatalogChildren(TemplatesHost, q);
        FilterCatalogChildren(CatalogHost, q);
    }

    private static void FilterCatalogChildren(System.Windows.Controls.Panel host, string q)
    {
        if (string.IsNullOrEmpty(q))
        {
            foreach (System.Windows.FrameworkElement child in host.Children)
                child.Visibility = Visibility.Visible;
            return;
        }
        foreach (System.Windows.FrameworkElement child in host.Children)
        {
            if (child is Button btn)
            {
                btn.Visibility = CardTitle(btn).ToLowerInvariant().Contains(q) ? Visibility.Visible : Visibility.Collapsed;
            }
            else if (child is System.Windows.Controls.Panel panel)
            {
                var match = false;
                foreach (var inner in panel.Children)
                    if (inner is Button b && CardTitle(b).ToLowerInvariant().Contains(q)) { match = true; break; }
                child.Visibility = match ? Visibility.Visible : Visibility.Collapsed;
            }
            else
            {
                child.Visibility = Visibility.Visible;
            }
        }
    }

    private static string CardTitle(Button btn)
    {
        if (btn.Content is StackPanel sp)
        {
            foreach (var c in sp.Children)
                if (c is TextBlock tb) return tb.Text ?? "";
        }
        return btn.Content?.ToString() ?? "";
    }

    private async void ExportBlueprint_Click(object sender, RoutedEventArgs e)
    {
        var picker = new SaveFileDialog { Title = App.L("Ms_C_ExportBlueprintTitle"), Filter = "JSON|*.json|YAML|*.yaml", FileName = "blueprint.json" };
        if (picker.ShowDialog() != true) return;
        try
        {
            var spec = CurrentSpec();
            await _bridge.InvokeAsync("blueprint.export", new { spec, path = picker.FileName });
            AnalyzeStatus.Text = App.L("Ms_C_Exported") + picker.FileName;
        }
        catch (Exception ex)
        {
            AnalyzeStatus.Text = App.L("Ms_C_ExportFail") + ex.Message;
        }
    }

    private async void ImportBlueprint_Click(object sender, RoutedEventArgs e)
    {
        var picker = new OpenFileDialog { Title = App.L("Ms_C_ImportBlueprintTitle"), Filter = App.L("Ms_C_ImportBlueprintFilter") };
        if (picker.ShowDialog() != true) return;
        try
        {
            var result = await _bridge.InvokeAsync("blueprint.import", new { path = picker.FileName });
            if (!result.TryGetProperty("spec", out var spec)) return;
            ApplyImportedSpec(spec);
            AnalyzeStatus.Text = App.L("Ms_C_ImportedTemplate");
            SetStep(2);
        }
        catch (Exception ex)
        {
            AnalyzeStatus.Text = App.L("Ms_C_ImportFail") + ex.Message;
        }
    }

    private void ApplyImportedSpec(JsonElement spec)
    {
        PurposeBox.Text = JsonView.String(spec, "purpose");
        ProjectNameBox.Text = JsonView.String(spec, "project_name");
        if (spec.TryGetProperty("work_products", out var products))
        {
            var csv = JsonView.Csv(products);
            SyncModuleChecks(csv);
            SelectOption(WorkProductsBox, csv.Replace('，', ',').Split(',')[0].Trim());
        }
        SelectOption(RequiredTechBox, JsonView.String(spec, "language"));
        SelectOption(BodyBox, JsonView.String(spec, "body"));
        if (spec.TryGetProperty("options", out var options) && options.ValueKind == JsonValueKind.Object)
        {
            OptScaffold.IsChecked = Bool(options, "scaffold", true);
            OptVerify.IsChecked = Bool(options, "verification", true);
            OptOverlay.IsChecked = Bool(options, "overlay", true);
            OptHarness.IsChecked = Bool(options, "harness", true);
            OptReadme.IsChecked = Bool(options, "readme", true);
        }
        if (string.IsNullOrWhiteSpace(RequirementTextBox.Text))
            RequirementTextBox.Text = PurposeBox.Text;
        QuestionsText.Text = App.L("Ms_C_FromImported");
    }

    private static bool Bool(JsonElement obj, string name, bool fallback)
        => obj.TryGetProperty(name, out var value) && value.ValueKind is JsonValueKind.True or JsonValueKind.False ? value.GetBoolean() : fallback;

    private Dictionary<string, object?> CurrentSpec()
    {
        static string[] Csv(string text) => text.Replace('，', ',').Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var products = Csv(ComboValue(WorkProductsBox));
        var spec = new Dictionary<string, object?>
        {
            ["schema"] = "project-factory-assembly-template/1",
            ["project_name"] = ProjectNameBox.Text.Trim(),
            ["purpose"] = PurposeBox.Text.Trim() is { Length: > 0 } purpose ? purpose : RequirementTextBox.Text.Trim(),
            ["work_products"] = products,
            ["language"] = ComboValue(RequiredTechBox),
            ["body"] = ComboValue(BodyBox),
            ["options"] = BuildOptions(),
        };
        return spec;
    }

    private Dictionary<string, object?> BuildOptions() => new()
    {
        ["scaffold"] = OptScaffold.IsChecked == true,
        ["verification"] = OptVerify.IsChecked == true,
        ["overlay"] = OptOverlay.IsChecked == true,
        ["harness"] = OptHarness.IsChecked == true,
        ["readme"] = OptReadme.IsChecked == true,
    };

    // F1/F2 fix: "空目录" blueprint is now a normal selectable option on step 1.
    // It no longer jumps to step 2, no longer wipes the requirement text the user
    // typed, and no longer overwrites the project name. It only turns off the
    // optional checkboxes so the confirmed result is an empty folder — the user
    // stays on step 1 and decides when to advance.
    private void BlankProject_Click(object sender, RoutedEventArgs e)
    {
        OptScaffold.IsChecked = false;
        OptVerify.IsChecked = false;
        OptOverlay.IsChecked = false;
        OptHarness.IsChecked = false;
        OptReadme.IsChecked = false;
        QuestionsText.Text = App.L("Ms_C_BlankDir");
    }

    private async void Analyze_Click(object sender, RoutedEventArgs e) => await AnalyzeRequirement();

    private async Task AnalyzeRequirement()
    {
        var requirement = RequirementTextBox.Text.Trim();
        if (requirement.Length < 4)
        {
            AnalyzeStatus.Text = App.L("Ms_C_NeedRealIdea");
            ShowSnackbar(App.L("Ms_C_NeedRealIdea"));
            return;
        }

        AnalyzeButton.IsEnabled = false;
        SkipAnalyzeButton.IsEnabled = false;
        AiOptimizeButton.IsEnabled = false;
        AnalyzeProgress.Visibility = Visibility.Visible;
        AnalyzeStatus.Text = App.L("Ms_C_Analyzing");
        try
        {
            var result = await _bridge.InvokeAsync("analyze", new { requirement, ai = new { enabled = false } });
            _matrix = result;
            PopulateReview(result, requirement);
            SetStep(2);
        }
        catch (Exception ex)
        {
            AnalyzeStatus.Text = App.L("Ms_C_AnalyzeFail") + ex.Message;
            EnterReviewFromLocal();
        }
        finally
        {
            AnalyzeButton.IsEnabled = true;
            SkipAnalyzeButton.IsEnabled = true;
            AiOptimizeButton.IsEnabled = true;
            AnalyzeProgress.Visibility = Visibility.Collapsed;
        }
    }

    private void SkipAnalyze_Click(object sender, RoutedEventArgs e) => EnterReviewFromLocal();

    private void EnterReviewFromLocal()
    {
        ApplySelectionAxes();
        if (string.IsNullOrWhiteSpace(PurposeBox.Text))
            PurposeBox.Text = RequirementTextBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(ProjectNameBox.Text))
            ProjectNameBox.Text = SuggestProjectName(RequirementTextBox.Text, ProfileText.Text);
        QuestionsText.Text = App.L("Ms_C_NoAiReview");
        OutputDirText.Text = _settings.DefaultOutputDirectory;
        SetStep(2);
    }

    private void PopulateReview(JsonElement matrix, string requirement)
    {
        PurposeBox.Text = JsonView.RowText(matrix, "purpose");
        var products = JsonView.RowText(matrix, "work_products");
        SyncModuleChecks(products);
        var firstProduct = products.Replace('，', ',').Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).FirstOrDefault() ?? "";
        SelectOption(WorkProductsBox, firstProduct);
        var required = JsonView.RowText(matrix, "technology_required");
        var requiredTokens = required.Replace('，', ',').Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        SelectOption(RequiredTechBox, requiredTokens.FirstOrDefault() ?? "");
        foreach (var token in requiredTokens)
        {
            var mapped = MapToken(token);
            if (mapped is "react" or "vue" or "svelte" or "nextjs" or "typer" or "hono" or "nestjs" or "axum" or "clap" or "avalonia" or "commander" or "astro" or "textual")
                SelectOption(BodyBox, mapped);
        }
        SelectOption(PreferredTechBox, JsonView.RowText(matrix, "technology_preferred").Replace('，', ',').Split(',')[0].Trim());
        SelectOption(ProhibitedTechBox, JsonView.RowText(matrix, "technology_prohibited").Replace('，', ',').Split(',')[0].Trim());
        var targets = JsonView.RowObjectFieldCsv(matrix, "targets", "value");
        if (string.IsNullOrWhiteSpace(targets)) targets = JsonView.RowText(matrix, "targets");
        SelectOption(TargetsBox, targets.Replace('，', ',').Split(',')[0].Trim());
        SelectOption(HardConstraintsBox, JsonView.RowText(matrix, "hard_constraints").Replace('，', ',').Split(',')[0].Trim());
        SelectOption(LifecycleBox, JsonView.RowText(matrix, "lifecycle_stage"));
        SelectOption(ScaleBox, JsonView.RowText(matrix, "scope_scale_hint"));
        SelectOption(QualityBox, QualityCsv(matrix).Replace('，', ',').Split(',')[0].Trim());
        QuestionsText.Text = string.IsNullOrWhiteSpace(JsonView.Questions(matrix)) ? App.L("Ms_C_NoQuestions") : JsonView.Questions(matrix);
        OutputDirText.Text = _settings.DefaultOutputDirectory;

        if (matrix.TryGetProperty("profile", out var profile))
            ProfileText.Text = JsonView.String(profile, "id", JsonView.String(profile, "status", App.L("Ms_C_NoMatch")));
        else
            ProfileText.Text = App.L("Ms_C_NoMatch");

        if (string.IsNullOrWhiteSpace(ProjectNameBox.Text))
            ProjectNameBox.Text = SuggestProjectName(requirement, ProfileText.Text);
    }

    private static string QualityCsv(JsonElement matrix)
    {
        var value = JsonView.RowValue(matrix, "quality");
        if (value is null || value.Value.ValueKind != JsonValueKind.Array) return "";
        var items = new List<string>();
        foreach (var item in value.Value.EnumerateArray())
            if (item.ValueKind == JsonValueKind.Object && item.TryGetProperty("attribute", out var attr))
                items.Add(attr.GetString() ?? attr.ToString());
        return string.Join(", ", items.Where(x => !string.IsNullOrWhiteSpace(x)));
    }

    private static string SuggestProjectName(string requirement, string profile)
    {
        var prefix = profile switch
        {
            "python-library" => "python-lib",
            "browser-extension-js" => "browser-extension",
            "node-library" => "node-lib",
            _ => "my-project",
        };
        // Robustness: the Core only accepts ASCII names ([A-Za-z0-9._-]), so the
        // auto-suggestion must never produce Chinese/other-non-ASCII slugs.
        var slug = Regex.Replace(requirement.Trim(), @"[^A-Za-z0-9]+", "-").Trim('-');
        if (slug.Length >= 3) return slug.Length > 30 ? slug[..30].Trim('-') : slug;
        return prefix;
    }

    private void BackToDescribe_Click(object sender, RoutedEventArgs e) => SetStep(1);

    private void ChangeOutput_Click(object sender, RoutedEventArgs e)
    {
        var picker = new OpenFolderDialog { Title = App.L("Ms_C_OutputDirTitle"), InitialDirectory = _settings.DefaultOutputDirectory };
        if (picker.ShowDialog() == true)
        {
            _settings.DefaultOutputDirectory = picker.FolderName;
            _settings.Save();
            OutputDirText.Text = _settings.DefaultOutputDirectory;
        }
    }

    private async void Generate_Click(object sender, RoutedEventArgs e)
    {
        if (_matrix is null && OptScaffold.IsChecked == true && string.IsNullOrWhiteSpace(WorkProductsBox.Text) && string.IsNullOrWhiteSpace(RequirementTextBox.Text))
        {
            QuestionsText.Text = App.L("Ms_C_NeedAnalyzeFirst");
            ShowSnackbar(App.L("Ms_C_NeedAnalyzeFirst"));
            return;
        }
        var projectName = ProjectNameBox.Text.Trim();
        if (!Regex.IsMatch(projectName, @"^[\p{L}\p{N}][\p{L}\p{N}._-]{0,79}$"))
        {
            QuestionsText.Text = App.L("Ms_C_InvalidName");
            ShowSnackbar(App.L("Ms_C_InvalidNameShort"));
            return;
        }

        GenerateButton.IsEnabled = false;
        GenerateProgress.Visibility = Visibility.Visible;
        // F25: make the two Generate paths explicit instead of silently branching — tell the user
        // which one is about to run (需求→生成 vs 蓝图/勾选直接组装).
        var useGenerateFlow = !string.IsNullOrWhiteSpace(RequirementTextBox.Text) && OptScaffold.IsChecked == true;
        QuestionsText.Text = useGenerateFlow
            ? App.L("Ms_C_FlowGenerate")
            : App.L("Ms_C_FlowAssemble");
        try
        {
            var overrides = BuildOverrides();
            var options = BuildOptions();
            JsonElement result;
            if (string.IsNullOrWhiteSpace(RequirementTextBox.Text) || OptScaffold.IsChecked != true)
            {
                result = await _bridge.InvokeAsync("assemble", new
                {
                    project_name = projectName,
                    output_dir = _settings.DefaultOutputDirectory,
                    spec = CurrentSpec(),
                    options,
                    blank = OptScaffold.IsChecked != true && OptHarness.IsChecked != true && OptOverlay.IsChecked != true,
                });
            }
            else
            {
                result = await _bridge.InvokeAsync("generate", new
                {
                    requirement = RequirementTextBox.Text.Trim(),
                    project_name = projectName,
                    output_dir = _settings.DefaultOutputDirectory,
                    overrides,
                    options,
                    ai = _settings.AiPayload(),
                });
            }

            var status = JsonView.String(result, "status", "UNKNOWN");
            _resultRoot = JsonView.String(result, "project_root");
            _resultZip = JsonView.String(result, "project_zip");
            ResultHeadline.Text = status is "PASS" or "VERIFIED" ? App.L("Ms_C_ResultVerified") : string.Format(App.L("Ms_C_ResultWithStatus"), status);
            ResultSummary.Text = status is "PASS" or "VERIFIED"
                ? App.L("Ms_C_ResultSummaryOk")
                : App.L("Ms_C_ResultSummaryWarn");
            ResultProfile.Text = JsonView.String(result, "profile", ProfileText.Text);
            ResultRoot.Text = _resultRoot;
            ResultZip.Text = _resultZip;
            ResultClaims.Text = FormatClaims(result);

            // T14：AI 被降级时明确告知，避免静默降级造成“AI 已生效”的误解。
            if (result.TryGetProperty("ai_degraded", out var aiDeg) && aiDeg.ValueKind == JsonValueKind.Object
                && aiDeg.TryGetProperty("skipped", out var skipped) && skipped.ValueKind == JsonValueKind.True)
            {
                var reason = JsonView.String(aiDeg, "reason", App.L("Ms_C_UnknownReason"));
                var endpoint = JsonView.String(aiDeg, "endpoint", App.L("Ms_C_NotConfigured"));
                var model = JsonView.String(aiDeg, "model", App.L("Ms_C_NotConfigured"));
                ResultSummary.Text = string.Format(App.L("Ms_C_AiDegraded"), reason, endpoint, model);
            }

            SetStep(3);
        }
            catch (Exception ex)
            {
                var msg = ex.Message;
                QuestionsText.Text = App.L("Ms_C_GenerateFail") + msg;
                try
                {
                    // T07：结构化、可复制的错误弹窗（机床门禁 / 无产线 / AI 凭据 均已分类为人话三段）
                    ErrorDialog.ShowError(msg, Window.GetWindow(this));
                }
                catch
                {
                    // 极端情况下弹窗不可用，至少小字已记录。
                }
            }
        finally
        {
            GenerateButton.IsEnabled = true;
            GenerateProgress.Visibility = Visibility.Collapsed;
        }
    }

    private Dictionary<string, object?> BuildOverrides()
    {
        static string[] Csv(string text) => text.Replace('，', ',').Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var quality = Csv(ComboValue(QualityBox)).Select(x => new Dictionary<string, string> { ["attribute"] = x, ["level"] = "normal" }).ToArray();
        return new Dictionary<string, object?>
        {
            ["purpose"] = PurposeBox.Text.Trim(),
            ["work_products"] = Csv(ComboValue(WorkProductsBox)),
            ["technology_required"] = Csv(string.Join(",", new[] { ComboValue(RequiredTechBox), ComboValue(BodyBox) }.Where(x => !string.IsNullOrWhiteSpace(x)))),
            ["technology_preferred"] = Csv(ComboValue(PreferredTechBox)),
            ["technology_prohibited"] = Csv(ComboValue(ProhibitedTechBox)),
            ["targets"] = Csv(ComboValue(TargetsBox)),
            ["hard_constraints"] = Csv(ComboValue(HardConstraintsBox)),
            ["quality"] = quality,
            ["lifecycle_stage"] = ComboValue(LifecycleBox),
            ["scope_scale_hint"] = ComboValue(ScaleBox),
        };
    }

    private string ComboValue(ComboBox box)
    {
        if (box == WorkProductsBox)
        {
            var checkedIds = _moduleBoxes.Where(kv => kv.Value.IsChecked == true).Select(kv => kv.Key).ToArray();
            if (checkedIds.Length > 0) return string.Join(", ", checkedIds);
        }
        if (box.SelectedItem is CatalogOption option)
            return option.Id;
        return MapToken(box.Text);
    }

    private static string FormatClaims(JsonElement result)
    {
        if (!result.TryGetProperty("verification", out var verification))
            return App.L("Ms_C_NoClaims");
        var lines = new List<string>();
        if (verification.TryGetProperty("claims", out var claims) && claims.ValueKind == JsonValueKind.Array)
        {
            foreach (var claim in claims.EnumerateArray())
            {
                var id = JsonView.String(claim, "id", "?");
                var status = JsonView.String(claim, "status", "?");
                lines.Add($"{status,-12} {id}");
            }
        }
        if (lines.Count == 0)
            lines.Add(App.L("Ms_C_StatusLabel") + JsonView.String(verification, "status", JsonView.String(result, "status", "UNKNOWN")));
        return string.Join("\n", lines);
    }

    private void OpenProject_Click(object sender, RoutedEventArgs e) => ShellActions.OpenPath(_resultRoot);
    private void OpenZip_Click(object sender, RoutedEventArgs e) => ShellActions.OpenPath(_resultZip);
    private void StartAnother_Click(object sender, RoutedEventArgs e) => StartFresh();

    // T43：非致命提示统一走 Snackbar；失败则静默退回调用方已设置的状态文本。
    private void ShowSnackbar(string message)
    {
        try
        {
            if (Window.GetWindow(this) is MainWindow mw)
                mw.ShowAppSnackbar(message);
        }
        catch { }
    }
}

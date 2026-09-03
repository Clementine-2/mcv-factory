using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using Microsoft.Win32;
using ProjectFactory.Workbench.Services;
using ComboBoxItem = System.Windows.Controls.ComboBoxItem;

namespace ProjectFactory.Workbench.Views;

public partial class SettingsPage : Page
{
    private readonly ShellSettings _settings;
    private readonly PythonBridgeClient _bridge;
    private bool _initializing = true;

    public SettingsPage(ShellSettings settings, PythonBridgeClient bridge)
    {
        _settings = settings;
        _bridge = bridge;
        InitializeComponent();
        OutputDirectoryText.Text = _settings.DefaultOutputDirectory;
        AiEnabledBox.IsChecked = _settings.AiEnabled;
        AiEndpointBox.Text = _settings.AiEndpoint;
        AiModelBox.Text = _settings.AiModel;
        AiKeyEnvBox.Text = _settings.AiKeyEnv;
        SelectTag(ThemeBox, _settings.Theme);
        SelectTag(AccentBox, _settings.Accent);
        SelectTag(BackdropBox, _settings.Backdrop);
        SelectTag(CornerBox, _settings.CornerStyle);
        SelectTag(FontBox, _settings.FontFamilyName);
        SelectTag(FontSizeBox, _settings.FontSizeKey);
        SelectTag(BackgroundOpacityBox, _settings.BackgroundOpacityKey);
        BackgroundPathText.Text = string.IsNullOrWhiteSpace(_settings.BackgroundImage) ? "未选择" : _settings.BackgroundImage;
        AiDetails.IsEnabled = _settings.AiEnabled;
        AiPresetBox.Items.Clear();
        AiPresetBox.Items.Add(new ComboBoxItem { Content = "SpaceXAI / xAI（推荐）", Tag = "https://api.x.ai/v1/chat/completions|grok-4.5|XAI_API_KEY" });
        AiPresetBox.Items.Add(new ComboBoxItem { Content = "OpenAI", Tag = "https://api.openai.com/v1/chat/completions|gpt-4o-mini|OPENAI_API_KEY" });
        AiPresetBox.Items.Add(new ComboBoxItem { Content = "Groq", Tag = "https://api.groq.com/openai/v1/chat/completions|llama-3.3-70b-versatile|GROQ_API_KEY" });
        AiPresetBox.Items.Add(new ComboBoxItem { Content = "DeepSeek", Tag = "https://api.deepseek.com/chat/completions|deepseek-chat|DEEPSEEK_API_KEY" });
        AiPresetBox.Items.Add(new ComboBoxItem { Content = "Ollama 本机（读取已装模型）", Tag = "http://127.0.0.1:11434||" });
        _initializing = false;
    }

    private void AiPresetChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_initializing) return;
        var tag = (AiPresetBox.SelectedItem as ComboBoxItem)?.Tag?.ToString();
        if (string.IsNullOrWhiteSpace(tag)) return;
        var parts = tag.Split('|');
        if (parts.Length < 3) return;
        AiEndpointBox.Text = parts[0];
        AiModelBox.Text = parts[1];
        AiKeyEnvBox.Text = parts[2];
        SaveAiFields();
        if (parts[0].Contains("11434"))
            AiProbeText.Text = "Ollama 不写死模型名。点「读取本机 Ollama 模型」。";
    }

    private async void LoadOllamaModels_Click(object sender, RoutedEventArgs e)
    {
        AiProbeText.Text = "正在读取本机 Ollama…";
        try
        {
            var result = await _bridge.InvokeAsync("ai.models", new { endpoint = string.IsNullOrWhiteSpace(AiEndpointBox.Text) ? "http://127.0.0.1:11434" : AiEndpointBox.Text.Trim() });
            AiModelBox.Items.Clear();
            if (result.TryGetProperty("models", out var models) && models.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in models.EnumerateArray())
                {
                    var name = item.GetString();
                    if (!string.IsNullOrWhiteSpace(name))
                        AiModelBox.Items.Add(name);
                }
            }
            if (AiModelBox.Items.Count == 0)
            {
                AiProbeText.Text = "Ollama 在跑，但没有已装模型。请先 ollama pull，工厂不会替你下载。";
                return;
            }
            AiModelBox.SelectedIndex = 0;
            SaveAiFields();
            AiProbeText.Text = "读到 " + AiModelBox.Items.Count + " 个本机模型。已选 " + AiModelBox.Text + "。";
        }
        catch (Exception ex)
        {
            AiProbeText.Text = ex.Message;
        }
    }

    private async void AiProbe_Click(object sender, RoutedEventArgs e)
    {
        AiProbeText.Text = "正在探测…";
        try
        {
            var result = await _bridge.InvokeAsync("ai.probe", new { endpoint = AiEndpointBox.Text.Trim() });
            if (JsonView.String(result, "status") != "OK")
            {
                AiProbeText.Text = "失败：" + JsonView.String(result, "error");
                return;
            }
            if (result.TryGetProperty("models", out var models) && models.ValueKind == JsonValueKind.Array)
            {
                AiProbeText.Text = "Ollama 已连通。本机模型：" + string.Join("、", models.EnumerateArray().Select(x => x.GetString()).Where(x => !string.IsNullOrWhiteSpace(x)));
                return;
            }
            AiProbeText.Text = "能连上。密钥和模型还要在本机环境变量里。";
        }
        catch (Exception ex)
        {
            AiProbeText.Text = ex.Message;
        }
    }

    private void AppearanceChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_initializing) return;
        _settings.Theme = TagOf(ThemeBox, "System");
        _settings.Accent = TagOf(AccentBox, "Default");
        _settings.Backdrop = TagOf(BackdropBox, "Mica");
        _settings.CornerStyle = TagOf(CornerBox, "Round");
        _settings.FontFamilyName = TagOf(FontBox, "Microsoft YaHei UI");
        _settings.FontSizeKey = TagOf(FontSizeBox, "Default");
        _settings.BackgroundOpacityKey = TagOf(BackgroundOpacityBox, "Medium");
        _settings.Save();
        _settings.Apply(Application.Current.MainWindow);
    }

    private void ChooseBackground_Click(object sender, RoutedEventArgs e)
    {
        var picker = new OpenFileDialog
        {
            Title = "选择背景图",
            Filter = "图片|*.png;*.jpg;*.jpeg;*.bmp;*.webp|所有文件|*.*",
        };
        if (picker.ShowDialog() == true)
        {
            _settings.BackgroundImage = picker.FileName;
            BackgroundPathText.Text = picker.FileName;
            _settings.Save();
            _settings.Apply(Application.Current.MainWindow);
        }
    }

    private void ClearBackground_Click(object sender, RoutedEventArgs e)
    {
        _settings.BackgroundImage = "";
        BackgroundPathText.Text = "未选择";
        _settings.Save();
        _settings.Apply(Application.Current.MainWindow);
    }

    private void ChangeOutput_Click(object sender, RoutedEventArgs e)
    {
        var picker = new OpenFolderDialog { Title = "选择 Project Factory 默认项目目录", InitialDirectory = _settings.DefaultOutputDirectory };
        if (picker.ShowDialog() == true)
        {
            _settings.DefaultOutputDirectory = picker.FolderName;
            _settings.Save();
            OutputDirectoryText.Text = _settings.DefaultOutputDirectory;
        }
    }

    private void AiChanged(object sender, RoutedEventArgs e)
    {
        if (_initializing) return;
        _settings.AiEnabled = AiEnabledBox.IsChecked == true;
        AiDetails.IsEnabled = _settings.AiEnabled;
        SaveAiFields();
    }

    private void AiField_LostFocus(object sender, RoutedEventArgs e)
    {
        if (!_initializing) SaveAiFields();
    }

    private void SaveAiFields()
    {
        _settings.AiEndpoint = AiEndpointBox.Text.Trim();
        _settings.AiModel = AiModelBox.Text.Trim();
        _settings.AiKeyEnv = AiKeyEnvBox.Text.Trim();
        _settings.Save();
    }

    private static void SelectTag(ComboBox box, string? value)
    {
        foreach (ComboBoxItem item in box.Items)
        {
            if (string.Equals(item.Tag?.ToString(), value, StringComparison.OrdinalIgnoreCase))
            {
                box.SelectedItem = item;
                return;
            }
        }
        box.SelectedIndex = box.SelectedIndex < 0 ? 0 : box.SelectedIndex;
    }

    private static string TagOf(ComboBox box, string fallback)
        => (box.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? fallback;
}

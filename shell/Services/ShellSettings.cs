using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Wpf.Ui.Appearance;
using Wpf.Ui.Controls;

namespace ProjectFactory.Workbench.Services;

public sealed class ShellSettings
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
    };

    private readonly string _path;

    public string Theme { get; set; } = "System";
    public string Accent { get; set; } = "Default";
    public string Backdrop { get; set; } = "Mica";
    public string CornerStyle { get; set; } = "Round";
    public string FontFamilyName { get; set; } = "Microsoft YaHei UI";
    public string FontSizeKey { get; set; } = "Default";
    public string ScaleMode { get; set; } = "Uniform";
    public string UiZoomKey { get; set; } = "100";
    public string BackgroundImage { get; set; } = "";
    public string BackgroundOpacityKey { get; set; } = "Medium";
    public string DefaultOutputDirectory { get; set; } = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "ProjectFactory", "Projects");
    public bool AiEnabled { get; set; }
    public string AiEndpoint { get; set; } = "";
    public string AiModel { get; set; } = "";
    public string AiKeyEnv { get; set; } = "OPENAI_API_KEY";

    public ShellSettings()
    {
        var root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ProjectFactory");
        Directory.CreateDirectory(root);
        _path = Path.Combine(root, "shell_settings.json");
        Load();
    }

    public double FontSizeScale => FontSizeKey switch
    {
        "Small" => 0.9,
        "Large" => 1.15,
        "XLarge" => 1.3,
        _ => 1.0,
    };

    public double UiZoom => UiZoomKey switch
    {
        "80" => 0.8,
        "90" => 0.9,
        "110" => 1.1,
        "125" => 1.25,
        "150" => 1.5,
        _ => 1.0,
    };

    public void Load()
    {
        if (!File.Exists(_path)) return;
        try
        {
            var saved = JsonSerializer.Deserialize<ShellSettingsDto>(File.ReadAllText(_path), JsonOptions);
            if (saved is null) return;
            Theme = saved.Theme ?? Theme;
            Accent = saved.Accent ?? Accent;
            Backdrop = saved.Backdrop ?? Backdrop;
            CornerStyle = saved.CornerStyle ?? CornerStyle;
            FontFamilyName = string.IsNullOrWhiteSpace(saved.FontFamilyName) ? FontFamilyName : saved.FontFamilyName;
            FontSizeKey = saved.FontSizeKey ?? FontSizeKey;
            ScaleMode = saved.ScaleMode ?? ScaleMode;
            UiZoomKey = saved.UiZoomKey ?? UiZoomKey;
            BackgroundImage = saved.BackgroundImage ?? "";
            BackgroundOpacityKey = saved.BackgroundOpacityKey ?? BackgroundOpacityKey;
            DefaultOutputDirectory = string.IsNullOrWhiteSpace(saved.DefaultOutputDirectory) ? DefaultOutputDirectory : saved.DefaultOutputDirectory;
            AiEnabled = saved.AiEnabled;
            AiEndpoint = saved.AiEndpoint ?? "";
            AiModel = saved.AiModel ?? "";
            // Distinguish "field absent" (fall back to default) from "user cleared it on
            // purpose" (respect the empty string).  Re-filling the default here silently
            // re-armed the API key requirement even for keyless local endpoints.
            AiKeyEnv = saved.AiKeyEnv is null ? AiKeyEnv : saved.AiKeyEnv.Trim();
        }
        catch
        {
            // Settings corruption is non-fatal; defaults are safe and recoverable.
        }
    }

    public void Save()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        var dto = new ShellSettingsDto
        {
            Theme = Theme,
            Accent = Accent,
            Backdrop = Backdrop,
            CornerStyle = CornerStyle,
            FontFamilyName = FontFamilyName,
            FontSizeKey = FontSizeKey,
            ScaleMode = ScaleMode,
            UiZoomKey = UiZoomKey,
            BackgroundImage = BackgroundImage,
            BackgroundOpacityKey = BackgroundOpacityKey,
            DefaultOutputDirectory = DefaultOutputDirectory,
            AiEnabled = AiEnabled,
            AiEndpoint = AiEndpoint,
            AiModel = AiModel,
            AiKeyEnv = AiKeyEnv,
        };
        var temp = _path + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(dto, JsonOptions));
        File.Move(temp, _path, true);
    }

    public Dictionary<string, object?> AiPayload() => new()
    {
        ["enabled"] = AiEnabled,
        ["endpoint"] = AiEndpoint,
        ["model"] = AiModel,
        ["key_env"] = AiKeyEnv,
    };

    public void Apply(Window? owner = null)
    {
        ApplyTheme(owner);
        ApplyType();
        if (owner is MainWindow window)
        {
            window.WindowBackdropType = ParseBackdrop();
            window.WindowCornerPreference = ParseCorner();
            window.FontFamily = (FontFamily)Application.Current.Resources["AppFont"];
            window.FontStretch = FontStretches.Normal;
            ApplyBackground(window);
            ApplyScale(window);
        }
    }

    public void ApplyTheme(Window? owner = null)
    {
        var backdrop = ParseBackdrop();
        var (theme, followSystem) = ResolveTheme();
        var fluent = owner as FluentWindow;

        if (followSystem)
        {
            ApplicationThemeManager.ApplySystemTheme();
            if (fluent is not null)
            {
                try { SystemThemeWatcher.UnWatch(fluent); } catch { }
                SystemThemeWatcher.Watch(fluent, backdrop, Accent == "Default");
            }
        }
        else
        {
            if (fluent is not null)
            {
                try { SystemThemeWatcher.UnWatch(fluent); } catch { }
            }
            ApplicationThemeManager.Apply(theme, backdrop, Accent == "Default" && Theme is not "Midnight" and not "Warm" and not "Contrast");
        }

        var accent = ResolveAccentColor();
        if (accent is null)
            ApplicationAccentColorManager.ApplySystemAccent();
        else
            ApplicationAccentColorManager.Apply(accent.Value, followSystem ? ApplicationThemeManager.GetAppTheme() : theme, false, false);
    }

    public void ApplyScale(MainWindow? window)
    {
        if (window?.ShellRoot is null || window.OuterRoot is null) return;

        // A组(R1): Viewbox 整体缩放已移除。ShellRoot 直接填满窗口，响应式布局由各页面
        // 自身（NavigationView 内容区 + 原生 ScrollViewer）完成，不再靠 RenderTransform 拉伸缩放
        // （非整数倍缩放会让中文发虚、窗口越大字越大）。字号档（FontSizeKey）由 ApplyType() 通过
        // AppFontSize* 资源键生效，不再走 UiZoom 的 RenderTransform。
        window.ShellRoot.Width = double.NaN;
        window.ShellRoot.Height = double.NaN;
        window.ShellRoot.HorizontalAlignment = HorizontalAlignment.Stretch;
        window.ShellRoot.VerticalAlignment = VerticalAlignment.Stretch;
        window.ShellRoot.LayoutTransform = Transform.Identity;
    }

    private void ApplyType()
    {
        var family = string.IsNullOrWhiteSpace(FontFamilyName) ? "Microsoft YaHei UI" : FontFamilyName.Trim();
        var stack = $"{family}, Microsoft YaHei UI, Segoe UI Variable Text, Segoe UI, Microsoft YaHei";
        var font = new FontFamily(stack);
        Application.Current.Resources["AppFont"] = font;
        Application.Current.Resources["AppDisplayFont"] = font;

        var z = FontSizeScale;
        Application.Current.Resources["AppFontSizeEyebrow"] = 12.0 * z;
        Application.Current.Resources["AppFontSizeBody"] = 14.0 * z;
        Application.Current.Resources["AppFontSizeLead"] = 15.0 * z;
        Application.Current.Resources["AppFontSizeSection"] = 19.0 * z;
        Application.Current.Resources["AppFontSizeTitle"] = 34.0 * z;
    }

    private void ApplyBackground(MainWindow window)
    {
        if (window.BackgroundImageLayer is null) return;
        if (string.IsNullOrWhiteSpace(BackgroundImage) || !File.Exists(BackgroundImage))
        {
            window.BackgroundImageLayer.Source = null;
            window.BackgroundImageLayer.Visibility = Visibility.Collapsed;
            return;
        }

        try
        {
            var image = new BitmapImage();
            image.BeginInit();
            image.CacheOption = BitmapCacheOption.OnLoad;
            image.UriSource = new Uri(BackgroundImage);
            image.EndInit();
            image.Freeze();
            window.BackgroundImageLayer.Source = image;
            window.BackgroundImageLayer.Opacity = BackgroundOpacityKey switch
            {
                "Low" => 0.14,
                "High" => 0.45,
                _ => 0.28,
            };
            window.BackgroundImageLayer.Visibility = Visibility.Visible;
        }
        catch
        {
            window.BackgroundImageLayer.Source = null;
            window.BackgroundImageLayer.Visibility = Visibility.Collapsed;
        }
    }

    private (ApplicationTheme theme, bool followSystem) ResolveTheme() => Theme switch
    {
        "Light" or "Warm" => (ApplicationTheme.Light, false),
        "Dark" or "Midnight" or "Contrast" => (ApplicationTheme.Dark, false),
        _ => (ApplicationTheme.Unknown, true),
    };

    private Color? ResolveAccentColor()
    {
        if (Accent is "Blue") return Color.FromRgb(0x00, 0x78, 0xD4);
        if (Accent is "Teal") return Color.FromRgb(0x0D, 0x94, 0x88);
        if (Accent is "Green") return Color.FromRgb(0x16, 0xA3, 0x4A);
        if (Accent is "Purple") return Color.FromRgb(0x7C, 0x3A, 0xED);
        if (Accent is "Orange") return Color.FromRgb(0xEA, 0x58, 0x0C);
        if (Accent is "Red") return Color.FromRgb(0xDC, 0x26, 0x26);
        return Theme switch
        {
            "Midnight" => Color.FromRgb(0x63, 0x66, 0xF1),
            "Warm" => Color.FromRgb(0xD9, 0x77, 0x06),
            "Contrast" => Color.FromRgb(0xF8, 0xFA, 0xFC),
            _ => null,
        };
    }

    private WindowBackdropType ParseBackdrop() => Backdrop switch
    {
        "Acrylic" => WindowBackdropType.Acrylic,
        "Tabbed" => WindowBackdropType.Tabbed,
        "None" => WindowBackdropType.None,
        _ => WindowBackdropType.Mica,
    };

    private WindowCornerPreference ParseCorner() => CornerStyle switch
    {
        "Square" => WindowCornerPreference.DoNotRound,
        "Small" => WindowCornerPreference.RoundSmall,
        _ => WindowCornerPreference.Round,
    };

    private sealed class ShellSettingsDto
    {
        public string? Theme { get; set; }
        public string? Accent { get; set; }
        public string? Backdrop { get; set; }
        public string? CornerStyle { get; set; }
        public string? FontFamilyName { get; set; }
        public string? FontSizeKey { get; set; }
        public string? ScaleMode { get; set; }
        public string? UiZoomKey { get; set; }
        public string? BackgroundImage { get; set; }
        public string? BackgroundOpacityKey { get; set; }
        public string? DefaultOutputDirectory { get; set; }
        public bool AiEnabled { get; set; }
        public string? AiEndpoint { get; set; }
        public string? AiModel { get; set; }
        public string? AiKeyEnv { get; set; }
    }
}

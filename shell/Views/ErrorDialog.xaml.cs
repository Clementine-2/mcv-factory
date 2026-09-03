using System.Windows;
using ProjectFactory.Workbench.Services;

namespace ProjectFactory.Workbench.Views;

/// <summary>
/// 结构化错误弹窗：展示「原因 / 影响 / 怎么办」三段人话，并提供「复制详情」按钮
/// （复制整段含原始信息），把 T07 / R2 深化的可读性要求落到 GUI。
/// 只接收已分类的 ErrorInfo，不改动任何内核语义。
/// </summary>
public partial class ErrorDialog : Window
{
    public ErrorDialog(ErrorInfo info)
    {
        InitializeComponent();
        TitleText.Text = info.Title;
        CategoryText.Text = "分类：" + info.Category;
        DetailBox.Text = info.DetailText();
    }

    private void CopyButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            Clipboard.SetText(DetailBox.Text);
            CopyButton.Content = "已复制";
        }
        catch
        {
            CopyButton.Content = "复制失败";
        }
    }

    private void CloseButton_Click(object sender, RoutedEventArgs e) => Close();

    /// <summary>
    /// 便捷入口：直接拿桥的 message 文本弹窗（自动分类）。
    /// </summary>
    public static void ShowError(string rawMessage, Window? owner = null)
    {
        var dlg = new ErrorDialog(ErrorInfo.Classify(rawMessage));
        if (owner is not null)
        {
            dlg.Owner = owner;
        }

        dlg.ShowDialog();
    }
}

namespace ProjectFactory.Workbench.Models;

public sealed class CatalogOption
{
    public string Id { get; init; } = "";
    public string Title { get; init; } = "";
    public string Blurb { get; init; } = "";

    /// <summary>
    /// T06：该选项是否有真实产线可服务。false 时 GUI 禁用并展示 Reason。
    /// 默认 true，保证兼容性（旧 catalog 不携带此字段时一切照旧）。
    /// </summary>
    public bool Available { get; init; } = true;

    /// <summary>
    /// T06：不可用时的人话原因（直接拼进 Blurb，保证禁用项仍可读）。
    /// </summary>
    public string Reason { get; init; } = "";

    public override string ToString() => string.IsNullOrWhiteSpace(Title) ? Id : Title;
}

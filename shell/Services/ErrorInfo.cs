using System;

namespace ProjectFactory.Workbench.Services;

/// <summary>
/// 把 backend bridge 抛回的原始错误信息（目前前端只拿到 message 文本）结构化成人话的
/// 「原因 / 影响 / 怎么办」三段，供错误弹窗展示与一键复制。
/// 分类只对 message 文本做子串匹配，绝不改动内核异常语义（T07 / R2 深化，boundary: 只改展示层与文案）。
/// 与 night_run/ERROR_CODES.md 一一对应。
/// </summary>
public sealed class ErrorInfo
{
    public string Category { get; set; } = "其他错误";
    public string Title { get; set; } = "操作未完成";
    public string Reason { get; set; } = "";
    public string Impact { get; set; } = "";
    public string WhatToDo { get; set; } = "";
    public string RawMessage { get; set; } = "";

    /// <summary>
    /// 把桥返回的原始 message 分成三类已知错误 + 兜底。
    /// 分类关键词与内核真实文案对齐（见 night_run/ERROR_CODES.md）。
    /// </summary>
    public static ErrorInfo Classify(string rawMessage)
    {
        var msg = (rawMessage ?? "").Trim();
        var info = new ErrorInfo { RawMessage = msg };

        // E01 机床版本门禁：registry.inspect_provider 拒绝未钉死版本
        if (msg.Contains("is not tested by this registry", StringComparison.OrdinalIgnoreCase)
            || msg.Contains("is tested but not supported", StringComparison.OrdinalIgnoreCase))
        {
            info.Category = "机床版本门禁";
            info.Title = "工具版本不在受测清单内";
            info.Reason = "工厂只接受钉死的 npm 10.9.2 / uv 0.10.0 等版本。当前解析到的工具版本未被内核兼容性测试过，门禁直接拒绝，避免用未验证版本产出不可信工程。";
            info.Impact = "本次生成被中止，不会产出半成品。Node / Web 类产线依赖这门禁；Python 类产线不受影响。";
            info.WhatToDo = "确认安装目录 tools/npm1092、tools/uv010 已随内核一起部署（资源页可看机床版本）。若缺失，运行安装器 Repair 或重新安装发布版 Setup。不要手动改造成允许其他版本——那是门禁常量，受 R3 保护。";
            return info;
        }

        // E02 无匹配产线：registry.select_profile 抛 No registered profile
        if (msg.Contains("No registered profile", StringComparison.OrdinalIgnoreCase))
        {
            info.Category = "组合不支持";
            info.Title = "当前「工作产品 / 语言 / 车身」没有对应产线";
            info.Reason = "你选的工作产品 + 技术 + 车身组合，在内核 registry 里匹配不到任何已注册的产线配置（例如 web-ssr 配了 astro 这种静态站车身，或 notebook 没选 jupyter 车身）。";
            info.Impact = "本次生成被中止。这是数据 / 选项层面的不匹配，不是内核故障。";
            info.WhatToDo = "只保留互相匹配的一组：React 网页 = web-spa + react；Python 命令行 = cli + python；WPF = desktop-app + csharp。Create 页已对无产线项做灰化并附原因，照着灰化提示选即可。";
            return info;
        }

        // E03 AI 凭据缺失：bridge._ai_assist / _semantic_adapter 抛的中文 ValueError
        var aiCredential =
            (msg.Contains("环境变量", StringComparison.OrdinalIgnoreCase) && msg.Contains("没有值", StringComparison.OrdinalIgnoreCase))
            || msg.Contains("AI endpoint 不完整", StringComparison.OrdinalIgnoreCase)
            || (msg.Contains("先展开", StringComparison.OrdinalIgnoreCase) && msg.Contains("AI", StringComparison.OrdinalIgnoreCase))
            || msg.Contains("AI model 不完整", StringComparison.OrdinalIgnoreCase)
            || msg.Contains("还没有选定 Ollama", StringComparison.OrdinalIgnoreCase);
        if (aiCredential)
        {
            info.Category = "AI 凭据缺失";
            info.Title = "AI 辅助未配置完整";
            info.Reason = "你启用了 AI 辅助，但凭据没给全：要么 key_env 指向的环境变量是空的，要么 endpoint / model 没填，要么 Ollama 还没选本机模型。";
            info.Impact = "AI 辅助这一步失败。注意：AI 只是辅助填模板，不是生成必需项——关掉「启用 AI 辅助」也能照常生成。";
            info.WhatToDo = "设置页里填好 endpoint + model，并把 API Key 放进 key_env 指向的那个环境变量后重试；或取消「启用 AI 辅助」直接生成。Ollama 用户先点「读取本机模型」选一个已 pull 的模型。";
            return info;
        }

        // E09 兜底：unknown action / 缺字段 / 进程层 / 网络等
        info.Category = "其他错误";
        info.Title = "操作未完成";
        info.Reason = "内核或桥返回了上方三类之外的错误。原始信息已保留在「原始信息」里，便于复制给维护者定位。";
        info.Impact = "本次操作被中止。";
        info.WhatToDo = "复制下方「原始信息」整段到 issue / 交给维护者；若涉及网络产线，网络失败不算内核失败，可重试。";
        return info;
    }

    /// <summary>
    /// 供「复制详情」按钮与弹窗展示的完整文本。
    /// </summary>
    public string DetailText() =>
        $"【{Title}】\n" +
        $"分类：{Category}\n\n" +
        $"原因\n{Reason}\n\n" +
        $"影响\n{Impact}\n\n" +
        $"怎么办\n{WhatToDo}\n\n" +
        $"原始信息\n{RawMessage}";
}

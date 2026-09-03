using System.Text.Json;

namespace ProjectFactory.Workbench.Services;

public static class JsonView
{
    public static string String(JsonElement element, string property, string fallback = "")
        => element.TryGetProperty(property, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? fallback
            : fallback;

    public static string Csv(JsonElement element)
    {
        if (element.ValueKind != JsonValueKind.Array) return "";
        return string.Join(", ", element.EnumerateArray()
            .Select(x => x.ValueKind == JsonValueKind.String ? x.GetString() : x.ToString())
            .Where(x => !string.IsNullOrWhiteSpace(x)));
    }

    public static JsonElement? FindRow(JsonElement matrix, string rowId)
    {
        if (!matrix.TryGetProperty("rows", out var rows) || rows.ValueKind != JsonValueKind.Array) return null;
        foreach (var row in rows.EnumerateArray())
            if (String(row, "id") == rowId) return row.Clone();
        return null;
    }

    public static JsonElement? RowValue(JsonElement matrix, string rowId)
    {
        var row = FindRow(matrix, rowId);
        return row is not null && row.Value.TryGetProperty("value", out var value) ? value.Clone() : null;
    }

    public static string RowText(JsonElement matrix, string rowId)
    {
        var value = RowValue(matrix, rowId);
        if (value is null) return "";
        return value.Value.ValueKind switch
        {
            JsonValueKind.Array => Csv(value.Value),
            JsonValueKind.String => value.Value.GetString() ?? "",
            _ => value.Value.ToString(),
        };
    }

    public static string RowObjectFieldCsv(JsonElement matrix, string rowId, string field)
    {
        var value = RowValue(matrix, rowId);
        if (value is null || value.Value.ValueKind != JsonValueKind.Array) return "";
        var items = new List<string>();
        foreach (var item in value.Value.EnumerateArray())
        {
            if (item.ValueKind == JsonValueKind.Object && item.TryGetProperty(field, out var v) && v.ValueKind == JsonValueKind.String)
            {
                var text = v.GetString();
                if (!string.IsNullOrWhiteSpace(text)) items.Add(text);
            }
        }
        return string.Join(", ", items);
    }

    public static string Questions(JsonElement matrix)
    {
        if (!matrix.TryGetProperty("questions", out var value) || value.ValueKind != JsonValueKind.Array) return "";
        return string.Join("\n", value.EnumerateArray().Select(x => "• " + (x.GetString() ?? x.ToString())));
    }
}

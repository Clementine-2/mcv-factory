namespace ProjectFactory.Workbench.Models;

public sealed record ProjectHistoryItem(
    string Name,
    string Profile,
    string Status,
    string Timestamp,
    string ProjectRoot,
    string ProjectZip
);

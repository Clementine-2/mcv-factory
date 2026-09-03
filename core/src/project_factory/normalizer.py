from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from .validator import ValidationResult, validate_blueprint


SOURCE_EXPLICIT = "EXPLICIT"
SOURCE_INFERRED = "INFERRED"
MAX_REQUIREMENT_CHARS = 100_000


_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "[REDACTED_SECRET]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", flags=re.IGNORECASE), "[REDACTED_SECRET]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_SECRET]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{8,}"), "Bearer [REDACTED_SECRET]"),
    (
        re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*[\"']?([A-Za-z0-9_.+/=-]{6,})[\"']?"),
        r"\1=[REDACTED_SECRET]",
    ),
)


def _redact_secrets(text: str) -> tuple[str, bool]:
    redacted = text
    changed = False
    for pattern, replacement in _SECRET_PATTERNS:
        updated, count = pattern.subn(replacement, redacted)
        if count:
            changed = True
            redacted = updated
    return redacted, changed


def redact_secrets(text: str) -> tuple[str, bool]:
    """Public defense-in-depth redaction helper for semantic adapter boundaries."""
    return _redact_secrets(text)


@dataclass(frozen=True)
class NormalizationResult:
    blueprint: dict[str, Any]
    metadata: dict[str, Any]
    validation: ValidationResult
    questions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint": self.blueprint,
            "metadata": self.metadata,
            "validation": self.validation.to_dict(),
            "questions": list(self.questions),
        }


@dataclass(frozen=True)
class _PatternRule:
    value: str
    patterns: tuple[str, ...]


def _contains(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _first_match(text: str, patterns: Iterable[str]) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match
    return None


def _append_provenance(meta: dict[str, Any], path: str, source: str, note: str | None = None) -> None:
    record: dict[str, Any] = {"source": source}
    if note:
        record["note"] = note
    meta.setdefault("provenance", {})[path] = record


def _append_assumption(meta: dict[str, Any], path: str, value: Any, reason: str) -> None:
    assumptions = meta.setdefault("assumptions", [])
    assumptions.append(
        {
            "id": f"A{len(assumptions) + 1:03d}",
            "path": path,
            "value": value,
            "reason": reason,
        }
    )


def _append_unresolved(
    meta: dict[str, Any],
    path: str,
    reason: str,
    *,
    blocking: bool = False,
    resolution_required: bool = False,
) -> None:
    meta.setdefault("unresolved", []).append(
        {
            "path": path,
            "reason": reason,
            "blocking": blocking,
            "resolution_required": resolution_required,
        }
    )


def _unique_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


_WORK_PRODUCT_RULES: tuple[_PatternRule, ...] = (
    _PatternRule("mcp-server", (r"\bmcp\b", r"MCP", r"模型上下文协议")),
    _PatternRule("vscode-extension", (r"vs\s*code\s*(?:插件|扩展)", r"\bvscode\s+extension\b")),
    _PatternRule("ci-action", (r"github\s+action", r"GitHub\s+Action", r"CI\s*Action")),
    _PatternRule("docs-site", (r"文档站", r"\bdocs\s+site\b", r"\bmkdocs\b")),
    _PatternRule("static-site", (r"静态(?:营销)?站", r"\bstatic\s+site\b", r"\bastro\b")),
    _PatternRule("tui", (r"\btui\b", r"终端界面", r"文本界面")),
    _PatternRule("serverless-function", (r"\blambda\b", r"cloudflare\s+worker", r"\bserverless\b")),
    _PatternRule("test-suite", (r"独立\s*playwright", r"playwright\s*仓库", r"e2e\s*测试仓")),
    _PatternRule("data-pipeline", (r"\betl\b", r"定时\s*ETL", r"数据管道", r"\bdata\s+pipeline\b")),
    _PatternRule("schema-migration-repo", (r"migration\s*仓库", r"schema\s+migration", r"\balembic\b", r"数据库\s*migration")),
    _PatternRule("generated-sdk", (r"生成\s*(?:TypeScript\s*)?客户端", r"generated\s+sdk", r"openapi\s*(?:client|sdk)")),
    _PatternRule("eval-harness", (r"评测仓", r"\beval(?:uation)?\s+harness\b", r"\beval\s+仓")),
    _PatternRule("bot", (r"Discord\s*机器人", r"\bdiscord\s+bot\b", r"聊天机器人")),
    _PatternRule("scraper", (r"爬虫", r"\bscraper\b", r"\bcrawler\b")),
    _PatternRule("graphql-api", (r"\bgraphql\b", r"GraphQL\s*API")),
    _PatternRule("realtime-service", (r"\bwebsocket\b", r"实时服务", r"WebSocket")),
    _PatternRule("schema-contract", (r"OpenAPI\s*合同", r"合同仓", r"schema\s+contract")),
    _PatternRule("agent-workflow", (r"agent\s*工作流", r"\bagent\s+workflow\b", r"\bpydantic-ai\b")),
    _PatternRule("design-system", (r"设计系统", r"组件库", r"\bdesign\s+system\b")),
    _PatternRule("rag-application", (r"\brag\b", r"RAG\s*service", r"检索增强")),
    _PatternRule("model-serving", (r"模型推理", r"\bmodel[- ]serving\b", r"推理服务")),
    _PatternRule("analytics-transform", (r"\bdbt\b", r"analytics\s+transform")),
    _PatternRule("container-stack", (r"docker\s+compose", r"compose\s*栈", r"容器栈")),
    _PatternRule("grpc-service", (r"gRPC\s*服务", r"\bgrpc\s+service\b", r"\bgrpc\s+server\b")),
    _PatternRule("event-driven-app", (r"kafka\s+consumer", r"纯消费者", r"事件消费者", r"event[- ]driven")),
    _PatternRule("observability-agent", (r"opentelemetry\s+collector", r"otel\s+collector", r"探针项目", r"observability[- ]agent")),
    _PatternRule("browser-extension", (r"浏览器(?:扩展|插件)", r"\bbrowser\s+extension\b", r"\bwebextension\b")),
    _PatternRule("mobile-app", (r"手机(?:应用|app)", r"移动(?:应用|app)", r"\bmobile\s+app(?:lication)?\b", r"\bandroid\s+app\b", r"\bios\s+app\b")),
    _PatternRule("desktop-app", (r"桌面(?:应用|app)", r"\bdesktop\s+app(?:lication)?\b")),
    _PatternRule("web-ssr", (r"\bnext\.js\b", r"\bnextjs\b")),
    _PatternRule("web-ui", (r"\bweb\s*(?:app|application|ui)\b", r"web应用", r"网页应用", r"网站", r"前端(?:界面|应用)?", r"单页应用", r"\bspa\b")),
    _PatternRule("native-extension", (r"Rust\s*扩展", r"\bnative extension\b", r"\bpyo3\b", r"\bmaturin\b")),
    _PatternRule("iac", (r"\biac\b", r"基础设施", r"\bopentofu\b", r"\bterraform\b", r"\bpulumi\b")),
    _PatternRule("service", (r"\bhttp\s+api\b", r"\bweb\s+api\b", r"\brest(?:ful)?\s+api\b", r"api服务", r"HTTP\s*服务", r"后端(?:服务|应用)?", r"\bbackend\b", r"\bservice\b", r"\bhono\b", r"边缘\s*API", r"\bnestjs\b", r"NestJS", r"微服务", r"\bfastapi\b")),
    _PatternRule("cli", (r"命令行", r"终端工具", r"\bcli\b", r"\bcommand[- ]line\b")),
    _PatternRule("library", (r"核心库", r"程序库", r"软件库", r"代码库", r"\blibrary\b", r"\bsdk\b", r"\bcrate\b", r"Rust\s*库", r"TypeScript\s*库", r"C#\s*库")),
    _PatternRule("notebook", (r"\bnotebook\b", r"\bjupyter\b", r"笔记本实验", r"研究笔记本", r"实验笔记本")),
    _PatternRule("experiment", (r"机器学习实验", r"实验项目", r"实验仓", r"可复现实验", r"\bexperiment(?:al)?\b")),
    _PatternRule("dataset", (r"数据集", r"\bdataset\b")),
    _PatternRule("model", (r"训练模型", r"模型文件", r"\btrained\s+model\b", r"\bmachine[- ]learning\s+model\b", r"\bml\s+model\b")),
    _PatternRule("research-result", (r"研究结果", r"实验结果", r"\bresearch\s+result\b")),
    _PatternRule("documentation", (r"文档项目", r"\bdocumentation\s+project\b")),
    _PatternRule("automation", (r"自动化脚本", r"自动化工具", r"\bautomation\s+(?:script|tool)\b")),
)

_TECH_RULES: tuple[_PatternRule, ...] = (
    _PatternRule("typescript", (r"\btypescript\b",)),
    _PatternRule("javascript", (r"\bjavascript\b",)),
    _PatternRule("python", (r"\bpython\b", r"\bjupyter\b")),
    _PatternRule("rust", (r"\brust\b", r"\bpyo3\b", r"\baxum\b", r"\bclap\b")),
    _PatternRule("golang", (r"\bgolang\b", r"\bgo语言\b")),
    _PatternRule("java", (r"\bjava\b",)),
    _PatternRule("kotlin", (r"\bkotlin\b",)),
    _PatternRule("swift", (r"\bswift\b",)),
    _PatternRule("csharp", (r"c#", r"\bcsharp\b", r"\bwpf\b", r"asp\.net")),
    _PatternRule("avalonia", (r"\bavalonia\b", r"跨平台桌面", r"cross-?platform desktop")),
    _PatternRule("cpp", (r"\bc\+\+\b", r"\bcpp\b")),
    _PatternRule("typer", (r"\btyper\b",)),
    _PatternRule("nextjs", (r"\bnext\.js\b", r"\bnextjs\b")),
    _PatternRule("react", (r"\breact\b",)),
    _PatternRule("fastapi", (r"\bfastapi\b",)),
    _PatternRule("vue", (r"\bvue(?:\.js)?\b",)),
    _PatternRule("svelte", (r"\bsvelte\b",)),
    _PatternRule("astro", (r"\bastro\b",)),
    _PatternRule("axum", (r"\baxum\b",)),
    _PatternRule("clap", (r"\bclap\b",)),
    _PatternRule("cloudflare", (r"\bcloudflare\b", r"\bwrangler\b")),
    _PatternRule("playwright", (r"\bplaywright\b",)),
    _PatternRule("textual", (r"\btextual\b",)),
    _PatternRule("lambda", (r"\blambda\b", r"\baws lambda\b")),
    _PatternRule("commander", (r"\bcommander\b",)),
    _PatternRule("alembic", (r"\balembic\b",)),
    _PatternRule("openapi", (r"\bopenapi\b",)),
    _PatternRule("hono", (r"\bhono\b",)),
    _PatternRule("graphql", (r"\bgraphql\b",)),
    _PatternRule("discord", (r"\bdiscord\b",)),
    _PatternRule("websocket", (r"\bwebsocket\b",)),
    _PatternRule("pydantic-ai", (r"\bpydantic-ai\b",)),
    _PatternRule("nestjs", (r"\bnestjs\b", r"NestJS")),
    _PatternRule("dbt", (r"\bdbt\b",)),
    _PatternRule("opentofu", (r"\bopentofu\b", r"\bterraform\b")),
    _PatternRule("tauri", (r"\btauri\b",)),
    _PatternRule("electron", (r"\belectron\b",)),
)

_TARGET_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("browser", "chrome", (r"\bchrome\b",)),
    ("browser", "firefox", (r"\bfirefox\b",)),
    ("os", "windows", (r"\bwindows\b",)),
    ("os", "linux", (r"\blinux\b",)),
    ("os", "macos", (r"\bmacos\b", r"\bmac\s*os\b")),
    ("platform", "ios", (r"\bios\b",)),
    ("platform", "android", (r"\bandroid\b",)),
    ("hardware", "cuda-gpu", (r"\bcuda\b",)),
    ("hardware", "gpu", (r"\bgpu\b",)),
    ("environment", "server", (r"服务器", r"\bserver\b")),
    ("runtime", "local", (r"本地运行", r"本地工具", r"\blocal(?:ly)?\b")),
)

_QUALITY_RULES: tuple[_PatternRule, ...] = (
    _PatternRule("security", (r"安全", r"\bsecurity\b")),
    _PatternRule("reliability", (r"可靠性", r"稳定性", r"稳定可靠", r"稳定", r"\breliability\b")),
    _PatternRule("privacy", (r"隐私", r"\bprivacy\b")),
    _PatternRule("performance", (r"性能", r"\bperformance\b")),
    _PatternRule("portability", (r"跨平台", r"可移植", r"\bportability\b", r"\bcross[- ]platform\b")),
    _PatternRule("reproducibility", (r"可复现", r"复现性", r"\breproducib(?:le|ility)\b")),
    _PatternRule("maintainability", (r"可维护", r"维护性", r"\bmaintainability\b")),
    _PatternRule("backward-compatibility", (r"向后兼容", r"兼容旧版本", r"\bbackward[- ]compatibility\b")),
    _PatternRule("accessibility", (r"无障碍", r"\baccessibility\b")),
    _PatternRule("testability", (r"可测试", r"易测试", r"测试友好", r"\btestability\b", r"\btestable\b")),
)

_HARD_MARKERS = (
    r"必须",
    r"不得",
    r"不能",
    r"不允许",
    r"禁止",
    r"\bmust\b",
    r"\bmust\s+not\b",
    r"\bcannot\b",
    r"\bcan't\b",
)


def _extract_sentences(text: str) -> list[str]:
    return [part.strip(" ,，.;；") for part in re.split(r"[。！？!?;；\n]+", text) if part.strip()]


def _classify_technology_context(text: str, match: re.Match[str]) -> str:
    left = text[max(0, match.start() - 18) : match.start()].casefold()
    if re.search(r"不要|不得|不能|禁止|避免|\bavoid\b|\bwithout\b|\bno\s+$", left, flags=re.IGNORECASE):
        return "prohibited"
    if re.search(r"最好|优先|偏好|倾向|\bprefer\b|\bpreferred\b", left, flags=re.IGNORECASE):
        return "preferred"
    return "required"


def _quality_level(text: str, match: re.Match[str]) -> str:
    window = text[max(0, match.start() - 16) : min(len(text), match.end() + 16)]
    if _contains(window, (r"最重要", r"最高", r"极高", r"关键", r"\bcritical\b")):
        return "critical"
    if _contains(window, (r"高", r"严格", r"很强", r"\bhigh\b", r"\bstrict\b")):
        return "high"
    return "normal"


def _extract_work_products(text: str, meta: dict[str, Any]) -> list[dict[str, str]]:
    products: list[dict[str, str]] = []
    for rule in _WORK_PRODUCT_RULES:
        if _contains(text, rule.patterns):
            products.append({"kind": rule.value})

    # Generic "tool" is a useful work product only when no more specific surface was stated.
    if not products and _contains(text, (r"小工具", r"\butility\b", r"(?:^|[，。 ,])工具(?:$|[，。 ,])", r"做个工具", r"做一个工具")):
        products.append({"kind": "utility"})

    # Generic "app/application" is intentionally unresolved rather than guessed as web/mobile/desktop.
    if not products and _contains(text, (r"\bapp\b", r"\bapplication\b", r"应用")):
        products.append({"kind": "application"})
        _append_unresolved(
            meta,
            "/work_products/0/kind",
            "The request says application/app but does not identify the application surface (for example web, mobile, or desktop).",
            resolution_required=True,
        )

    if not products:
        products.append({"kind": "unspecified"})
        _append_unresolved(
            meta,
            "/work_products/0/kind",
            "No concrete work product could be extracted without guessing.",
            resolution_required=True,
        )

    for index, product in enumerate(products):
        _append_provenance(meta, f"/work_products/{index}/kind", SOURCE_EXPLICIT if product["kind"] not in {"application", "unspecified"} else SOURCE_INFERRED)
    return products


def _extract_technology(text: str, meta: dict[str, Any]) -> dict[str, list[str]] | None:
    # Preserve the user's textual order instead of the registry/rule-table order.
    matches: list[tuple[int, str, str]] = []
    for rule in _TECH_RULES:
        match = _first_match(text, rule.patterns)
        if not match:
            continue
        bucket = _classify_technology_context(text, match)
        matches.append((match.start(), bucket, rule.value))

    matches.sort(key=lambda item: item[0])
    buckets: dict[str, list[str]] = {"required": [], "preferred": [], "prohibited": []}
    for _, bucket, value in matches:
        buckets[bucket].append(value)

    result: dict[str, list[str]] = {}
    for bucket in ("required", "preferred", "prohibited"):
        values = _unique_preserve(buckets[bucket])
        if not values:
            continue
        result[bucket] = values
        for index, _ in enumerate(values):
            _append_provenance(meta, f"/technology/{bucket}/{index}", SOURCE_EXPLICIT)
    return result or None


def _extract_targets(text: str, meta: dict[str, Any]) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for kind, value, patterns in _TARGET_RULES:
        if not _contains(text, patterns):
            continue
        item = (kind, value)
        if item in seen:
            continue
        seen.add(item)
        targets.append({"kind": kind, "value": value})

    # "GPU" plus "CUDA" should not duplicate a generic GPU target.
    if ("hardware", "cuda-gpu") in seen and ("hardware", "gpu") in seen:
        targets = [item for item in targets if not (item["kind"] == "hardware" and item["value"] == "gpu")]

    for index, _ in enumerate(targets):
        _append_provenance(meta, f"/targets/{index}", SOURCE_EXPLICIT)
    return targets


def _extract_lifecycle(text: str, meta: dict[str, Any]) -> dict[str, str] | None:
    lifecycle: dict[str, str] = {}

    if _contains(text, (r"\bmvp\b",)):
        lifecycle["stage"] = "prototype"
        _append_provenance(meta, "/lifecycle/stage", SOURCE_INFERRED, "MVP was normalized to prototype stage.")
        _append_assumption(meta, "/lifecycle/stage", "prototype", "The request explicitly says MVP; prototype is the normalized lifecycle stage.")
    elif _contains(text, (r"原型", r"\bprototype\b")):
        lifecycle["stage"] = "prototype"
        _append_provenance(meta, "/lifecycle/stage", SOURCE_EXPLICIT)
    elif _contains(text, (r"实验项目", r"研究实验", r"\bexperimental\s+project\b")):
        lifecycle["stage"] = "experiment"
        _append_provenance(meta, "/lifecycle/stage", SOURCE_INFERRED, "Experimental project wording was normalized to experiment stage.")
        _append_assumption(meta, "/lifecycle/stage", "experiment", "The request describes the project as an experiment.")
    elif _contains(text, (r"生产环境", r"正式生产", r"\bproduction\b")):
        lifecycle["stage"] = "production"
        _append_provenance(meta, "/lifecycle/stage", SOURCE_EXPLICIT)

    if _contains(text, (r"长期维护", r"长期项目", r"持续多年", r"很多年", r"\blong[- ]lived\b", r"\blong[- ]term\b")):
        lifecycle["horizon"] = "long-lived"
        _append_provenance(meta, "/lifecycle/horizon", SOURCE_EXPLICIT)
    elif _contains(text, (r"一次性", r"用完就扔", r"\bthrowaway\b")):
        lifecycle["horizon"] = "throwaway"
        _append_provenance(meta, "/lifecycle/horizon", SOURCE_EXPLICIT)
    elif _contains(text, (r"短期", r"\bshort[- ]lived\b", r"\bshort[- ]term\b")):
        lifecycle["horizon"] = "short-lived"
        _append_provenance(meta, "/lifecycle/horizon", SOURCE_EXPLICIT)

    return lifecycle or None


def _extract_scope(text: str, meta: dict[str, Any]) -> dict[str, str] | None:
    rules = (
        ("very-large", (r"超大型", r"特大型", r"\bvery[- ]large\b")),
        ("large", (r"大型", r"大规模", r"\blarge[- ]scale\b", r"\blarge\b")),
        ("medium", (r"中型", r"中等规模", r"\bmedium[- ]scale\b")),
        ("small", (r"小型", r"小规模", r"\bsmall[- ]scale\b")),
        ("tiny", (r"微型", r"极小", r"\btiny\b")),
    )
    for value, patterns in rules:
        if _contains(text, patterns):
            _append_provenance(meta, "/scope/scale_hint", SOURCE_EXPLICIT)
            return {"scale_hint": value}

    line_count = re.search(r"(?:大约|约|不超过|少于)?\s*(\d{1,4})\s*行(?:代码)?", text)
    if line_count and int(line_count.group(1)) <= 200:
        _append_provenance(meta, "/scope/scale_hint", SOURCE_INFERRED, "A <=200 line request was normalized to tiny scale_hint.")
        _append_assumption(meta, "/scope/scale_hint", "tiny", "The request explicitly bounds the implementation to at most roughly 200 lines.")
        return {"scale_hint": "tiny"}
    return None


def _extract_constraints(text: str, meta: dict[str, Any]) -> dict[str, Any] | None:
    hard: list[str] = []
    for sentence in _extract_sentences(text):
        if _contains(sentence, _HARD_MARKERS):
            hard.append(sentence)

    quality: list[dict[str, str]] = []
    seen_quality: set[str] = set()
    for rule in _QUALITY_RULES:
        match = _first_match(text, rule.patterns)
        if not match or rule.value in seen_quality:
            continue
        seen_quality.add(rule.value)
        quality.append({"attribute": rule.value, "level": _quality_level(text, match)})

    constraints: dict[str, Any] = {}
    if hard:
        constraints["hard"] = _unique_preserve(hard)
        for index, _ in enumerate(constraints["hard"]):
            _append_provenance(meta, f"/constraints/hard/{index}", SOURCE_EXPLICIT)
    if quality:
        constraints["quality"] = quality
        for index, _ in enumerate(quality):
            _append_provenance(meta, f"/constraints/quality/{index}", SOURCE_EXPLICIT)
    return constraints or None


def _questions_from_meta(meta: dict[str, Any]) -> tuple[str, ...]:
    questions: list[str] = []
    for item in meta.get("unresolved", []):
        if not item.get("resolution_required"):
            continue
        path = item["path"]
        if path == "/work_products/0/kind":
            questions.append("What kind of deliverable should this be (for example CLI, web app, mobile app, desktop app, library, or research artifact)?")
        elif path == "/targets":
            questions.append("Which target platform(s) are required?")
        else:
            questions.append(f"Please resolve the requirement at {path}: {item['reason']}")
    return tuple(_unique_preserve(questions))


def normalize_requirement(text: str) -> NormalizationResult:
    if len(text) > MAX_REQUIREMENT_CHARS:
        raise ValueError(
            f"Requirement text is too large ({len(text)} characters); maximum is {MAX_REQUIREMENT_CHARS}."
        )
    normalized_text = " ".join(text.strip().split())
    if not normalized_text:
        raise ValueError("Requirement text must not be empty.")

    meta: dict[str, Any] = {"schema_version": "0.1"}
    safe_purpose, redacted = _redact_secrets(normalized_text)
    blueprint: dict[str, Any] = {
        "schema_version": "0.1",
        "project": {"purpose": safe_purpose},
    }
    _append_provenance(
        meta,
        "/project/purpose",
        SOURCE_EXPLICIT,
        "Potential secret material was redacted before persistence." if redacted else None,
    )

    blueprint["work_products"] = _extract_work_products(normalized_text, meta)

    targets = _extract_targets(normalized_text, meta)
    if targets:
        blueprint["targets"] = targets

    technology = _extract_technology(normalized_text, meta)
    if technology:
        blueprint["technology"] = technology

    lifecycle = _extract_lifecycle(normalized_text, meta)
    if lifecycle:
        blueprint["lifecycle"] = lifecycle

    scope = _extract_scope(normalized_text, meta)
    if scope:
        blueprint["scope"] = scope

    constraints = _extract_constraints(normalized_text, meta)
    if constraints:
        blueprint["constraints"] = constraints

    product_kinds = {item["kind"] for item in blueprint["work_products"]}
    target_values = {item["value"] for item in targets}
    if "mobile-app" in product_kinds and not ({"ios", "android"} & target_values):
        _append_unresolved(
            meta,
            "/targets",
            "A mobile application was requested but iOS/Android target platforms were not specified.",
            resolution_required=True,
        )

    validation = validate_blueprint(blueprint, meta)
    questions = _questions_from_meta(meta)
    return NormalizationResult(
        blueprint=blueprint,
        metadata=meta,
        validation=validation,
        questions=questions,
    )


def write_normalization(result: NormalizationResult, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    blueprint_path = output_dir / "project.blueprint.yaml"
    meta_path = output_dir / "project.blueprint.meta.yaml"
    blueprint_path.write_text(
        yaml.safe_dump(result.blueprint, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    meta_path.write_text(
        yaml.safe_dump(result.metadata, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return blueprint_path, meta_path


def _exit_code(result: NormalizationResult) -> int:
    if result.validation.structure_status != "STRUCTURALLY_VALID":
        return 1
    if result.validation.readiness_status == "USABLE":
        return 0
    if result.validation.readiness_status == "NEEDS_RESOLUTION":
        return 2
    if result.validation.readiness_status == "BLOCKED":
        return 3
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Conservatively normalize natural-language project requirements into Blueprint V0.1")
    parser.add_argument("text", nargs="?", help="Natural-language project requirement. If omitted, read stdin.")
    parser.add_argument("--out-dir", type=Path, default=None, help="Write project.blueprint.yaml and project.blueprint.meta.yaml")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    text = args.text
    if text is None:
        import sys

        text = sys.stdin.read()

    try:
        result = normalize_requirement(text)
    except ValueError as exc:
        if args.as_json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}")
        return 1

    written: list[str] = []
    if args.out_dir is not None:
        paths = write_normalization(result, args.out_dir)
        written = [str(path) for path in paths]

    if args.as_json:
        payload = result.to_dict()
        payload["written"] = written
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"structure_status: {result.validation.structure_status}")
        print(f"readiness_status: {result.validation.readiness_status or '-'}")
        for question in result.questions:
            print(f"question: {question}")
        for path in written:
            print(f"written: {path}")
    return _exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())

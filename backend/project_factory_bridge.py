from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
import socket
import sys
import time
from typing import Any

# backend/  contains gui_catalog, module_store, wheel_store, user_resources, network_ops
# When launched from the installed runtime, this directory is not automatically on sys.path.
_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

os.environ.setdefault("PROJECT_FACTORY_LOAD_USER_WAREHOUSE", "1")

from project_factory.ai_adapter import AIEndpointConfig, OpenAICompatibleSemanticAdapter
from project_factory.factory import FACTORY_STAGE, FACTORY_VERSION, generate_project, restore_verify_project_zip
from project_factory.tools import apply_owned_tools_path, owned_provider_dirs, resolve_executable
from project_factory.product import doctor
from project_factory.requirements_matrix import apply_matrix_overrides, build_requirement_matrix
from project_factory.ux import check_project


# Set when AI was enabled but had to be skipped, so the GUI can tell the user plainly
# that generation used the deterministic local intake instead of failing outright.
_LATEST_AI_DEGRADATION: dict[str, Any] = {}


def _appdata() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "ProjectFactory"
    return Path.home() / ".project-factory"


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _append_history(record: dict[str, Any]) -> None:
    path = _appdata() / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _read_history(limit: int = 100) -> list[dict[str, Any]]:
    path = _appdata() / "history.jsonl"
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            out.append(item)
    out.reverse()
    return out


def _semantic_adapter(ai: Any):
    """Build the AI adapter, or fall back to the deterministic local one.

    AI is an *enhancement* for generation, never a precondition: the kernel already
    runs on ``DeterministicSemanticAdapter`` when no adapter is supplied, so a broken
    or unreachable AI must not be able to block the whole assembly.  Reaching the
    fallback is reported through :func:`_ai_degradation` so the GUI can say so plainly.
    """
    if not isinstance(ai, dict) or not ai.get("enabled"):
        return None
    endpoint = str(ai.get("endpoint") or "").strip()
    model = str(ai.get("model") or "").strip()
    key_env = str(ai.get("key_env") or "").strip()
    if not endpoint or not model:
        raise ValueError("AI enabled but endpoint/model is incomplete.")
    adapter = OpenAICompatibleSemanticAdapter(AIEndpointConfig(endpoint=endpoint, model=model, api_key_env=key_env or ""))
    try:
        # Probe with a short timeout before the real request.  If the endpoint is
        # unreachable, lacks credentials, or answers in a way that would fail the
        # provenance contract mid-build, return None so the kernel uses its own
        # DeterministicSemanticAdapter -- which keeps the correct trust_class and
        # therefore the correct (local) validation rules.
        adapter.probe()
    except Exception as exc:  # noqa: BLE001 - any AI failure degrades, never blocks.
        _ai_degradation(endpoint, model, exc)
        return None
    return adapter


def _ai_degradation(endpoint: str, model: str, exc: Exception) -> None:
    """Record why AI was skipped, for the GUI to surface honestly."""
    _LATEST_AI_DEGRADATION.clear()
    _LATEST_AI_DEGRADATION.update(
        {
            "skipped": True,
            "endpoint": endpoint,
            "model": model,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    )


def _tools_status() -> dict[str, Any]:
    apply_owned_tools_path()
    rows = []
    for name, pin in (("uv", "0.10.0"), ("npm", "10.9.2"), ("cargo", "1.98.0"), ("dotnet", "9.0.315")):
        path = resolve_executable(name)
        version = ""
        if path:
            import subprocess

            probe = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
            version = (probe.stdout or probe.stderr or "").strip().splitlines()[0] if (probe.stdout or probe.stderr) else ""
        rows.append(
            {
                "id": name,
                "label": name,
                "pinned": pin,
                "path": path or "",
                "version": version,
                "owned": bool(path) and pin in version,
            }
        )
    return {"status": "OK", "dirs": [str(path) for path in owned_provider_dirs()], "items": rows}


def _ollama_base(endpoint: str) -> str:
    text = endpoint.strip()
    if "/v1" in text:
        text = text.split("/v1", 1)[0]
    if "/api" in text:
        text = text.split("/api", 1)[0]
    return text.rstrip("/")


def _is_ollama(endpoint: str) -> bool:
    folded = endpoint.casefold()
    return "11434" in folded or "ollama" in folded


def _http_json(url: str, *, data: bytes | None = None, timeout: int = 20) -> dict[str, Any]:
    from urllib.request import Request, urlopen

    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    with urlopen(req, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _ollama_models(endpoint: str) -> dict[str, Any]:
    if not _is_ollama(endpoint):
        raise ValueError("这不是 Ollama 地址。Ollama 只读本机 11434 上已经 pull 过的模型。")
    try:
        payload = _http_json(_ollama_base(endpoint) + "/api/tags", timeout=8)
    except Exception as exc:
        raise ValueError("读不到本机 Ollama。先确认 ollama serve 在跑，再用 ollama list 看模型。") from exc
    names = []
    for item in payload.get("models") or []:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return {
        "status": "OK",
        "models": names,
        "note": "只列出本机已经安装的模型，不会替你下载。模型名为空就先 ollama pull。",
    }


def _assist_messages(requirement: str) -> list[dict[str, str]]:
    import yaml
    from project_factory.template import AI_FILL_INSTRUCTIONS, empty_template

    blank = yaml.safe_dump(empty_template(), sort_keys=False, allow_unicode=True)
    user = (
        "用户原始想法：\n"
        + (requirement or "（空）")
        + "\n\n请按系统指令工作：先写一段工厂能懂的中文描述，再填下面这份模板。不要编业务功能。\n\n"
        + blank
    )
    return [
        {"role": "system", "content": AI_FILL_INSTRUCTIONS},
        {"role": "user", "content": user},
    ]


def _parse_assist_text(raw: str) -> dict[str, Any]:
    import re

    import yaml

    text = str(raw or "").strip()
    spec = None
    prose = text
    match = re.search(r"```(?:yaml|yml)?\s*\n(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    blob = match.group(1) if match else ""
    if match:
        prose = (text[: match.start()] + text[match.end() :]).strip()
    else:
        blob = text
    try:
        loaded = yaml.safe_load(blob)
    except yaml.YAMLError:
        loaded = None
    if isinstance(loaded, dict) and (
        loaded.get("schema") or loaded.get("work_products") is not None or loaded.get("purpose")
    ):
        spec = loaded
        if not prose:
            prose = str(loaded.get("purpose") or text)
    return {"text": prose or text, "spec": spec}


def _ai_assist(requirement: str, ai: Any) -> dict[str, Any]:
    if not isinstance(ai, dict) or not ai.get("enabled"):
        raise ValueError("先展开「AI 辅助」并启用。Ollama 要先读取本机已装模型。")
    endpoint = str(ai.get("endpoint") or "").strip()
    model = str(ai.get("model") or "").strip()
    key_env = str(ai.get("key_env") or "").strip()
    if not endpoint:
        raise ValueError("AI endpoint 不完整。")
    messages = _assist_messages(requirement)
    if _is_ollama(endpoint):
        if not model:
            raise ValueError("还没有选定 Ollama 模型。点「读取本机模型」从 ollama list 里选一个。")
        payload = _http_json(
            _ollama_base(endpoint) + "/api/chat",
            data=json.dumps({"model": model, "stream": False, "messages": messages}, ensure_ascii=False).encode("utf-8"),
            timeout=120,
        )
        text = str((payload.get("message") or {}).get("content") or "").strip()
        if not text:
            raise ValueError("Ollama 没有返回文本。确认模型名就是 ollama list 里的那一行。")
        parsed = _parse_assist_text(text)
        parsed["status"] = "OK"
        return parsed

    if not model:
        raise ValueError("AI model 不完整。")
    from urllib.request import Request, urlopen

    key = os.environ.get(key_env, "") if key_env else ""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    elif key_env:
        raise ValueError(f"环境变量 {key_env} 没有值。")
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.2}, ensure_ascii=False).encode("utf-8")
    req = Request(endpoint, data=body, headers=headers, method="POST")
    with urlopen(req, timeout=90) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        text = json.dumps(payload, ensure_ascii=False)[:2000]
    parsed = _parse_assist_text(str(text))
    parsed["status"] = "OK"
    return parsed


def handle(request: dict[str, Any]) -> dict[str, Any]:
    apply_owned_tools_path()
    action = str(request.get("action") or "").strip()
    payload = request.get("payload") or {}
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    if action == "ping":
        return {"status": "OK", "factory": {"version": FACTORY_VERSION, "stage": FACTORY_STAGE}}

    if action == "advise":
        # Pre-flight selection advisor: warns the GUI about mutually-exclusive (factory will
        # reject) or functionally-overlapping (factory silently prefers one) selections, plus
        # tech/body mismatches. Mirrors the assembly planner but in human wording.
        from project_factory.selection_advisor import advise_selection

        work_products = payload.get("work_products") or []
        technology = payload.get("technology") or []
        if not isinstance(work_products, list):
            work_products = [work_products]
        if not isinstance(technology, list):
            technology = [technology]
        return {"status": "OK", "advice": advise_selection(work_products, technology)}

    if action == "status":
        return _jsonable(doctor(deep=bool(payload.get("deep", False))))

    if action == "overview":
        # R2 adjacent: one Process instead of 5 serial on ResourcesPage
        from gui_catalog import catalog as _cat2
        from module_store import list_modules as _lm2
        from wheel_store import list_store as _ls2
        from user_resources import list_resources as _lr2

        out: dict[str, Any] = {"status": "OK"}
        try:
            out["factory_version"] = {"version": FACTORY_VERSION, "stage": FACTORY_STAGE}
        except Exception:
            pass
        try:
            out["wheels"] = _ls2()
        except Exception as e:
            out["wheels"] = {"error": str(e)}
        try:
            out["resources"] = _lr2()
        except Exception as e:
            out["resources"] = {"error": str(e)}
        try:
            out["tools"] = _tools_status()
        except Exception as e:
            out["tools"] = {"error": str(e)}
        try:
            extras2: list[dict[str, Any]] = []
            try:
                extras2.extend(_lm2().get("items") or [])
            except Exception:
                pass
            try:
                for it in _lr2().get("items") or []:
                    n = str(it.get("name") or "")
                    extras2.append({"id": Path(n).stem, "label": n, "kind": "file", "status": "preloaded", "purpose": "用户仓库文件", "source": it.get("path") or "", "body": Path(n).stem})
            except Exception:
                pass
            cat2 = _cat2(extras2)
            out["catalog"] = cat2
            out["factory_lines"] = cat2.get("factory_lines", [])
            out["modules"] = _lm2()
        except Exception as e:
            out["catalog_error"] = str(e)
        return out

    if action == "catalog.gui":
        from gui_catalog import catalog

        extras: list[dict[str, Any]] = []
        try:
            from module_store import list_modules

            extras.extend(list_modules().get("items") or [])
        except Exception:
            pass
        try:
            from user_resources import list_resources

            for item in list_resources().get("items") or []:
                name = str(item.get("name") or "")
                extras.append(
                    {
                        "id": Path(name).stem,
                        "label": name,
                        "kind": "file",
                        "status": "preloaded",
                        "purpose": "用户仓库文件",
                        "source": item.get("path") or "",
                        "body": Path(name).stem,
                    }
                )
        except Exception:
            pass
        return {"status": "OK", "catalog": catalog(extras)}

    if action == "ai.presets":
        from gui_catalog import AI_PRESETS

        return {"status": "OK", "presets": AI_PRESETS}

    if action == "ai.assist":
        return _ai_assist(str(payload.get("requirement") or "").strip(), payload.get("ai"))

    if action == "ai.models":
        return _ollama_models(str(payload.get("endpoint") or ""))

    if action == "tools.list":
        return _tools_status()

    if action == "modules.list":
        from module_store import list_modules

        return list_modules()

    if action == "modules.download":
        from module_store import download_module

        return download_module(str(payload.get("id") or ""), str(payload.get("url") or ""))

    if action == "modules.import":
        from module_store import import_module

        return import_module(str(payload.get("path") or ""))

    if action == "modules.update":
        from module_store import update_module

        fields = payload.get("fields") or {}
        if not isinstance(fields, dict):
            raise ValueError("fields must be an object")
        return update_module(str(payload.get("family") or ""), str(payload.get("version") or ""), fields)

    if action == "modules.delete":
        from module_store import delete_module

        return delete_module(str(payload.get("family") or ""), str(payload.get("version") or ""))

    if action == "ai.probe":
        endpoint = str(payload.get("endpoint") or "").strip()
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("endpoint must be http(s)")
        if _is_ollama(endpoint):
            try:
                listed = _ollama_models(endpoint)
            except Exception as exc:
                return {"status": "FAIL", "error": str(exc)}
            return {
                "status": "OK",
                "http": 200,
                "models": listed.get("models") or [],
                "note": listed.get("note") or "",
            }
        from urllib.request import Request, urlopen

        req = Request(endpoint, method="GET")
        try:
            with urlopen(req, timeout=8) as response:  # noqa: S310
                code = getattr(response, "status", 200)
        except Exception as exc:
            return {"status": "FAIL", "error": str(exc)}
        return {"status": "OK", "http": code, "note": "地址能通。Chat Completions 还要密钥和模型名。"}

    if action == "wheels.list":
        from wheel_store import list_store

        return list_store()

    if action == "wheels.import":
        from wheel_store import import_local

        return import_local(str(payload.get("path") or ""))

    if action == "wheels.download":
        from wheel_store import download

        return download(str(payload.get("url") or ""))

    if action == "wheels.auto_update":
        from wheel_store import set_auto_update

        return set_auto_update(bool(payload.get("enabled")))

    if action == "wheels.apply":
        from wheel_store import apply_kernel_wheel

        return apply_kernel_wheel(str(payload.get("path") or ""))

    if action == "wheels.delete":
        from wheel_store import delete_wheel

        return delete_wheel(str(payload.get("path") or ""))

    if action == "factory.version":
        return {"status": "OK", "version": FACTORY_VERSION, "stage": FACTORY_STAGE}

    if action == "resources.list":
        from user_resources import list_resources

        return list_resources()

    if action == "resources.import":
        from user_resources import import_resource

        return import_resource(str(payload.get("path") or ""))

    if action == "resources.delete":
        from user_resources import delete_resource

        return delete_resource(str(payload.get("path") or ""))

    if action == "blueprint.export":
        from user_resources import export_blueprint

        spec = payload.get("spec")
        if not isinstance(spec, dict):
            raise ValueError("spec must be an object")
        return export_blueprint(spec, str(payload.get("path") or ""))

    if action == "blueprint.import":
        from user_resources import load_blueprint

        return load_blueprint(str(payload.get("path") or ""))

    if action == "analyze":
        requirement = str(payload.get("requirement") or "").strip()
        if not requirement:
            raise ValueError("requirement is empty")
        adapter = _semantic_adapter(payload.get("ai"))
        result = build_requirement_matrix(requirement, adapter=adapter)
        return _jsonable(result.to_dict())

    if action == "template.export":
        from project_factory.template import export_template

        dest = str(payload.get("path") or "").strip()
        template = export_template(Path(dest) if dest else None)
        return {"status": "OK", "template": template, "path": dest}

    if action == "assemble":
        from project_factory.assembly import AssemblyOptions

        project_name = str(payload.get("project_name") or "").strip()
        output_dir = Path(str(payload.get("output_dir") or "")).expanduser()
        spec = payload.get("spec")
        if not project_name or not str(output_dir):
            raise ValueError("project_name and output_dir are required")
        raw_options = payload.get("options") or {}
        if payload.get("blank") or (isinstance(raw_options, dict) and not any(raw_options.get(key, True) for key in ("scaffold", "verification", "overlay", "harness", "readme"))):
            options = AssemblyOptions(False, False, False, False, False, ())
            spec = spec if isinstance(spec, dict) else None
        else:
            options = AssemblyOptions(
                scaffold=bool(raw_options.get("scaffold", True)),
                verification=bool(raw_options.get("verification", True)),
                overlay=bool(raw_options.get("overlay", True)),
                harness=bool(raw_options.get("harness", True)),
                readme=bool(raw_options.get("readme", True)),
                harness_ids=tuple(raw_options.get("harnesses") or []) or None,
            )
            if not options.harness:
                options = AssemblyOptions(options.scaffold, options.verification, options.overlay, False, options.readme, ())
        result = generate_project(
            str(payload.get("requirement") or ""),
            project_name,
            output_dir,
            options=options,
            spec=spec if isinstance(spec, dict) else None,
            semantic_adapter=_semantic_adapter(payload.get("ai")),
        )
        return {
            "status": result.verification.get("status"),
            "project_name": result.project_name,
            "project_root": str(result.project_root),
            "project_zip": str(result.project_zip),
            "profile": result.profile.profile_id,
            "verification": _jsonable(result.verification),
        }

    if action == "generate":
        requirement = str(payload.get("requirement") or "").strip()
        project_name = str(payload.get("project_name") or "").strip()
        output_dir = Path(str(payload.get("output_dir") or "")).expanduser()
        overrides = payload.get("overrides") or {}
        if not requirement or not project_name or not str(output_dir):
            raise ValueError("requirement, project_name and output_dir are required")
        matrix = build_requirement_matrix(requirement, adapter=_semantic_adapter(payload.get("ai")))
        confirmed = apply_matrix_overrides(matrix, overrides if isinstance(overrides, dict) else {})
        from project_factory.assembly import AssemblyOptions

        raw_options = payload.get("options") or {}
        options = None
        if isinstance(raw_options, dict) and raw_options:
            options = AssemblyOptions(
                scaffold=bool(raw_options.get("scaffold", True)),
                verification=bool(raw_options.get("verification", True)),
                overlay=bool(raw_options.get("overlay", True)),
                harness=bool(raw_options.get("harness", True)),
                readme=bool(raw_options.get("readme", True)),
                harness_ids=tuple(raw_options.get("harnesses") or []) or None,
            )
        result = generate_project(requirement, project_name, output_dir, semantic_adapter=confirmed, options=options)
        response = {
            "ai_degraded": dict(_LATEST_AI_DEGRADATION) if _LATEST_AI_DEGRADATION else None,
            "status": "VERIFIED" if result.verification.get("status") in {"PASS", "VERIFIED"} else result.verification.get("status", "UNKNOWN"),
            "project_name": result.project_name,
            "project_root": str(result.project_root),
            "project_zip": str(result.project_zip),
            "profile": result.profile.profile_id,
            "verification": _jsonable(result.verification),
            "blueprint": _jsonable(result.blueprint),
        }
        _append_history({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "project_name": result.project_name,
            "project_root": str(result.project_root),
            "project_zip": str(result.project_zip),
            "profile": result.profile.profile_id,
            "status": response["status"],
        })
        return response

    if action == "history":
        return {"status": "OK", "items": _read_history(int(payload.get("limit", 100)))}

    if action == "check":
        return _jsonable(check_project(Path(str(payload.get("project_root") or ""))))

    if action == "verify_zip":
        return _jsonable(restore_verify_project_zip(Path(str(payload.get("zip_path") or ""))))

    raise ValueError(f"unknown action: {action}")


def _write_response(req_id: Any, ok: bool, result: Any = None, error: str | None = None, message: str | None = None) -> None:
    payload: dict[str, Any] = {"id": req_id, "ok": ok}
    if ok:
        payload["result"] = result
    else:
        payload["error"] = error
        payload["message"] = message
    # Line-delimited protocol: one JSON object per line, flush after each so the
    # resident client can match responses by request id. ensure_ascii=False already
    # emits UTF-8; a plain "\n" terminates the line (no BOM).
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    # Resident line protocol: read one JSON request per line from stdin, write one
    # JSON response line per request (id-matched). EOF on stdin terminates the loop
    # cleanly, so one-shot callers that close stdin after a single request still work.
    try:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except Exception as exc:
                _write_response(None, False, error=type(exc).__name__, message=f"invalid JSON: {exc}")
                continue
            if not isinstance(request, dict):
                _write_response(None, False, error="TypeError", message="request must be a JSON object")
                continue
            req_id = request.get("id")
            try:
                result = handle(request)
                _write_response(req_id, True, result=result)
            except Exception as exc:
                _write_response(req_id, False, error=type(exc).__name__, message=str(exc))
        return 0
    except Exception as exc:
        # Outer failure (e.g. stdin broke): best-effort log and exit.
        sys.stderr.write(f"bridge fatal: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

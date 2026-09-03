from __future__ import annotations

import json
import os
from pathlib import Path
import time

APP_TITLE = "Project Factory 0.14.1 - Windows Fluent UX5.0"
OFFICIAL_INDEX = "https://pypi.org/simple"
TUNA_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
BFSU_INDEX = "https://mirrors.bfsu.edu.cn/pypi/web/simple"
USTC_INDEX = "https://mirrors.ustc.edu.cn/pypi/simple"
ALIYUN_INDEX = "https://mirrors.aliyun.com/pypi/simple"
HUAWEI_INDEX = "https://mirrors.huaweicloud.com/repository/pypi/simple"
AUTO_SOURCE_NAME = "自动镜像池（推荐）"
SOURCE_OPTIONS = {
    "清华 TUNA": TUNA_INDEX,
    "北外 BFSU": BFSU_INDEX,
    "中科大 USTC": USTC_INDEX,
    "阿里云": ALIYUN_INDEX,
    "华为云": HUAWEI_INDEX,
    "官方 PyPI": OFFICIAL_INDEX,
}
SOURCE_ORDER = tuple(SOURCE_OPTIONS)


def appdata_root() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "ProjectFactory"
    return Path.home() / ".project-factory"


NETWORK_STATE = appdata_root() / "network_state.json"


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def load_last_success_source() -> str:
    try:
        data = json.loads(NETWORK_STATE.read_text(encoding="utf-8"))
        value = str(data.get("last_success_source") or "")
        return value if value in SOURCE_OPTIONS else ""
    except Exception:
        return ""


def record_source_success(source_name: str) -> None:
    if source_name not in SOURCE_OPTIONS:
        return
    NETWORK_STATE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"last_success_source": source_name, "updated_at": _ts()}
    temp = NETWORK_STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, NETWORK_STATE)


def source_failover_order(source_name: str) -> list[str]:
    if source_name != AUTO_SOURCE_NAME:
        if source_name not in SOURCE_OPTIONS:
            raise ValueError(f"Unknown package source: {source_name}")
        return [source_name]
    order = list(SOURCE_ORDER)
    remembered = load_last_success_source()
    if remembered and remembered in order:
        order.remove(remembered)
        order.insert(0, remembered)
    return order


def self_test() -> None:
    assert len(SOURCE_OPTIONS) >= 6
    assert SOURCE_ORDER[0] == "清华 TUNA"
    assert all(value.startswith("https://") for value in SOURCE_OPTIONS.values())
    assert source_failover_order("官方 PyPI") == ["官方 PyPI"]

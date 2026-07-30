"""lib/tools.py — Function Calling tools for detective actions"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CCTV_PATH = ROOT / "data" / "tools" / "cctv.yaml"
FORENSIC_PATH = ROOT / "data" / "tools" / "forensic.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def request_cctv_log(location: str) -> dict[str, Any]:
    """CCTV 조회. 로비 등은 결측, 라운지/복도는 부분 단서."""
    cfg = _load_yaml(CCTV_PATH)
    key = (location or "").strip().lower().replace(" ", "_")
    aliases = {
        "로비": "lobby",
        "lobby": "lobby",
        "라운지": "lounge",
        "휴게실": "lounge",
        "lounge": "lounge",
        "서버실": "server_room",
        "server_room": "server_room",
        "server": "server_room",
        "3층": "office_floor3",
        "복도": "office_floor3",
        "office": "office_floor3",
        "office_floor3": "office_floor3",
    }
    loc = aliases.get(key, key)
    locations = cfg.get("locations", {})
    payload = locations.get(loc)
    if not payload:
        return {
            "tool": "request_cctv_log",
            "location": location,
            "status": "not_found",
            "message": f"위치 '{location}' CCTV 정의 없음. lobby|lounge|server_room|office_floor3",
            "hint": cfg.get("default_note"),
        }
    return {
        "tool": "request_cctv_log",
        "location": loc,
        "status": payload.get("status"),
        "reason": payload.get("reason"),
        "entries": payload.get("entries") or [],
        "note": cfg.get("default_note"),
    }


def run_forensic(device: str) -> dict[str, Any]:
    """기기 포렌식. 삭제 메시지·MAC 힌트 등 사전 시나리오 데이터 반환."""
    cfg = _load_yaml(FORENSIC_PATH)
    key = (device or "").strip().lower().replace(" ", "_")
    aliases = {
        "이대리": "lee_laptop",
        "이대리노트북": "lee_laptop",
        "lee": "lee_laptop",
        "lee_laptop": "lee_laptop",
        "suspect_b": "lee_laptop",
        "김팀장": "kim_pc",
        "kim": "kim_pc",
        "kim_pc": "kim_pc",
        "suspect_a": "kim_pc",
        "박신입": "park_phone",
        "park": "park_phone",
        "park_phone": "park_phone",
        "suspect_c": "park_phone",
    }
    dev = aliases.get(key, key)
    devices = cfg.get("devices", {})
    payload = devices.get(dev)
    if not payload:
        return {
            "tool": "run_forensic",
            "device": device,
            "status": "not_found",
            "message": f"기기 '{device}' 포렌식 정의 없음. lee_laptop|kim_pc|park_phone",
        }
    result = {
        "tool": "run_forensic",
        "device": dev,
        "status": "ok",
        "label": payload.get("label"),
        "owner": payload.get("owner"),
        "findings": payload.get("findings") or [],
    }
    if payload.get("mac"):
        result["mac"] = payload["mac"]
    return result


TOOL_REGISTRY = {
    "request_cctv_log": lambda args: request_cctv_log(str(args.get("location", ""))),
    "run_forensic": lambda args: run_forensic(str(args.get("device", ""))),
}


def call_tool(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    args = args or {}
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        return {
            "error": "unknown_tool",
            "name": name,
            "available": list(TOOL_REGISTRY.keys()),
        }
    return fn(args)

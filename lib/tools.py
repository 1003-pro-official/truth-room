# -*- coding: utf-8 -*-
"""lib/tools.py — Function Calling tools for detective actions"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from lib.assistant_prompt import unauthorized_message

ROOT = Path(__file__).resolve().parent.parent
CCTV_PATH = ROOT / "data" / "tools" / "cctv.yaml"
FORENSIC_PATH = ROOT / "data" / "tools" / "forensic.yaml"
CARD_PATH = ROOT / "data" / "tools" / "card.yaml"
MESSENGER_PATH = ROOT / "data" / "tools" / "messenger.yaml"


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
        "summary": _dry_summary_cctv(payload),
    }


def _dry_summary_cctv(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "")
    reason = str(payload.get("reason") or "")
    if status == "missing" or "결측" in reason:
        return "해당 구간 CCTV 결측 확인됨."
    entries = payload.get("entries") or []
    if entries:
        first = entries[0] if isinstance(entries[0], dict) else {}
        ts = first.get("ts") or first.get("time") or ""
        text = first.get("text") or first.get("note") or reason or "기록 확인됨."
        return f"{ts} {text}".strip()
    return reason or "CCTV 기록 확인됨."


def run_forensic(device: str = "", suspect_name: str = "") -> dict[str, Any]:
    """기기 포렌식. device 또는 suspect_name으로 조회."""
    cfg = _load_yaml(FORENSIC_PATH)
    key = (device or suspect_name or "").strip().lower().replace(" ", "_")
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
    # suspect_name이 한글일 때도 매핑
    if suspect_name and not device:
        key = aliases.get(suspect_name.strip(), aliases.get(key, key))
    else:
        key = aliases.get(key, key)
    devices = cfg.get("devices", {})
    payload = devices.get(key)
    if not payload:
        return {
            "tool": "run_forensic",
            "device": device or suspect_name,
            "status": "not_found",
            "message": unauthorized_message(),
            "summary": unauthorized_message(),
        }
    findings = payload.get("findings") or []
    facts: list[str] = []
    for item in findings:
        if not isinstance(item, dict):
            continue
        if item.get("text"):
            facts.append(str(item["text"]))
        for msg in item.get("items") or []:
            if isinstance(msg, dict) and msg.get("text"):
                ts = msg.get("ts") or ""
                facts.append(f"{ts} {msg['text']}".strip())
    summary = facts[0] if facts else "포렌식 기록 확인됨."
    result = {
        "tool": "run_forensic",
        "device": key,
        "status": "ok",
        "label": payload.get("label"),
        "owner": payload.get("owner"),
        "findings": findings,
        "facts": facts,
        "summary": summary,
    }
    if payload.get("mac"):
        result["mac"] = payload["mac"]
    return result


def check_card_history(suspect_name: str) -> dict[str, Any]:
    """법인카드 결제 내역 조회 — 사실만 반환."""
    cfg = _load_yaml(CARD_PATH)
    key = (suspect_name or "").strip()
    suspects = cfg.get("suspects") or {}
    payload = suspects.get(key) or suspects.get(key.lower())
    if not payload:
        # id 별칭
        for alias, row in suspects.items():
            if str(row.get("suspect_id")) == key:
                payload = row
                break
    if not payload:
        return {
            "tool": "check_card_history",
            "suspect_name": suspect_name,
            "status": "denied",
            "message": unauthorized_message(),
            "summary": unauthorized_message(),
        }
    facts = [str(f) for f in (payload.get("facts") or [])]
    return {
        "tool": "check_card_history",
        "suspect_name": suspect_name,
        "suspect_id": payload.get("suspect_id"),
        "status": "ok",
        "facts": facts,
        "summary": facts[0] if facts else "결제 기록 확인됨.",
    }


def search_messenger(suspect_name: str, keyword: str = "") -> dict[str, Any]:
    """사내 메신저 검색 — 사실만 반환."""
    cfg = _load_yaml(MESSENGER_PATH)
    name = (suspect_name or "").strip()
    kw = (keyword or "").strip().lower()
    for entry in cfg.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        keys = [str(k) for k in (entry.get("suspect_keys") or [])]
        if name not in keys:
            continue
        keywords = [str(k).lower() for k in (entry.get("keywords") or [])]
        if kw and kw not in keywords and not any(k and k in kw for k in keywords if k):
            # 키워드 불일치여도 빈 키워드("") 허용 엔트리면 통과
            if "" not in keywords:
                continue
        facts = [str(f) for f in (entry.get("facts") or [])]
        return {
            "tool": "search_messenger",
            "suspect_name": suspect_name,
            "keyword": keyword,
            "status": "ok",
            "facts": facts,
            "summary": facts[0] if facts else "메신저 기록 확인됨.",
        }
    return {
        "tool": "search_messenger",
        "suspect_name": suspect_name,
        "keyword": keyword,
        "status": "denied",
        "message": unauthorized_message(),
        "summary": unauthorized_message(),
    }


TOOL_REGISTRY = {
    "request_cctv_log": lambda args: request_cctv_log(str(args.get("location", ""))),
    "run_forensic": lambda args: run_forensic(
        device=str(args.get("device", "")),
        suspect_name=str(args.get("suspect_name", "")),
    ),
    "check_card_history": lambda args: check_card_history(str(args.get("suspect_name", ""))),
    "search_messenger": lambda args: search_messenger(
        str(args.get("suspect_name", "")),
        str(args.get("keyword", "")),
    ),
}


def call_tool(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    args = args or {}
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        msg = unauthorized_message()
        return {
            "error": "unknown_tool",
            "name": name,
            "message": msg,
            "summary": msg,
            "available": list(TOOL_REGISTRY.keys()),
        }
    return fn(args)

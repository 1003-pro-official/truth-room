# -*- coding: utf-8 -*-
"""조수 AI 시스템 프롬프트 — RAG 라우터 / Function Calling 템플릿."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "data" / "assistant" / "prompt_template.yaml"

_CACHE: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        if not TEMPLATE_PATH.exists():
            _CACHE = {}
        else:
            with TEMPLATE_PATH.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            _CACHE = data if isinstance(data, dict) else {}
    return _CACHE


def assistant_system_prompt() -> str:
    """조수 AI 시스템 프롬프트 본문."""
    return str(_load().get("template") or "").strip()


def unauthorized_message() -> str:
    return str(_load().get("unauthorized_message") or "해당 조사 권한이 없습니다").strip()


def assistant_function_names() -> list[str]:
    funcs = _load().get("functions") or []
    names: list[str] = []
    if isinstance(funcs, list):
        for item in funcs:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
    return names

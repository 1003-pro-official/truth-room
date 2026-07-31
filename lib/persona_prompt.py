# -*- coding: utf-8 -*-
"""용의자 시스템 프롬프트 — 마스터 템플릿 + prompt_vars 치환."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "data" / "personas" / "prompt_template.yaml"

_TEMPLATE_CACHE: dict[str, Any] | None = None


def _load_template() -> dict[str, Any]:
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is None:
        with TEMPLATE_PATH.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _TEMPLATE_CACHE = data if isinstance(data, dict) else {}
    return _TEMPLATE_CACHE


def pressure_to_stress(pressure: float) -> int:
    """세션 pressure(0..1) → 템플릿 stress_level(0..100)."""
    try:
        p = float(pressure)
    except (TypeError, ValueError):
        p = 0.0
    return max(0, min(100, int(round(p * 100))))


def render_suspect_prompt(
    persona: dict[str, Any],
    *,
    stress_level: int | None = None,
    mental_break: bool = False,
    pressure: float | None = None,
) -> str:
    """
    prompt_vars로 마스터 템플릿을 채운다.
    stress_level 미지정 시 pressure 또는 0.
    mental_break면 addon 붙이고 stress 하한을 71로 올린다.
    """
    tmpl = _load_template()
    body = str(tmpl.get("template") or "").strip()
    addon = str(tmpl.get("mental_break_addon") or "").strip()
    raw_vars = persona.get("prompt_vars") or {}
    if not isinstance(raw_vars, dict):
        raw_vars = {}

    if stress_level is None:
        if pressure is not None:
            stress_level = pressure_to_stress(pressure)
        else:
            stress_level = 0
    if mental_break:
        stress_level = max(71, int(stress_level))

    filled: dict[str, str] = {
        str(k): str(v).strip() if v is not None else "" for k, v in raw_vars.items()
    }
    filled["stress_level"] = str(int(stress_level))

    # 누락 키는 빈 문자열로 남겨 FormatError 방지
    class _Safe(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    text = body.format_map(_Safe(filled))
    if mental_break and addon:
        text = text + "\n\n" + addon.format_map(_Safe(filled))

    # 정적 system_prompt가 있고 prompt_vars가 비면 폴백
    if not raw_vars:
        key = "system_prompt_mental_break" if mental_break else "system_prompt"
        fallback = str(persona.get(key) or persona.get("system_prompt") or "").strip()
        if fallback:
            return fallback
    return text.strip()

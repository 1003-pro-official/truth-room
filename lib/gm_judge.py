# -*- coding: utf-8 -*-
"""게임마스터(심판) AI — 알리바이 붕괴 판정 (LangGraph · UI 미노출)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "data" / "gm" / "prompt_template.yaml"

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


def judge_system_prompt() -> str:
    """템플릿 원문(변수 미치환). LLM 시스템 프롬프트용."""
    return str(_load().get("template") or "").strip()


def render_judge_prompt(
    *,
    prompt_vars: dict[str, Any] | None,
    user_input: str,
    npc_response: str = "",
) -> str:
    """심판 프롬프트에 용의자 변수·발언을 채운다."""
    body = judge_system_prompt()
    vars_ = {str(k): str(v) if v is not None else "" for k, v in (prompt_vars or {}).items()}
    vars_["user_input"] = str(user_input or "")
    vars_["npc_response"] = str(npc_response or "")

    class _Safe(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    # 템플릿의 JSON 예시 중 {{ }} 는 format 후 단일 {}
    return body.format_map(_Safe(vars_)).strip()


def _clamp_delta(value: int) -> int:
    schema = _load().get("output_schema") or {}
    lo = int(schema.get("stress_delta_min", -10))
    hi = int(schema.get("stress_delta_max", 30))
    return max(lo, min(hi, int(value)))


def parse_judge_json(raw: str) -> dict[str, Any] | None:
    """LLM 응답에서 JSON 객체만 추출."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    status = str(data.get("status") or "no_effect")
    if status not in ("lie_broken", "no_effect"):
        status = "no_effect"
    try:
        delta = int(data.get("stress_delta", 0))
    except (TypeError, ValueError):
        delta = 0
    return {
        "status": status,
        "stress_delta": _clamp_delta(delta),
        "reason_internal": str(data.get("reason_internal") or "")[:240],
        "judge": "llm_json",
    }


def local_judge_lie(
    *,
    suspect_id: str,
    user_input: str,
    evidence_ids: list[str] | None = None,
    prompt_vars: dict[str, Any] | None = None,
    npc_response: str = "",
) -> dict[str, Any]:
    """
    템플릿 규칙의 로컬 판정 (LLM 없이 스모크 가능).
    - 결정적 증거 핵심 토큰이 user_input에 포함
    - 그리고 해당 evidence_id를 보유(또는 질문만으로도 토큰+보유)
    → lie_broken
    """
    evidence_ids = list(evidence_ids or [])
    tokens_cfg = (_load().get("evidence_tokens") or {}).get(suspect_id) or {}
    need_ids = [str(x) for x in (tokens_cfg.get("evidence_ids") or [])]
    tokens = [str(t) for t in (tokens_cfg.get("tokens") or [])]
    q = user_input or ""

    has_token = any(t and t in q for t in tokens)
    has_ev = any(eid in evidence_ids for eid in need_ids) if need_ids else False

    # 결정적 증거 문구가 발언에 직접 언급된 경우도 인정
    decisive = str((prompt_vars or {}).get("결정적_증거") or "")
    decisive_hit = bool(decisive) and any(
        frag and frag in q for frag in ("카드", "룸살롱", "Wi-Fi", "와이파이", "슬랙", "지문", "100GB", "서버실")
    )

    if has_token and has_ev:
        return {
            "status": "lie_broken",
            "stress_delta": _clamp_delta(20),
            "reason_internal": f"{suspect_id}: 결정적 증거 보유+발언 토큰 일치",
            "judge": "gm_local",
            "prompt_preview_chars": len(
                render_judge_prompt(
                    prompt_vars=prompt_vars,
                    user_input=user_input,
                    npc_response=npc_response,
                )
            ),
        }
    if has_token and decisive_hit and has_ev:
        return {
            "status": "lie_broken",
            "stress_delta": _clamp_delta(20),
            "reason_internal": f"{suspect_id}: 모순 지적+증거 보유",
            "judge": "gm_local",
        }
    if has_token and not has_ev:
        return {
            "status": "no_effect",
            "stress_delta": _clamp_delta(5),
            "reason_internal": f"{suspect_id}: 토큰은 있으나 결정적 증거 미보유",
            "judge": "gm_local",
        }
    return {
        "status": "no_effect",
        "stress_delta": _clamp_delta(0),
        "reason_internal": f"{suspect_id}: 단순 질문 또는 무관 발언",
        "judge": "gm_local",
    }


def stress_delta_to_pressure(delta: int) -> float:
    """stress_delta(-10~30) → pressure 증분(대략 0~0.3)."""
    return max(-0.1, min(0.3, float(delta) / 100.0))


def is_lie_broken(verdict: dict[str, Any] | None) -> bool:
    return bool(verdict) and str(verdict.get("status")) == "lie_broken"

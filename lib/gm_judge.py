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


def accuse_system_prompt() -> str:
    return str(_load().get("accuse_template") or "").strip()


def render_accuse_prompt(
    *,
    accused_suspect_id: str,
    submitted_evidence_ids: list[str],
    owned_evidence_ids: list[str],
    rule_correct: bool,
    rule_errors: list[str],
) -> str:
    body = accuse_system_prompt()
    vars_ = {
        "accused_suspect_id": str(accused_suspect_id or ""),
        "submitted_evidence_ids": ", ".join(str(x) for x in submitted_evidence_ids),
        "owned_evidence_ids": ", ".join(str(x) for x in owned_evidence_ids),
        "rule_correct": "true" if rule_correct else "false",
        "rule_errors": "; ".join(rule_errors) if rule_errors else "(없음)",
    }

    class _Safe(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    return body.format_map(_Safe(vars_)).strip()


def parse_accuse_json(raw: str, *, rule_correct: bool) -> dict[str, Any] | None:
    """LLM 조합 지목 JSON — correct는 서버 룰로 강제."""
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
    summary = str(data.get("public_summary") or "").strip()
    if not summary:
        return None
    return {
        "correct": bool(rule_correct),
        "public_summary": summary[:480],
        "reason_internal": str(data.get("reason_internal") or "")[:240],
        "judge": "llm_accuse",
    }


def local_accuse_summary(*, correct: bool, errors: list[str]) -> str:
    if correct:
        return (
            "자백 엔딩: 이대리 — 공로·보너스 불만으로 중국 경쟁사 5억에 응해 "
            "라운지 Wi-Fi로 Omega 가중치 약 100GB를 유출. 미션 클리어."
        )
    if errors:
        return "조합 지목 실패: " + "; ".join(errors)
    return "조합 지목 실패: 진범·증거가 일치하지 않습니다."


def llm_judge_accuse(
    *,
    accused_suspect_id: str,
    submitted_evidence_ids: list[str],
    owned_evidence_ids: list[str],
    rule_correct: bool,
    rule_errors: list[str],
    model: str = "gpt-4o-mini",
    timeout_sec: float = 20.0,
) -> dict[str, Any] | None:
    """OpenAI로 조합 지목 판결 문장 생성. 실패 시 None → 로컬 요약."""
    prompt = render_accuse_prompt(
        accused_suspect_id=accused_suspect_id,
        submitted_evidence_ids=submitted_evidence_ids,
        owned_evidence_ids=owned_evidence_ids,
        rule_correct=rule_correct,
        rule_errors=rule_errors,
    )
    if not prompt:
        return None
    try:
        from openai import OpenAI

        client = OpenAI()
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            timeout=timeout_sec,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 JSON만 출력하는 심판입니다. 마크다운·설명 금지.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception:
        return None
    return parse_accuse_json(raw, rule_correct=rule_correct)


def enrich_accuse_verdict(
    stub: dict[str, Any],
    *,
    accused_suspect_id: str,
    owned_evidence_ids: list[str],
    agent_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    룰 스텁 판정 + (옵션) Judge LLM 공개 요약.
    correct는 항상 stub 권위. reason_internal은 서버 전용.
    """
    out = dict(stub)
    correct = bool(stub.get("correct"))
    errors = [str(e) for e in (stub.get("errors") or [])]
    submitted = [str(e) for e in (stub.get("submitted_evidence_ids") or [])]
    out["public_summary"] = local_accuse_summary(correct=correct, errors=errors)
    out["judge"] = str(stub.get("judge") or "local_stub")

    cfg = agent_cfg or {}
    judge_cfg = cfg.get("judge") if isinstance(cfg.get("judge"), dict) else {}
    enabled = bool(judge_cfg.get("accuse_llm", True))
    if not enabled:
        return out

    model = str(judge_cfg.get("model") or cfg.get("llm_model") or "gpt-4o-mini")
    timeout_sec = float(judge_cfg.get("timeout_sec") or 20)
    llm = llm_judge_accuse(
        accused_suspect_id=accused_suspect_id,
        submitted_evidence_ids=submitted,
        owned_evidence_ids=list(owned_evidence_ids),
        rule_correct=correct,
        rule_errors=errors,
        model=model,
        timeout_sec=timeout_sec,
    )
    if not llm:
        out["judge"] = "local_stub"
        return out

    out["public_summary"] = llm["public_summary"]
    out["reason_internal"] = llm.get("reason_internal") or ""
    out["judge"] = "llm_accuse"
    out["correct"] = correct  # 재확인
    return out


def public_accuse_judge(verdict: dict[str, Any] | None) -> dict[str, Any]:
    """API 응답용 — reason_internal / 내부 오류 상세 최소화."""
    v = verdict or {}
    return {
        "judge": str(v.get("judge") or "local_stub"),
        "correct": bool(v.get("correct")),
    }

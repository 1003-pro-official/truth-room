# -*- coding: utf-8 -*-
"""세션 심문 대화 메모리 — ask 턴 컨텍스트용."""

from __future__ import annotations

from typing import Any


def _clip(text: str, n: int) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1] + "…"


def build_session_memory(
    messages: list[dict[str, Any]] | None,
    *,
    suspect_id: str,
    suspect_name: str,
    evidence_briefs: list[str] | None = None,
    name_by_id: dict[str, str] | None = None,
    focus_turns: int = 6,
    other_turns: int = 2,
) -> dict[str, str]:
    """
    세션 messages를 프롬프트용 블록으로 정리.

    - focus: 현재 용의자와의 최근 심문 (대화 연속성)
    - other: 다른 용의자 요약 (오인용 방지용·짧게)
    - evidence: 확보 증거 요약
    - block: 합본 (AutoGen opening / LLM user에 주입)
    """
    sid = str(suspect_id or "")
    who = (suspect_name or "용의자").strip()
    names = name_by_id or {}
    msgs = [m for m in (messages or []) if isinstance(m, dict)]

    focus_msgs = [m for m in msgs if str(m.get("suspect_id") or "") == sid][-max(1, focus_turns) :]
    other_msgs = [m for m in msgs if str(m.get("suspect_id") or "") != sid][-max(0, other_turns) :]

    focus_lines: list[str] = []
    for m in focus_msgs:
        q = _clip(str(m.get("question") or ""), 160)
        a = _clip(str(m.get("answer") or ""), 160)
        note = _clip(str(m.get("assistant_note") or ""), 120)
        if q:
            focus_lines.append(f"탐정: {q}")
        if a:
            focus_lines.append(f"{who}: {a}")
        if note:
            focus_lines.append(f"조수: {note}")

    other_lines: list[str] = []
    for m in other_msgs:
        oid = str(m.get("suspect_id") or "")
        oname = names.get(oid) or oid or "다른 용의자"
        q = _clip(str(m.get("question") or ""), 80)
        note = _clip(str(m.get("assistant_note") or ""), 80)
        bit = f"{oname}"
        if q:
            bit += f" ← '{q}'"
        if note:
            bit += f" / 조수: {note}"
        other_lines.append(f"- {bit}")

    briefs = [b.strip() for b in (evidence_briefs or []) if str(b).strip()]
    ev_lines = [f"- {b}" for b in briefs] if briefs else ["- (아직 확보한 증거 없음)"]

    focus_dialogue = "\n".join(focus_lines) if focus_lines else "(이 용의자와는 아직 심문 기록 없음)"
    other_summary = (
        "\n".join(other_lines)
        if other_lines
        else "(다른 용의자 심문 요약 없음)"
    )
    evidence_block = "\n".join(ev_lines)

    block = (
        f"[세션 메모리]\n"
        f"현재 심문 대상: {who} ({sid or 'unknown'})\n"
        f"[확보 증거]\n{evidence_block}\n"
        f"[이 용의자와의 최근 대화]\n{focus_dialogue}\n"
        f"[다른 용의자 심문 요약 · 참고만, 현재 대상에 덮어쓰지 말 것]\n{other_summary}"
    )
    return {
        "focus_dialogue": focus_dialogue,
        "other_summary": other_summary,
        "evidence_block": evidence_block,
        "block": block,
    }

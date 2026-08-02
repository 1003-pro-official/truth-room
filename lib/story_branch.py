# -*- coding: utf-8 -*-
"""증거 수·pressure·break에 따른 스토리 분기 (슬라이드 LangGraph 층).

ask 턴·LangGraph smoke가 공유. 판정 권한이 아니라 톤·힌트만 결정한다.
"""

from __future__ import annotations

from typing import Any


def resolve_story_branch(
    *,
    suspect_id: str,
    evidence_ids: list[str] | None = None,
    pressure: dict[str, float] | None = None,
    break_count: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    상태 → 분기 노드.

    - probe: 증거 부족 · 기초 탐문
    - evidence_pressure: 핵심 증거 1장+ · 압박 시작
    - confront: 증거 2장+ 또는 중간 압박 · 대질
    - mental_edge: break≥2 또는 고압박 · 붕괴 직전
    """
    ids = [str(x) for x in (evidence_ids or [])]
    n = len(ids)
    sid = str(suspect_id or "")
    p = float((pressure or {}).get(sid, 0.0) or 0.0)
    b = int((break_count or {}).get(sid, 0) or 0)

    if b >= 2 or p >= 0.75:
        return {
            "id": "mental_edge",
            "label": "붕괴 직전",
            "tone": "말수가 줄고 목소리가 갈라짐. 인정할 건 인정하되 범행은 부인.",
            "assistant_hint": "확보한 증거로 짧게 모순만 짚고, 추가 수색 유도는 하지 마세요.",
            "clue_count": n,
            "pressure": p,
            "break_count": b,
        }
    if n >= 2 or p >= 0.45:
        return {
            "id": "confront",
            "label": "대질 강화",
            "tone": "증거가 쌓였음을 의식. 알리바이를 고집하되 흔들림이 드러남.",
            "assistant_hint": "보유 증거 [주체]만 사실로 확인하고, 다음 루트 힌트는 한 번만.",
            "clue_count": n,
            "pressure": p,
            "break_count": b,
        }
    if n >= 1:
        return {
            "id": "evidence_pressure",
            "label": "증거 압박",
            "tone": "증거가 나왔다는 뉘앙스에 경계. 알리바이는 유지.",
            "assistant_hint": "질문과 맞는 보유 증거만 짧게 확인하세요. 없는 증거는 수색 안내.",
            "clue_count": n,
            "pressure": p,
            "break_count": b,
        }
    return {
        "id": "probe",
        "label": "기초 탐문",
        "tone": "여유 있고 자신만만. 야근·휴식·화장실 알리바이를 반복.",
        "assistant_hint": "아직 핵심 증거가 부족하니 「증거 수색」 쪽을 안내하세요.",
        "clue_count": n,
        "pressure": p,
        "break_count": b,
    }

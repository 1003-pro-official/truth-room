# -*- coding: utf-8 -*-
"""lib/game_rules.py — 3-Out · 알리바이 붕괴 스텁 판정 (docs/GAME_RULES.md)"""

from __future__ import annotations

from typing import Any

# 용의자별: 붕괴에 필요한 증거 + 질문 키워드 (스텁 · 이후 GM JSON으로 교체)
ALIBI_BREAK_RULES: dict[str, dict[str, Any]] = {
    "suspect_a": {
        "evidence_ids": ["ev_card_03"],
        "keywords": ("카드", "룸살롱", "강남", "법인", "결제", "알리바이", "자리"),
    },
    "suspect_b": {
        "evidence_ids": ["ev_net_01", "ev_log_07"],
        "keywords": (
            "라운지",
            "넷플릭스",
            "Wi-Fi",
            "와이파이",
            "MAC",
            "전송",
            "100GB",
            "서버실",
            "지문",
            "알리바이",
        ),
    },
    "suspect_c": {
        "evidence_ids": ["ev_msg_12"],
        "keywords": ("화장실", "슬랙", "서버실", "DM", "마라탕", "알리바이", "목격"),
    },
}


def load_game_cfg(agent_cfg: dict[str, Any] | None) -> dict[str, Any]:
    game = (agent_cfg or {}).get("game") or {}
    return {
        "break_threshold": int(game.get("break_threshold", 3)),
        "turn_seconds": int(game.get("turn_seconds", 20)),
        "timer_enabled": bool(game.get("timer_enabled", True)),
        "max_break_per_turn": int(game.get("max_break_per_turn", 1)),
        "timeout_strike_max": int(game.get("timeout_strike_max", 3)),
        "stamina_max": int(game.get("stamina_max", 3)),
    }


CLUE_TITLES: dict[str, str] = {
    "ev_card_03": "법인카드 · 강남역 룸살롱 결제",
    "ev_msg_12": "슬랙 DM · 박신입 서버실 침입",
    "ev_net_01": "라운지 Wi-Fi · ~100GB 외부 전송",
    "ev_log_07": "출입 로그 · 김팀장 지문 (미끼)",
}

SMOKING_GUN_IDS = frozenset(CLUE_TITLES.keys())


def clue_title(evidence_id: str) -> str:
    return CLUE_TITLES.get(evidence_id, evidence_id)


def judge_combo_accuse(
    *,
    suspect_id: str,
    evidence_ids: list[str],
    culprit_id: str,
    win_evidence_ids: list[str],
    owned_evidence_ids: list[str],
) -> dict[str, Any]:
    """조합 지목 스텁 Judge. 이후 GM LLM JSON으로 교체 가능."""
    submitted = [str(e) for e in evidence_ids]
    errors: list[str] = []
    if len(submitted) != 2:
        errors.append("결정적 증거는 정확히 2장을 선택해야 합니다.")
    if len(set(submitted)) != len(submitted):
        errors.append("동일한 증거를 중복 선택할 수 없습니다.")
    for eid in submitted:
        if eid not in owned_evidence_ids:
            errors.append(f"미보유 증거: {eid}")
    win_set = set(win_evidence_ids)
    if not all(eid in win_set for eid in submitted):
        errors.append("지목용 증거는 win_condition 핵심 ID여야 합니다.")
    if "ev_net_01" not in submitted:
        errors.append("결정타 증거 ev_net_01(네트워크)이 필요합니다.")

    correct = (
        not errors
        and bool(culprit_id)
        and suspect_id == culprit_id
        and "ev_net_01" in submitted
    )
    return {
        "correct": correct,
        "errors": errors,
        "submitted_evidence_ids": submitted,
        "judge": "local_stub",
    }


def judge_alibi_broken(
    suspect_id: str,
    question: str,
    evidence_ids: list[str],
    *,
    prompt_vars: dict[str, Any] | None = None,
    npc_response: str = "",
) -> bool:
    """GM 심판 판정 — lie_broken 여부. 상세 JSON은 lib.gm_judge.local_judge_lie."""
    from lib.gm_judge import is_lie_broken, local_judge_lie

    verdict = local_judge_lie(
        suspect_id=suspect_id,
        user_input=question,
        evidence_ids=evidence_ids,
        prompt_vars=prompt_vars,
        npc_response=npc_response,
    )
    return is_lie_broken(verdict)


def apply_break_count(
    break_count: dict[str, int],
    suspect_id: str,
    *,
    is_broken: bool,
    threshold: int = 3,
    max_per_turn: int = 1,
) -> tuple[dict[str, int], bool]:
    """Returns (updated_break_count, incremented)."""
    updated = dict(break_count)
    if not is_broken or max_per_turn <= 0:
        return updated, False
    cur = int(updated.get(suspect_id, 0))
    if cur >= threshold:
        return updated, False
    updated[suspect_id] = min(threshold, cur + 1)
    return updated, True


def mental_break_suspects(break_count: dict[str, int], threshold: int = 3) -> list[str]:
    return [sid for sid, n in break_count.items() if int(n) >= threshold]


def session_status(
    suspect_id: str | None,
    broken: list[str],
    *,
    timeout_strikes: int = 0,
    timeout_strike_max: int = 3,
    ended: bool = False,
    turn_out: bool = False,
    stamina: int | None = None,
) -> str:
    if ended and stamina is not None and stamina <= 0:
        return "authority_revoked"
    if turn_out or (ended and timeout_strikes >= timeout_strike_max):
        return "turn_out"
    if suspect_id and suspect_id in broken:
        return "mental_break"
    if broken:
        return "mental_break"
    return "playing"

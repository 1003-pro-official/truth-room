# -*- coding: utf-8 -*-
"""로컬 심판 — 타 용의자 증거·확보 주장만으로 붕괴 금지."""

from __future__ import annotations

from lib.gm_judge import local_judge_lie


def test_lee_room_salon_claim_is_no_effect() -> None:
    v = local_judge_lie(
        suspect_id="suspect_b",
        user_input="이대리 내가 증거를 확보했어 확실히 말해 자네 그날 룸살롱에 갔었지?",
        evidence_ids=["ev_net_01"],
    )
    assert v["status"] == "no_effect"
    assert int(v["stress_delta"]) == 0


def test_lee_net_token_with_held_breaks() -> None:
    v = local_judge_lie(
        suspect_id="suspect_b",
        user_input="라운지 Wi-Fi로 100GB 외부 전송한 거 맞죠?",
        evidence_ids=["ev_net_01"],
    )
    assert v["status"] == "lie_broken"
    assert int(v["stress_delta"]) >= 20

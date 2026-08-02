# -*- coding: utf-8 -*-
"""조수 멘트 교정 — 보유 증거 부정·네트워크 귀속."""

from __future__ import annotations

from lib.autogen_runtime import repair_assistant_note


def test_kim_net_question_rejects_empty_inventory_lie() -> None:
    fixed = repair_assistant_note(
        "아직 확보한 증거는 없어요. 서버실 출입 로그부터 확인해 보죠.",
        question="외부에 전송한 것을 확인 했어요",
        evidence_ids=["ev_net_01"],
        suspect_id="suspect_a",
        suspect_name="김팀장",
    )
    assert "없어요" not in fixed
    assert "이대" in fixed


def test_park_net_question_keeps_lee_attribution() -> None:
    note = (
        "현재 확보한 증거는 이대리의 라운지 Wi-Fi에서의 ~100GB 외부 전송이에요. "
        "메신저 기록부터 확인해 보죠."
    )
    fixed = repair_assistant_note(
        note,
        question="박신입 네트워크 확인해보니 외부로 전송한 것을 확인했어요",
        evidence_ids=["ev_net_01"],
        suspect_id="suspect_c",
        suspect_name="박신입",
    )
    assert fixed == note


def test_kim_card_question_drops_log_pivot() -> None:
    fixed = repair_assistant_note(
        "법인카드로 강남역 룸살롱에서 850,000원 결제가 확인됐어요. "
        "서버실 출입 로그부터 확인해 보죠.",
        question="그날 룸살롱 갔었죠?",
        evidence_ids=["ev_card_03"],
        suspect_id="suspect_a",
        suspect_name="김팀장",
    )
    assert "출입 로그" not in fixed
    assert "법인카드" in fixed or "룸살롱" in fixed

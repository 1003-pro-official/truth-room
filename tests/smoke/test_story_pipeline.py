# -*- coding: utf-8 -*-
"""슬라이드 층 — 스토리 분기 · 포렌식 Function Calling 라우터."""

from __future__ import annotations

from lib.forensic_router import collect_forensic_facts
from lib.story_branch import resolve_story_branch


def test_story_branch_probe_to_pressure() -> None:
    b0 = resolve_story_branch(suspect_id="suspect_a", evidence_ids=[], pressure={"suspect_a": 0.0})
    assert b0["id"] == "probe"
    b1 = resolve_story_branch(
        suspect_id="suspect_a",
        evidence_ids=["ev_card_03"],
        pressure={"suspect_a": 0.1},
    )
    assert b1["id"] == "evidence_pressure"
    b2 = resolve_story_branch(
        suspect_id="suspect_a",
        evidence_ids=["ev_card_03", "ev_net_01"],
        pressure={"suspect_a": 0.5},
    )
    assert b2["id"] == "confront"


def test_forensic_uses_held_card() -> None:
    pack = collect_forensic_facts(
        question="그날 룸살롱 갔었죠?",
        suspect_id="suspect_a",
        suspect_name="김팀장",
        evidence_ids=["ev_card_03"],
        evidence_briefs=["법인카드 · 강남역 룸살롱 결제 [주체:김팀장]: 850,000원"],
    )
    assert pack["source"] == "held_evidence"
    assert pack["tool_calls"] == []
    assert "보유" in pack["summary"]


def test_forensic_calls_tool_when_missing() -> None:
    pack = collect_forensic_facts(
        question="그날 룸살롱 갔었죠?",
        suspect_id="suspect_a",
        suspect_name="김팀장",
        evidence_ids=[],
        evidence_briefs=[],
    )
    assert pack["source"] == "function_calling"
    assert pack["tool_calls"]
    assert pack["tool_calls"][0]["name"] == "check_card_history"


def test_witness_question_does_not_dump_net_gun() -> None:
    pack = collect_forensic_facts(
        question="구내 식당 라운지에서 있던 사람들의 증언에는 이대리는 없었다던데?",
        suspect_id="suspect_b",
        suspect_name="이대리",
        evidence_ids=["ev_net_01"],
        evidence_briefs=["라운지 Wi-Fi · ~100GB 외부 전송 [주체:이대리(MAC)]"],
    )
    assert pack["intent"] == "witness"
    assert pack["source"] == "no_data"
    assert "100GB" not in pack["summary"]
    assert "증언" in pack["summary"] or "없어요" in pack["summary"]


def test_explicit_net_question_uses_held() -> None:
    pack = collect_forensic_facts(
        question="라운지 Wi-Fi로 100GB 외부 전송한 거 맞죠?",
        suspect_id="suspect_b",
        suspect_name="이대리",
        evidence_ids=["ev_net_01"],
        evidence_briefs=["라운지 Wi-Fi · ~100GB 외부 전송 [주체:이대리(MAC)]"],
    )
    assert pack["source"] == "held_evidence"
    assert "100GB" in pack["summary"] or "Wi-Fi" in pack["summary"]


def test_alibi_where_nudge_not_gun() -> None:
    pack = collect_forensic_facts(
        question="이대리 자네 그날 어디에 있었나?",
        suspect_id="suspect_b",
        suspect_name="이대리",
        evidence_ids=["ev_net_01"],
        evidence_briefs=["라운지 Wi-Fi · ~100GB"],
    )
    assert pack["intent"] == "alibi_lee"
    assert pack["source"] == "nudge"
    assert "전송이 있었" not in pack["summary"]
    assert "약 100" not in pack["summary"]
    assert "짚어" in pack["summary"] or "질문" in pack["summary"]


def test_repair_strips_gun_on_alibi_probe() -> None:
    from lib.autogen_runtime import repair_assistant_note

    fixed = repair_assistant_note(
        "이대리, 그날 라운지에서 Wi-Fi로 약 100GB의 외부 전송이 있었어요.",
        question="이대리 자네 그날 어디에 있었나?",
        evidence_ids=["ev_net_01"],
        suspect_id="suspect_b",
        suspect_name="이대리",
    )
    assert "전송이 있었" not in fixed
    assert "약 100" not in fixed
    assert "짚어" in fixed or "네트워크" in fixed

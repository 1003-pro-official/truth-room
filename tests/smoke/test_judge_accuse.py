# -*- coding: utf-8 -*-
"""tests/smoke/test_judge_accuse.py — G10 조합 지목 Judge (룰 + 파서)."""

from __future__ import annotations

from lib.game_rules import judge_combo_accuse
from lib.gm_judge import (
    enrich_accuse_verdict,
    parse_accuse_json,
    public_accuse_judge,
    render_accuse_prompt,
)


def test_stub_correct_combo() -> None:
    v = judge_combo_accuse(
        suspect_id="suspect_b",
        evidence_ids=["ev_net_01", "ev_card_03"],
        culprit_id="suspect_b",
        win_evidence_ids=["ev_card_03", "ev_msg_12", "ev_net_01"],
        owned_evidence_ids=["ev_card_03", "ev_msg_12", "ev_net_01"],
    )
    assert v["correct"] is True
    assert v["judge"] == "local_stub"


def test_stub_rejects_without_net() -> None:
    v = judge_combo_accuse(
        suspect_id="suspect_b",
        evidence_ids=["ev_card_03", "ev_msg_12"],
        culprit_id="suspect_b",
        win_evidence_ids=["ev_card_03", "ev_msg_12", "ev_net_01"],
        owned_evidence_ids=["ev_card_03", "ev_msg_12", "ev_net_01"],
    )
    assert v["correct"] is False
    assert any("ev_net_01" in e for e in v["errors"])


def test_parse_accuse_json_forces_rule_correct() -> None:
    raw = '{"correct": false, "public_summary": "클리어", "reason_internal": "x"}'
    parsed = parse_accuse_json(raw, rule_correct=True)
    assert parsed is not None
    assert parsed["correct"] is True
    assert "클리어" in parsed["public_summary"]


def test_enrich_falls_back_without_llm() -> None:
    stub = judge_combo_accuse(
        suspect_id="suspect_a",
        evidence_ids=["ev_net_01", "ev_card_03"],
        culprit_id="suspect_b",
        win_evidence_ids=["ev_card_03", "ev_msg_12", "ev_net_01"],
        owned_evidence_ids=["ev_card_03", "ev_net_01"],
    )
    enriched = enrich_accuse_verdict(
        stub,
        accused_suspect_id="suspect_a",
        owned_evidence_ids=["ev_card_03", "ev_net_01"],
        agent_cfg={"judge": {"accuse_llm": False}},
    )
    assert enriched["correct"] is False
    assert enriched["public_summary"]
    pub = public_accuse_judge(enriched)
    assert "reason_internal" not in pub
    assert pub["correct"] is False


def test_accuse_prompt_renders() -> None:
    text = render_accuse_prompt(
        accused_suspect_id="suspect_b",
        submitted_evidence_ids=["ev_net_01", "ev_msg_12"],
        owned_evidence_ids=["ev_net_01", "ev_msg_12"],
        rule_correct=True,
        rule_errors=[],
    )
    assert "suspect_b" in text
    assert "ev_net_01" in text

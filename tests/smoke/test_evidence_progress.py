# -*- coding: utf-8 -*-
"""증거 수집 진행·책상 완료 후 헛수색 수사권 보호."""

from __future__ import annotations

from lib.game_rules import build_evidence_progress
from backend.game_engine import GameEngine


def test_build_evidence_progress_win_and_desk() -> None:
    prog = build_evidence_progress(
        ["ev_card_03", "ev_msg_12"],
        win_evidence_ids=["ev_card_03", "ev_msg_12", "ev_net_01"],
        desk_evidence_ids=["ev_card_03", "ev_msg_12", "ev_net_01", "ev_log_07"],
    )
    assert prog["win_evidence_count"] == 2
    assert prog["win_evidence_total"] == 3
    assert prog["desk_evidence_count"] == 2
    assert prog["desk_evidence_total"] == 4
    assert prog["evidence_ready_for_accuse"] is False
    assert prog["desk_evidence_complete"] is False

    done = build_evidence_progress(
        ["ev_card_03", "ev_msg_12", "ev_net_01", "ev_log_07"],
        win_evidence_ids=["ev_card_03", "ev_msg_12", "ev_net_01"],
        desk_evidence_ids=["ev_card_03", "ev_msg_12", "ev_net_01", "ev_log_07"],
    )
    assert done["evidence_ready_for_accuse"] is True
    assert done["desk_evidence_complete"] is True


def test_public_state_includes_evidence_progress() -> None:
    engine = GameEngine()
    session = engine.create_session()
    state = engine.public_state(session)
    assert state["win_evidence_total"] == 3
    assert state["desk_evidence_total"] == 4
    assert state["evidence_ready_for_accuse"] is False
    assert state["desk_evidence_complete"] is False


def test_decoy_no_stamina_when_desk_complete() -> None:
    engine = GameEngine()
    session = engine.create_session()
    for eid in ("ev_card_03", "ev_msg_12", "ev_net_01", "ev_log_07"):
        engine.search(session, "q", force_evidence_id=eid)
    stamina_before = session.stamina
    result = engine.search(session, "decoy", force_miss=True)
    assert result.get("stamina_preserved") is True
    assert result.get("desk_search_complete") is True
    assert session.stamina == stamina_before


def test_decoy_costs_stamina_when_desk_incomplete() -> None:
    engine = GameEngine()
    session = engine.create_session()
    engine.search(session, "q", force_evidence_id="ev_card_03")
    stamina_before = session.stamina
    result = engine.search(session, "decoy", force_miss=True)
    assert result.get("useless_search") is True
    assert result.get("stamina_preserved") is not True
    assert session.stamina == stamina_before - 1

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lib/langgraph_runtime.py — 공식 LangGraph StateGraph 심문 루프

TECH_SPEC §5:
  route → interrogate | retrieve_evidence | call_tool
       → update_pressure → confront → judge_ending

retrieve 목표는 smoke 내러티브상 interrogate를 선행
(route → interrogate → retrieve_evidence → call_tool → …).
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class AgentGraphState(TypedDict, total=False):
    session_id: str
    turn: int
    suspect_id: str
    user_goal: str
    messages: list
    evidence_ids: list
    pressure: dict
    break_count: dict
    last_retrieval: list
    tool_results: list
    phase: str
    clue_count: int
    ended: bool
    trace: list
    next_hint: str


RouteTarget = Literal["to_interrogate", "to_retrieve", "to_tool", "to_ending"]


def langgraph_available() -> bool:
    try:
        from langgraph.graph import StateGraph  # noqa: F401

        return True
    except ImportError:
        return False


def build_langgraph_app(
    cfg: dict[str, Any],
    *,
    personas: dict[str, Any],
    rag_cfg: dict[str, Any],
    scenario: dict[str, Any],
):
    """Compile LangGraph StateGraph. Raises ImportError if langgraph missing."""
    from langgraph.graph import END, START, StateGraph

    from agent_graph import (  # lazy: avoid circular import at module load
        AgentState,
        node_call_tool,
        node_confront,
        node_interrogate,
        node_judge_ending,
        node_retrieve_evidence,
        node_route,
        node_update_pressure,
    )

    def state_to_dict(state: AgentState) -> dict[str, Any]:
        return {
            "session_id": state.session_id,
            "turn": state.turn,
            "suspect_id": state.suspect_id,
            "user_goal": state.user_goal,
            "messages": list(state.messages),
            "evidence_ids": list(state.evidence_ids),
            "pressure": dict(state.pressure),
            "break_count": dict(state.break_count),
            "last_retrieval": list(state.last_retrieval),
            "tool_results": list(state.tool_results),
            "phase": state.phase,
            "clue_count": state.clue_count,
            "ended": state.ended,
            "trace": list(state.trace),
        }

    def dict_to_state(data: AgentGraphState) -> AgentState:
        return AgentState(
            session_id=str(data.get("session_id") or "smoke"),
            turn=int(data.get("turn") or 0),
            suspect_id=str(data.get("suspect_id") or "suspect_a"),
            user_goal=str(data.get("user_goal") or ""),
            messages=list(data.get("messages") or []),
            evidence_ids=list(data.get("evidence_ids") or []),
            pressure=dict(data.get("pressure") or {}),
            break_count=dict(data.get("break_count") or {}),
            last_retrieval=list(data.get("last_retrieval") or []),
            tool_results=list(data.get("tool_results") or []),
            phase=data.get("phase") or "interrogate",  # type: ignore[arg-type]
            clue_count=int(data.get("clue_count") or 0),
            ended=bool(data.get("ended")),
            trace=list(data.get("trace") or []),
        )

    def _route(state: AgentGraphState) -> dict[str, Any]:
        return state_to_dict(node_route(dict_to_state(state), cfg))

    def _interrogate(state: AgentGraphState) -> dict[str, Any]:
        return state_to_dict(node_interrogate(dict_to_state(state), cfg, personas))

    def _retrieve(state: AgentGraphState) -> dict[str, Any]:
        return state_to_dict(node_retrieve_evidence(dict_to_state(state), cfg, rag_cfg))

    def _tool(state: AgentGraphState) -> dict[str, Any]:
        return state_to_dict(node_call_tool(dict_to_state(state), cfg))

    def _pressure(state: AgentGraphState) -> dict[str, Any]:
        return state_to_dict(node_update_pressure(dict_to_state(state), cfg, personas))

    def _confront(state: AgentGraphState) -> dict[str, Any]:
        return state_to_dict(node_confront(dict_to_state(state), cfg, personas))

    def _judge(state: AgentGraphState) -> dict[str, Any]:
        s = node_judge_ending(dict_to_state(state), cfg, scenario)
        s.turn = 1
        return state_to_dict(s)

    def after_route(state: AgentGraphState) -> RouteTarget:
        phase = str(state.get("phase") or "interrogate")
        if phase == "ending":
            return "to_ending"
        if phase == "tool":
            return "to_tool"
        if phase == "retrieve":
            return "to_interrogate"
        return "to_interrogate"

    g: StateGraph = StateGraph(AgentGraphState)
    g.add_node("route", _route)
    g.add_node("interrogate", _interrogate)
    g.add_node("retrieve_evidence", _retrieve)
    g.add_node("call_tool", _tool)
    g.add_node("update_pressure", _pressure)
    g.add_node("confront", _confront)
    g.add_node("judge_ending", _judge)

    g.add_edge(START, "route")
    g.add_conditional_edges(
        "route",
        after_route,
        {
            "to_interrogate": "interrogate",
            "to_retrieve": "retrieve_evidence",
            "to_tool": "call_tool",
            "to_ending": "judge_ending",
        },
    )
    g.add_edge("interrogate", "retrieve_evidence")
    g.add_edge("retrieve_evidence", "call_tool")
    g.add_edge("call_tool", "update_pressure")
    g.add_edge("update_pressure", "confront")
    g.add_edge("confront", "judge_ending")
    g.add_edge("judge_ending", END)

    return g.compile()


def invoke_langgraph(
    cfg: dict[str, Any],
    *,
    personas: dict[str, Any],
    rag_cfg: dict[str, Any],
    scenario: dict[str, Any],
    initial: AgentGraphState,
) -> AgentGraphState:
    app = build_langgraph_app(cfg, personas=personas, rag_cfg=rag_cfg, scenario=scenario)
    return app.invoke(initial)  # type: ignore[return-value]

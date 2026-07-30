#!/usr/bin/env python3
"""agent_graph.py — LangGraph-style 심문 상태머신 + ReAct 툴 연쇄

실패키지 langgraph 없이도 동일 노드명으로 동작.
`--smoke` 는 알리바이 검증 1턴 완주 게이트.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lib.rag_core import get_or_build_index, retrieve  # noqa: E402
from lib.tools import call_tool  # noqa: E402

Phase = Literal["interrogate", "retrieve", "tool", "confront", "ending"]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass
class AgentState:
    session_id: str = "smoke"
    turn: int = 0
    suspect_id: str = "suspect_a"
    user_goal: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    pressure: dict[str, float] = field(default_factory=dict)
    last_retrieval: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    phase: Phase = "interrogate"
    clue_count: int = 0
    ended: bool = False
    trace: list[dict[str, Any]] = field(default_factory=list)


def _pressure_step(cfg: dict[str, Any]) -> float:
    return float(cfg.get("graph", {}).get("pressure_step", 0.15))


def node_route(state: AgentState, cfg: dict[str, Any]) -> AgentState:
    goal = state.user_goal
    if any(k in goal for k in ("알리바이", "검증", "확인", "CCTV", "출입")):
        state.phase = "retrieve"
        next_hint = "retrieve_then_tool"
    elif any(k in goal for k in ("포렌식", "노트북", "삭제")):
        state.phase = "tool"
        next_hint = "forensic"
    elif any(k in goal for k in ("지목", "자백", "엔딩")):
        state.phase = "ending"
        next_hint = "judge"
    else:
        state.phase = "interrogate"
        next_hint = "ask"
    state.trace.append({"node": "route", "phase": state.phase, "hint": next_hint})
    return state


def node_interrogate(state: AgentState, cfg: dict[str, Any], personas: dict[str, Any]) -> AgentState:
    persona = personas.get(state.suspect_id, {})
    question = state.user_goal or "그날 밤 어디에 있었습니까?"
    answer = (
        f"[{persona.get('name', state.suspect_id)}] "
        f"{persona.get('alibi', '기억이 나지 않습니다.')}"
    )
    state.messages.append(
        {"role": "suspect", "suspect_id": state.suspect_id, "question": question, "answer": answer}
    )
    state.trace.append(
        {
            "node": "interrogate",
            "suspect_id": state.suspect_id,
            "question": question,
            "answer": answer[:120],
        }
    )
    state.phase = "retrieve"
    return state


def node_retrieve_evidence(state: AgentState, cfg: dict[str, Any], rag_cfg: dict[str, Any]) -> AgentState:
    query = state.user_goal or "알리바이 출입 로그"
    if state.suspect_id == "suspect_a":
        query = "김팀장 법인카드 룸살롱"
    elif state.suspect_id == "suspect_b":
        query = "서버실 출입 지문 Wi-Fi 100GB"
    elif state.suspect_id == "suspect_c":
        query = "박신입 슬랙 서버실"

    persist = ROOT / rag_cfg.get("persist_dir", "runs/rag/index")
    index = get_or_build_index(ROOT / "data/processed/chunks.jsonl", persist / "vectors.json")
    retrieval = rag_cfg.get("retrieval", {})
    hits = retrieve(
        index,
        query,
        mode="advanced",
        top_k=int(retrieval.get("top_k", 5)),
        rrf_k=int(retrieval.get("rrf_k", 60)),
        rerank=bool(retrieval.get("rerank", True)),
    )
    state.last_retrieval = [
        {
            "evidence_id": h.get("evidence_id"),
            "source_type": h.get("source_type"),
            "score": h.get("score"),
            "snippet": str(h.get("text", ""))[:160],
        }
        for h in hits
    ]
    for h in hits:
        eid = h.get("evidence_id")
        if eid and eid not in state.evidence_ids:
            state.evidence_ids.append(str(eid))
            state.clue_count += 1
    state.trace.append(
        {
            "node": "retrieve_evidence",
            "query": query,
            "n_hits": len(hits),
            "evidence_ids": list(state.evidence_ids),
        }
    )
    state.phase = "tool"
    return state


def node_call_tool(state: AgentState, cfg: dict[str, Any]) -> AgentState:
    tools_cfg = cfg.get("tools", {})
    results: list[dict[str, Any]] = []

    # ReAct: alibi check → CCTV then (optional) forensic
    if tools_cfg.get("request_cctv_log", True):
        loc = "lounge" if state.suspect_id == "suspect_b" else "office_floor3"
        if "CCTV" in state.user_goal or "알리바이" in state.user_goal or "검증" in state.user_goal:
            if state.suspect_id == "suspect_a":
                loc = "lobby"
            results.append(call_tool("request_cctv_log", {"location": loc}))

    if tools_cfg.get("run_forensic", True) and (
        "포렌식" in state.user_goal or state.suspect_id == "suspect_b" and "검증" in state.user_goal
    ):
        device = {
            "suspect_a": "kim_pc",
            "suspect_b": "lee_laptop",
            "suspect_c": "park_phone",
        }.get(state.suspect_id, "lee_laptop")
        results.append(call_tool("run_forensic", {"device": device}))

    if not results and tools_cfg.get("request_cctv_log", True):
        results.append(call_tool("request_cctv_log", {"location": "lounge"}))

    state.tool_results.extend(results)
    state.trace.append({"node": "call_tool", "n_tools": len(results), "tools": [r.get("tool") for r in results]})
    state.phase = "confront"
    return state


def node_update_pressure(state: AgentState, cfg: dict[str, Any], personas: dict[str, Any]) -> AgentState:
    step = _pressure_step(cfg)
    sid = state.suspect_id
    cur = float(state.pressure.get(sid, 0.0))
    gain = step * max(1, state.clue_count)
    if any(h.get("evidence_id") for h in state.last_retrieval):
        gain += step
    new_p = min(1.0, cur + gain)
    state.pressure[sid] = new_p
    threshold = float(personas.get(sid, {}).get("leak_threshold", 0.9))
    state.trace.append(
        {
            "node": "update_pressure",
            "suspect_id": sid,
            "pressure": new_p,
            "leak_threshold": threshold,
            "stress_exceeded": new_p >= threshold,
        }
    )
    return state


def node_confront(state: AgentState, cfg: dict[str, Any], personas: dict[str, Any]) -> AgentState:
    persona = personas.get(state.suspect_id, {})
    eids = state.evidence_ids
    line = f"{persona.get('name', state.suspect_id)}에게 증거 {eids or ['(없음)']} 제시."
    if "ev_net_01" in eids and state.suspect_id == "suspect_b":
        line += " 결정적 네트워크 로그로 압박."
    state.messages.append({"role": "gm", "text": line})
    state.trace.append({"node": "confront", "ok": True, "line": line})
    state.phase = "ending"
    return state


def node_judge_ending(state: AgentState, cfg: dict[str, Any], scenario: dict[str, Any]) -> AgentState:
    culprit = str(scenario.get("culprit_id", ""))
    min_eids = list((scenario.get("win_condition") or {}).get("min_evidence_ids") or [])
    has_min = all(e in state.evidence_ids for e in min_eids) if min_eids else False
    # smoke turn does not force ending clear
    state.ended = False
    state.trace.append(
        {
            "node": "judge_ending",
            "ended": state.ended,
            "culprit_id_hidden": True,
            "evidence_progress": f"{len(state.evidence_ids)}/{len(min_eids) if min_eids else 0}",
            "ready_to_accuse": has_min and state.pressure.get(culprit, 0) >= 0.7,
        }
    )
    return state


def run_graph(
    cfg: dict[str, Any],
    *,
    user_goal: str,
    suspect_id: str = "suspect_a",
) -> dict[str, Any]:
    scenario_path = ROOT / cfg.get("scenario", "data/scenarios/case_01.yaml")
    personas_dir = ROOT / cfg.get("personas_dir", "data/personas")
    scenario = load_yaml(scenario_path) if scenario_path.exists() else {}
    personas: dict[str, Any] = {}
    if personas_dir.exists():
        for path in sorted(personas_dir.glob("suspect_*.yaml")):
            p = load_yaml(path)
            personas[str(p.get("id") or path.stem)] = p

    rag_cfg_path = ROOT / "configs" / "rag.yaml"
    rag_cfg = load_yaml(rag_cfg_path) if rag_cfg_path.exists() else {}

    suspects = list(scenario.get("suspects") or personas.keys())
    state = AgentState(
        suspect_id=suspect_id,
        user_goal=user_goal,
        pressure={s: 0.0 for s in suspects},
    )

    state = node_route(state, cfg)
    if state.phase == "interrogate":
        state = node_interrogate(state, cfg, personas)
    if state.phase in {"retrieve", "tool"} or state.last_retrieval == []:
        # ReAct chain for alibi verification
        state = node_interrogate(state, cfg, personas) if not state.messages else state
        state = node_retrieve_evidence(state, cfg, rag_cfg)
        state = node_call_tool(state, cfg)
    state = node_update_pressure(state, cfg, personas)
    state = node_confront(state, cfg, personas)
    state = node_judge_ending(state, cfg, scenario)
    state.turn = 1

    return {
        "status": "ok",
        "case_id": scenario.get("case_id"),
        "gm_tone": bool(cfg.get("gm_system_prompt")),
        "state": {
            "session_id": state.session_id,
            "turn": state.turn,
            "suspect_id": state.suspect_id,
            "evidence_ids": state.evidence_ids,
            "pressure": state.pressure,
            "clue_count": state.clue_count,
            "phase": state.phase,
            "ended": state.ended,
            "last_retrieval": state.last_retrieval,
            "tool_results": state.tool_results,
        },
        "trace": state.trace,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": "pure-Python LangGraph-compatible nodes · ReAct retrieve+tool",
    }


def smoke_run(cfg: dict[str, Any]) -> dict[str, Any]:
    return run_graph(
        cfg,
        user_goal="김팀장 알리바이가 맞는지 검증해줘. CCTV도 확인해.",
        suspect_id="suspect_a",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/agent.yaml")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--goal", default="")
    parser.add_argument("--suspect", default="suspect_a")
    args = parser.parse_args()

    cfg_path = ROOT / args.config
    if not cfg_path.exists():
        cfg_path = ROOT / "configs" / "agent.yaml.example"
    cfg = load_yaml(cfg_path)

    if args.smoke:
        result = smoke_run(cfg)
    elif args.goal:
        result = run_graph(cfg, user_goal=args.goal, suspect_id=args.suspect)
    else:
        raise SystemExit("사용법: python3 agent_graph.py --smoke | --goal '...' [--suspect suspect_b]")

    out_dir = ROOT / "runs" / "agent"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / ("smoke.json" if args.smoke else "last_run.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

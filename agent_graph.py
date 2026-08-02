#!/usr/bin/env python3
"""agent_graph.py — LangGraph 심문 상태머신 + ReAct 툴 연쇄

본선 그래프: 공식 `langgraph` StateGraph (`lib/langgraph_runtime.py`).
langgraph 미설치 시에만 순수 Python 순차 폴백.
`--smoke` 는 알리바이 검증 1턴 완주 게이트.

노드: route → interrogate → retrieve_evidence → call_tool
    → update_pressure → confront → judge_ending
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

from lib.game_rules import apply_break_count, load_game_cfg, mental_break_suspects  # noqa: E402
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
    break_count: dict[str, int] = field(default_factory=dict)
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
    from lib.persona_prompt import render_suspect_prompt

    persona = personas.get(state.suspect_id, {})
    question = state.user_goal or "그날 밤 어디에 있었습니까?"
    pressure = float((state.pressure or {}).get(state.suspect_id, 0.0))
    prompt = render_suspect_prompt(persona, pressure=pressure)
    vars_ = persona.get("prompt_vars") or {}
    example = str(vars_.get("예시_대사") or "").strip()
    alibi = persona.get("alibi", "기억이 나지 않습니다.")
    if example:
        answer = f"[{persona.get('name', state.suspect_id)}] {example} — {alibi}"
    else:
        answer = f"[{persona.get('name', state.suspect_id)}] {alibi}"
    state.messages.append(
        {"role": "suspect", "suspect_id": state.suspect_id, "question": question, "answer": answer}
    )
    state.trace.append(
        {
            "node": "interrogate",
            "suspect_id": state.suspect_id,
            "question": question,
            "answer": answer[:120],
            "prompt_chars": len(prompt),
            "stress_level": int(round(pressure * 100)),
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
        expand=bool(retrieval.get("expand", True)),
        source_routing=str(retrieval.get("source_routing") or "off"),
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
    from lib.assistant_prompt import assistant_system_prompt

    tools_cfg = cfg.get("tools", {})
    results: list[dict[str, Any]] = []
    goal = state.user_goal or ""
    name_map = {
        "suspect_a": "김팀장",
        "suspect_b": "이대리",
        "suspect_c": "박신입",
    }
    suspect_name = name_map.get(state.suspect_id, state.suspect_id)

    if tools_cfg.get("check_card_history", True) and any(
        k in goal for k in ("카드", "결제", "룸살롱", "법인")
    ):
        results.append(call_tool("check_card_history", {"suspect_name": suspect_name}))

    if tools_cfg.get("search_messenger", True) and any(
        k in goal for k in ("메신저", "슬랙", "DM", "메시지", "채팅")
    ):
        results.append(
            call_tool(
                "search_messenger",
                {"suspect_name": suspect_name, "keyword": "서버"},
            )
        )

    if tools_cfg.get("run_forensic", True) and (
        "포렌식" in goal or ("검증" in goal and state.suspect_id == "suspect_b")
    ):
        device = {
            "suspect_a": "kim_pc",
            "suspect_b": "lee_laptop",
            "suspect_c": "park_phone",
        }.get(state.suspect_id, "lee_laptop")
        results.append(
            call_tool(
                "run_forensic",
                {"device": device, "suspect_name": suspect_name},
            )
        )

    if tools_cfg.get("request_cctv_log", True) and any(
        k in goal for k in ("CCTV", "시시티비", "알리바이", "카메라")
    ):
        loc = "lounge" if state.suspect_id == "suspect_b" else "office_floor3"
        if state.suspect_id == "suspect_a":
            loc = "lobby"
        results.append(call_tool("request_cctv_log", {"location": loc}))

    if not results and tools_cfg.get("check_card_history", True) and state.suspect_id == "suspect_a":
        results.append(call_tool("check_card_history", {"suspect_name": "김팀장"}))
    elif not results and tools_cfg.get("request_cctv_log", True):
        results.append(call_tool("request_cctv_log", {"location": "lounge"}))

    state.tool_results.extend(results)
    state.trace.append(
        {
            "node": "call_tool",
            "n_tools": len(results),
            "tools": [r.get("tool") for r in results],
            "assistant_prompt": bool(assistant_system_prompt() or cfg.get("gm_system_prompt")),
        }
    )
    state.phase = "confront"
    return state


def node_update_pressure(state: AgentState, cfg: dict[str, Any], personas: dict[str, Any]) -> AgentState:
    from lib.gm_judge import is_lie_broken, local_judge_lie, stress_delta_to_pressure

    step = _pressure_step(cfg)
    sid = state.suspect_id
    cur = float(state.pressure.get(sid, 0.0))
    gain = step * max(1, state.clue_count)
    if any(h.get("evidence_id") for h in state.last_retrieval):
        gain += step
    new_p = min(1.0, cur + gain)
    state.pressure[sid] = new_p

    game = load_game_cfg(cfg)
    persona = personas.get(sid) or {}
    vars_ = persona.get("prompt_vars") if isinstance(persona.get("prompt_vars"), dict) else {}
    npc = ""
    if state.messages:
        last = state.messages[-1]
        npc = str(last.get("answer") or last.get("text") or "")
    verdict = local_judge_lie(
        suspect_id=sid,
        user_input=state.user_goal,
        evidence_ids=state.evidence_ids,
        prompt_vars=vars_,
        npc_response=npc,
    )
    is_broken = is_lie_broken(verdict)
    state.break_count, incremented = apply_break_count(
        state.break_count or {sid: 0},
        sid,
        is_broken=is_broken,
        threshold=int(game["break_threshold"]),
        max_per_turn=int(game["max_break_per_turn"]),
    )
    state.pressure[sid] = min(
        1.0,
        state.pressure[sid] + stress_delta_to_pressure(int(verdict.get("stress_delta") or 0)),
    )
    if incremented:
        state.pressure[sid] = min(1.0, state.pressure[sid] + step)

    threshold = float(personas.get(sid, {}).get("leak_threshold", 0.9))
    broken = mental_break_suspects(state.break_count, int(game["break_threshold"]))
    state.trace.append(
        {
            "node": "update_pressure",
            "suspect_id": sid,
            "pressure": state.pressure[sid],
            "break_count": int(state.break_count.get(sid, 0)),
            "is_alibi_broken": bool(incremented),
            "gm_status": verdict.get("status"),
            "stress_delta": verdict.get("stress_delta"),
            "mental_break": sid in broken,
            "leak_threshold": threshold,
            "stress_exceeded": state.pressure[sid] >= threshold,
        }
    )
    return state


def node_confront(state: AgentState, cfg: dict[str, Any], personas: dict[str, Any]) -> AgentState:
    from lib.story_branch import resolve_story_branch

    persona = personas.get(state.suspect_id, {})
    eids = state.evidence_ids
    branch = resolve_story_branch(
        suspect_id=state.suspect_id,
        evidence_ids=list(eids),
        pressure=dict(state.pressure),
        break_count=dict(state.break_count),
    )
    line = (
        f"{persona.get('name', state.suspect_id)}에게 증거 {eids or ['(없음)']} 제시. "
        f"[{branch.get('label')}] {branch.get('assistant_hint')}"
    )
    if "ev_net_01" in eids and state.suspect_id == "suspect_b":
        line += " 결정적 네트워크 로그로 압박."
    state.messages.append({"role": "gm", "text": line})
    state.trace.append(
        {
            "node": "confront",
            "ok": True,
            "line": line,
            "story_branch": branch.get("id"),
        }
    )
    state.phase = "ending"
    return state


def node_judge_ending(state: AgentState, cfg: dict[str, Any], scenario: dict[str, Any]) -> AgentState:
    culprit = str(scenario.get("culprit_id", ""))
    min_eids = list((scenario.get("win_condition") or {}).get("min_evidence_ids") or [])
    has_min = all(e in state.evidence_ids for e in min_eids) if min_eids else False
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


def _load_context(cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
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
    return scenario, personas, rag_cfg


def _run_graph_fallback(
    cfg: dict[str, Any],
    *,
    user_goal: str,
    suspect_id: str,
    scenario: dict[str, Any],
    personas: dict[str, Any],
    rag_cfg: dict[str, Any],
) -> dict[str, Any]:
    """langgraph 미설치 시 동일 노드 순차 실행."""
    suspects = list(scenario.get("suspects") or personas.keys())
    suspect_ids: list[str] = []
    for s in suspects:
        if isinstance(s, dict):
            suspect_ids.append(str(s.get("id") or ""))
        else:
            suspect_ids.append(str(s))
    suspect_ids = [s for s in suspect_ids if s] or list(personas.keys())

    state = AgentState(
        suspect_id=suspect_id,
        user_goal=user_goal,
        pressure={s: 0.0 for s in suspect_ids},
        break_count={s: 0 for s in suspect_ids},
    )
    state = node_route(state, cfg)
    if state.phase == "ending":
        state = node_judge_ending(state, cfg, scenario)
    elif state.phase == "tool":
        state = node_call_tool(state, cfg)
        state = node_update_pressure(state, cfg, personas)
        state = node_confront(state, cfg, personas)
        state = node_judge_ending(state, cfg, scenario)
    else:
        state = node_interrogate(state, cfg, personas)
        state = node_retrieve_evidence(state, cfg, rag_cfg)
        state = node_call_tool(state, cfg)
        state = node_update_pressure(state, cfg, personas)
        state = node_confront(state, cfg, personas)
        state = node_judge_ending(state, cfg, scenario)
    state.turn = 1
    return _result_payload(cfg, scenario, state, backend="pure_python_fallback")


def _result_payload(
    cfg: dict[str, Any],
    scenario: dict[str, Any],
    state: AgentState,
    *,
    backend: str,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "case_id": scenario.get("case_id"),
        "gm_tone": bool(cfg.get("gm_system_prompt")),
        "backend": backend,
        "state": {
            "session_id": state.session_id,
            "turn": state.turn,
            "suspect_id": state.suspect_id,
            "evidence_ids": state.evidence_ids,
            "pressure": state.pressure,
            "break_count": state.break_count,
            "mental_break_suspects": mental_break_suspects(
                state.break_count, int(load_game_cfg(cfg)["break_threshold"])
            ),
            "clue_count": state.clue_count,
            "phase": state.phase,
            "ended": state.ended,
            "last_retrieval": state.last_retrieval,
            "tool_results": state.tool_results,
        },
        "trace": state.trace,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "LangGraph StateGraph · ReAct retrieve+tool"
            if backend.startswith("langgraph")
            else "pure-Python fallback · same nodes"
        ),
    }


def run_graph(
    cfg: dict[str, Any],
    *,
    user_goal: str,
    suspect_id: str = "suspect_a",
) -> dict[str, Any]:
    scenario, personas, rag_cfg = _load_context(cfg)
    suspects = list(scenario.get("suspects") or personas.keys())
    suspect_ids: list[str] = []
    for s in suspects:
        if isinstance(s, dict):
            suspect_ids.append(str(s.get("id") or ""))
        else:
            suspect_ids.append(str(s))
    suspect_ids = [s for s in suspect_ids if s] or list(personas.keys())

    use_lg = bool((cfg.get("langgraph") or {}).get("enabled", True))
    from lib.langgraph_runtime import invoke_langgraph, langgraph_available

    if use_lg and langgraph_available():
        initial = {
            "session_id": "smoke",
            "turn": 0,
            "suspect_id": suspect_id,
            "user_goal": user_goal,
            "messages": [],
            "evidence_ids": [],
            "pressure": {s: 0.0 for s in suspect_ids},
            "break_count": {s: 0 for s in suspect_ids},
            "last_retrieval": [],
            "tool_results": [],
            "phase": "interrogate",
            "clue_count": 0,
            "ended": False,
            "trace": [],
        }
        final = invoke_langgraph(
            cfg,
            personas=personas,
            rag_cfg=rag_cfg,
            scenario=scenario,
            initial=initial,  # type: ignore[arg-type]
        )
        state = AgentState(
            session_id=str(final.get("session_id") or "smoke"),
            turn=int(final.get("turn") or 1),
            suspect_id=str(final.get("suspect_id") or suspect_id),
            user_goal=str(final.get("user_goal") or user_goal),
            messages=list(final.get("messages") or []),
            evidence_ids=list(final.get("evidence_ids") or []),
            pressure=dict(final.get("pressure") or {}),
            break_count=dict(final.get("break_count") or {}),
            last_retrieval=list(final.get("last_retrieval") or []),
            tool_results=list(final.get("tool_results") or []),
            phase=final.get("phase") or "ending",  # type: ignore[arg-type]
            clue_count=int(final.get("clue_count") or 0),
            ended=bool(final.get("ended")),
            trace=list(final.get("trace") or []),
        )
        if state.turn < 1:
            state.turn = 1
        return _result_payload(cfg, scenario, state, backend="langgraph")

    return _run_graph_fallback(
        cfg,
        user_goal=user_goal,
        suspect_id=suspect_id,
        scenario=scenario,
        personas=personas,
        rag_cfg=rag_cfg,
    )


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

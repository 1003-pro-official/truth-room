#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/autogen_experiment.py — AutoGen GroupChat 단독 스모크 (레거시 EXP)

본선 ask 경로는 `lib/autogen_runtime.py` + `backend/game_engine.ask`.
검증 권장: `python3 scripts/smoke_autogen_ask.py`

  pip install 'pyautogen>=0.2.0,<0.3'
  python3 scripts/autogen_experiment.py --smoke
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from lib.persona_prompt import render_suspect_prompt  # noqa: E402


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _llm_config(model: str) -> dict[str, Any]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY 필요")
    return {
        "config_list": [{"model": model, "api_key": key}],
        "temperature": 0.2,
        "timeout": 60,
    }


def run_smoke(*, model: str, suspect_id: str, max_round: int) -> dict[str, Any]:
    try:
        from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent
    except ImportError as exc:
        raise SystemExit(
            "pyautogen 미설치 — pip install 'pyautogen>=0.2.0,<0.3'\n" + str(exc)
        ) from exc

    cfg = load_yaml(ROOT / "configs" / "agent.yaml")
    persona = load_yaml(ROOT / "data" / "personas" / f"{suspect_id}.yaml")
    suspect_sys = render_suspect_prompt(persona, pressure=0.35)
    assistant_sys = str(cfg.get("gm_system_prompt") or "").strip()
    judge_sys = (
        "당신은 심판 AI입니다. 사용자와 잡담하지 마세요. "
        "마지막에 JSON 한 줄만 출력: "
        '{"status":"lie_broken"|"no_effect","reason_internal":"..."}. '
        "culprit_id나 진범 이름을 쓰지 마세요."
    )

    llm = _llm_config(model)

    detective = UserProxyAgent(
        name="Detective",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=0,
        code_execution_config=False,
        system_message="외부 디지털 포렌식 감사관. 짧게 질문만 한다.",
    )
    suspect = AssistantAgent(
        name="Suspect",
        system_message=suspect_sys,
        llm_config=llm,
    )
    assistant = AssistantAgent(
        name="ForensicAssistant",
        system_message=assistant_sys
        or "포렌식 조수. 사실만 짧게. 진범을 단정하지 말 것.",
        llm_config=llm,
    )
    judge = AssistantAgent(
        name="Judge",
        system_message=judge_sys,
        llm_config=llm,
    )

    group = GroupChat(
        agents=[detective, suspect, assistant, judge],
        messages=[],
        max_round=max_round,
        speaker_selection_method="round_robin",
    )
    manager = GroupChatManager(groupchat=group, llm_config=llm)

    opening = (
        f"{persona.get('name', suspect_id)}에게 묻는다: "
        "그날 밤 어디에 있었습니까? "
        "조수는 관련 단서 힌트만 짧게, 심판은 마지막에 JSON만."
    )
    chat_result = detective.initiate_chat(manager, message=opening, clear_history=True)

    messages: list[dict[str, Any]] = []
    # GroupChat history
    for m in group.messages:
        messages.append(
            {
                "role": m.get("name") or m.get("role"),
                "content": str(m.get("content") or "")[:500],
            }
        )

    # Fallback: chat_result.chat_history
    if not messages and chat_result is not None:
        hist = getattr(chat_result, "chat_history", None) or []
        for m in hist:
            messages.append(
                {
                    "role": m.get("name") or m.get("role"),
                    "content": str(m.get("content") or "")[:500],
                }
            )

    leaked_culprit = any(
        ("진범" in (m.get("content") or "") and "이대리" in (m.get("content") or ""))
        or ("culprit_id" in (m.get("content") or ""))
        for m in messages
    )

    return {
        "status": "ok",
        "backend": "pyautogen_groupchat",
        "model": model,
        "suspect_id": suspect_id,
        "max_round": max_round,
        "n_messages": len(messages),
        "messages": messages,
        "culprit_leak_detected": leaked_culprit,
        "note": "선택 실험 · 본선은 agent_graph.py",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoGen EXP smoke (optional)")
    parser.add_argument("--smoke", action="store_true", help="GroupChat 1세션 스모크")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--suspect", default="suspect_a")
    parser.add_argument("--max-round", type=int, default=4)
    args = parser.parse_args()
    if not args.smoke:
        parser.print_help()
        raise SystemExit(2)

    result = run_smoke(
        model=args.model, suspect_id=args.suspect, max_round=args.max_round
    )
    out_dir = ROOT / "runs" / "agent"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "autogen_smoke.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[wrote] {out}")


if __name__ == "__main__":
    main()

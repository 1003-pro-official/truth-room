# -*- coding: utf-8 -*-
"""lib/autogen_runtime.py — 본선 AutoGen 멀티에이전트 턴 (안정 모드)

고정 화자 순서 · max_round · timeout · culprit 필터 · 실패 시 예외.
발표 스택: 용의자 AI · 포렌식 조수 AI · 심판(GM) AI 협업.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

_JSON_RE = re.compile(r"\{[^{}]*\"status\"[^{}]*\}")


def autogen_available() -> bool:
    try:
        import autogen  # noqa: F401

        return True
    except ImportError:
        return False


def _llm_config(model: str, temperature: float, timeout: int) -> dict[str, Any]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY missing")
    return {
        "config_list": [{"model": model, "api_key": key}],
        "temperature": float(temperature),
        "timeout": int(timeout),
    }


def _parse_judge(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = _JSON_RE.search(raw)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"status": "no_effect", "reason_internal": "parse_fail"}
    return {"status": "no_effect", "reason_internal": "no_json"}


def _strip_culprit_leak(text: str) -> str:
    """클라 노출 방지 — 진범 단정 문구 완화."""
    t = text or ""
    for bad in ("culprit_id", "진범은 이대리", "범인은 이대리"):
        t = t.replace(bad, "[편집됨]")
    return t


def _extract_suspect_utterance(text: str) -> str:
    """페르소나가 JSON으로 답해도 UI에는 대사만."""
    raw = (text or "").strip()
    if not raw:
        return ""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict) and obj.get("response"):
            return str(obj["response"]).strip()
    except json.JSONDecodeError:
        pass
    # trailing JSON blob after prose
    m = re.search(r"\{[^{}]*\"response\"\s*:\s*\"([^\"]+)\"[^{}]*\}\s*$", raw, re.DOTALL)
    if m:
        prose = raw[: m.start()].strip()
        return prose or m.group(1).strip()
    # drop inline JSON object at end if present
    m2 = re.search(r"\n\s*\{[\s\S]*\}\s*$", raw)
    if m2 and "response" in m2.group(0):
        return raw[: m2.start()].strip() or raw
    return raw


def run_interrogation_turn(
    *,
    question: str,
    suspect_system: str,
    assistant_system: str,
    judge_system: str | None = None,
    evidence_ids: list[str] | None = None,
    model: str = "gpt-4o-mini",
    max_round: int = 4,
    temperature: float = 0.2,
    timeout_sec: int = 45,
) -> dict[str, Any]:
    """
    Detective → Suspect → ForensicAssistant → Judge (round_robin).
    반환: answer(용의자), transcript, judge verdict.
    """
    from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent

    t0 = time.time()
    ev = ", ".join(evidence_ids or []) or "(없음)"
    judge_sys = judge_system or (
        "당신은 심판 AI입니다. 잡담 금지. "
        '마지막 발화는 JSON만: {"status":"lie_broken"|"no_effect","stress_delta":0,"reason_internal":"..."}. '
        "culprit_id·진범 이름 금지."
    )
    assist = (assistant_system or "").strip()
    assist += (
        f"\n\n[세션 보유 증거] {ev}\n"
        "증거가 있으면 한 줄로 사실만 상기시키세요. "
        "없으면 '추가 수색이 필요합니다.'만. 진범을 단정하지 마세요."
    )

    llm = _llm_config(model, temperature, timeout_sec)

    detective = UserProxyAgent(
        name="Detective",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=0,
        code_execution_config=False,
        system_message="외부 디지털 포렌식 감사관. 질문만 전달한다.",
    )
    suspect = AssistantAgent(
        name="Suspect",
        system_message=(
            suspect_system
            + "\n\n[출력] 한국어 대사만. JSON·코드블록·메타 태그 금지."
        ),
        llm_config=llm,
    )
    forensic = AssistantAgent(
        name="ForensicAssistant",
        system_message=assist,
        llm_config=llm,
    )
    judge = AssistantAgent(
        name="Judge",
        system_message=judge_sys,
        llm_config=llm,
    )

    group = GroupChat(
        agents=[detective, suspect, forensic, judge],
        messages=[],
        max_round=max(3, int(max_round)),
        speaker_selection_method="round_robin",
    )
    manager = GroupChatManager(groupchat=group, llm_config=llm)

    opening = (
        f"감사관 질문: {question}\n"
        "순서: 용의자 답변 → 조수 사실 한 줄 → 심판 JSON."
    )
    detective.initiate_chat(manager, message=opening, clear_history=True)

    transcript: list[dict[str, str]] = []
    for m in group.messages:
        role = str(m.get("name") or m.get("role") or "")
        content = _strip_culprit_leak(str(m.get("content") or ""))
        if content:
            transcript.append({"role": role, "content": content[:800]})

    suspect_answer = ""
    judge_raw = ""
    assist_line = ""
    for m in transcript:
        if m["role"] == "Suspect" and not suspect_answer:
            suspect_answer = _extract_suspect_utterance(m["content"])
            m["content"] = suspect_answer
        if m["role"] == "ForensicAssistant":
            assist_line = m["content"]
        if m["role"] == "Judge":
            judge_raw = m["content"]

    verdict = _parse_judge(judge_raw)
    status = str(verdict.get("status") or "no_effect")
    if status not in ("lie_broken", "no_effect"):
        status = "no_effect"
        verdict["status"] = status

    elapsed = round(time.time() - t0, 3)
    if not suspect_answer:
        raise RuntimeError("AutoGen: empty suspect answer")

    return {
        "backend": "autogen_groupchat",
        "answer": suspect_answer,
        "assistant_note": assist_line,
        "transcript": transcript,
        "gm_verdict": {
            "status": status,
            "stress_delta": int(verdict.get("stress_delta") or 0),
            "judge": "autogen",
        },
        "elapsed_sec": elapsed,
        "n_messages": len(transcript),
    }

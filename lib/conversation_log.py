# -*- coding: utf-8 -*-
"""심문 ask 턴 대화 로그 — FT 말투 후보 수집용 (룰/판정 권한 없음).

기본 OFF. configs/agent.yaml conversation_log.enabled=true 일 때만 append.
culprit_id · secrets · 내부 디버그는 기록하지 않는다.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger("truth_room.conversation_log")

ROOT = Path(__file__).resolve().parents[1]
_LEAK_RE = re.compile(
    r"culprit_id|진범은\s*이대리|범인은\s*이대리|secrets?",
    re.IGNORECASE,
)


def _clip(text: str, n: int = 800) -> str:
    t = (text or "").strip()
    if _LEAK_RE.search(t):
        t = _LEAK_RE.sub("[편집됨]", t)
    return t if len(t) <= n else t[: n - 1] + "…"


def log_config(agent_cfg: dict[str, Any] | None) -> dict[str, Any]:
    raw = (agent_cfg or {}).get("conversation_log")
    cfg = raw if isinstance(raw, dict) else {}
    # 실서버: yaml true 또는 환경변수 CONVERSATION_LOG=1
    env_on = str(os.environ.get("CONVERSATION_LOG") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    enabled = bool(cfg.get("enabled", False)) or env_on
    path = str(cfg.get("path") or "runs/conversation_log/ask_turns.jsonl")
    return {"enabled": enabled, "path": path}


def append_ask_turn(
    agent_cfg: dict[str, Any] | None,
    *,
    session_id: str,
    case_id: str,
    suspect_id: str,
    suspect_name: str,
    question: str,
    answer: str,
    assistant_note: str = "",
    evidence_ids: list[str] | None = None,
    is_alibi_broken: bool = False,
    break_count: int = 0,
    gm_status: str = "",
    source: str = "ask",
) -> bool:
    """성공한 ask 턴 1줄을 JSONL에 append. 비활성이면 False."""
    cfg = log_config(agent_cfg)
    if not cfg["enabled"]:
        return False
    path = Path(cfg["path"])
    if not path.is_absolute():
        path = ROOT / path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "session_id": str(session_id),
            "case_id": str(case_id),
            "suspect_id": str(suspect_id),
            "suspect_name": _clip(suspect_name, 40),
            "question": _clip(question, 500),
            "answer": _clip(answer, 800),
            "assistant_note": _clip(assistant_note, 400),
            "evidence_ids": [str(x) for x in (evidence_ids or [])],
            "is_alibi_broken": bool(is_alibi_broken),
            "break_count": int(break_count),
            "gm_status": str(gm_status or "")[:40],
            # 학습 용도 힌트 — 룰 재현용이 아님
            "ft_candidate": "persona_speech",
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except Exception as exc:  # noqa: BLE001 — 로깅 실패가 ask를 깨면 안 됨
        _log.warning("conversation_log append 실패: %s", exc)
        return False

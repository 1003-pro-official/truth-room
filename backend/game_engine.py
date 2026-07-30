"""
backend/game_engine.py — 세션 · 심문 · RAG 검색 · Function Calling
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.rag_core import get_or_build_index, retrieve  # noqa: E402
from lib.tools import call_tool  # noqa: E402

DEFAULT_API_CONFIG = ROOT / "configs" / "api.yaml"
SCENARIO_PATH = ROOT / "data" / "scenarios" / "case_01.yaml"
PERSONA_DIR = ROOT / "data" / "personas"
RAG_CONFIG = ROOT / "configs" / "rag.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML must be a mapping: {path}")
    return data


def load_api_config(path: Path = DEFAULT_API_CONFIG) -> dict[str, Any]:
    if not path.exists():
        return {"cors_origins": ["http://localhost:8501"], "server": {"port": 8000}}
    return load_yaml(path)


@dataclass
class Session:
    session_id: str
    case_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    pressure: dict[str, float] = field(default_factory=dict)
    tool_log: list[dict[str, Any]] = field(default_factory=list)
    accused: str | None = None
    ended: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_FALLBACK_CATALOG = [
    {
        "evidence_id": "ev_card_03",
        "source_type": "corporate_card",
        "snippet": "23:30 김팀장 · 강남역 룸살롱 · 850,000원",
    },
    {
        "evidence_id": "ev_msg_12",
        "source_type": "messenger",
        "snippet": "박신입 DM 23:20: 팀장 몰래 서버실 들어왔어... 누군가 또 들어온 것 같기도 하고 ㄷㄷ",
    },
    {
        "evidence_id": "ev_log_07",
        "source_type": "logs",
        "snippet": "23:10 서버실 보안문 ENTER — badge=E-A(김팀장) fingerprint",
    },
    {
        "evidence_id": "ev_net_01",
        "source_type": "network",
        "snippet": "23:25 라운지 Wi-Fi 192.168.1.15 · ~100GB 외부전송 · MAC=이대리 개인노트북",
    },
]


class GameEngine:
    """In-memory 게임 엔진 — RAG search + detective tools."""

    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.scenario: dict[str, Any] = {}
        self.personas: dict[str, dict[str, Any]] = {}
        self.rag_cfg: dict[str, Any] = {}
        self._load_content()

    def _load_content(self) -> None:
        if SCENARIO_PATH.exists():
            self.scenario = load_yaml(SCENARIO_PATH)
        if PERSONA_DIR.exists():
            for path in sorted(PERSONA_DIR.glob("suspect_*.yaml")):
                persona = load_yaml(path)
                pid = str(persona.get("id") or path.stem)
                self.personas[pid] = persona
        if RAG_CONFIG.exists():
            self.rag_cfg = load_yaml(RAG_CONFIG)

    def create_session(self) -> Session:
        suspects = list(self.scenario.get("suspects") or self.personas.keys())
        session = Session(
            session_id=str(uuid.uuid4())[:8],
            case_id=str(self.scenario.get("case_id", "case_01")),
            pressure={s: 0.0 for s in suspects},
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def public_state(self, session: Session) -> dict[str, Any]:
        suspect_ids = list(self.scenario.get("suspects") or self.personas.keys())
        return {
            "session_id": session.session_id,
            "case_id": session.case_id,
            "title": self.scenario.get("title"),
            "suspects": [
                {"id": sid, "name": self.personas.get(sid, {}).get("name", sid)}
                for sid in suspect_ids
            ],
            "evidence_ids": list(session.evidence_ids),
            "pressure": dict(session.pressure),
            "ended": session.ended,
            "accused": session.accused,
            "turn": len(session.messages),
            "tool_calls": len(session.tool_log),
        }

    def ask(self, session: Session, suspect_id: str, question: str) -> dict[str, Any]:
        if session.ended:
            return {"error": "session_ended"}
        persona = self.personas.get(suspect_id) or {"name": suspect_id, "alibi": "모릅니다."}
        answer = (
            f"[{persona.get('name', suspect_id)}] "
            f"알리바이 기준으로 말하면, {persona.get('alibi', '기억이 안 납니다.')} "
            f"(질문 요약: {question[:80]})"
        )
        pressure = float(session.pressure.get(suspect_id, 0.0))
        if any(
            k in question
            for k in (
                "카드",
                "서버",
                "로그",
                "슬랙",
                "출입",
                "룸살롱",
                "와이파이",
                "Wi-Fi",
                "MAC",
                "전송",
                "모순",
                "증거",
                "Omega",
                "오메가",
                "CCTV",
                "포렌식",
            )
        ):
            pressure = min(1.0, pressure + 0.15)
            session.pressure[suspect_id] = pressure
        # Decisive evidence already collected → higher pressure on culprit
        if suspect_id == self.scenario.get("culprit_id") and "ev_net_01" in session.evidence_ids:
            pressure = min(1.0, max(pressure, 0.85))
            session.pressure[suspect_id] = pressure
        session.messages.append(
            {"role": "suspect", "suspect_id": suspect_id, "question": question, "answer": answer}
        )
        return {"answer": answer, "pressure": pressure, "suspect_id": suspect_id}

    def search(self, session: Session, query: str) -> dict[str, Any]:
        retrieval = self.rag_cfg.get("retrieval", {})
        top_k = int(retrieval.get("top_k", 5))
        rrf_k = int(retrieval.get("rrf_k", 60))
        hits: list[dict[str, Any]] = []
        try:
            persist = ROOT / self.rag_cfg.get("persist_dir", "runs/rag/index")
            index = get_or_build_index(
                ROOT / "data" / "processed" / "chunks.jsonl",
                persist / "vectors.json",
            )
            raw_hits = retrieve(
                index,
                query,
                mode="advanced",
                top_k=top_k,
                rrf_k=rrf_k,
                rerank=bool(retrieval.get("rerank", True)),
            )
            hits = [
                {
                    "evidence_id": h.get("evidence_id"),
                    "source_type": h.get("source_type"),
                    "snippet": str(h.get("text", ""))[:200],
                    "score": h.get("score"),
                    "chunk_id": h.get("chunk_id"),
                }
                for h in raw_hits
            ]
        except Exception:
            hits = []

        if not hits:
            tokens = [t for t in query.split() if t]
            hits = [
                c
                for c in _FALLBACK_CATALOG
                if any(tok in c["snippet"] or tok in query for tok in tokens)
            ] or _FALLBACK_CATALOG[:2]

        for h in hits:
            eid = h.get("evidence_id")
            if eid and eid not in session.evidence_ids:
                session.evidence_ids.append(str(eid))
        return {"query": query, "hits": hits, "evidence_ids": list(session.evidence_ids)}

    def tool(self, session: Session, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        if session.ended:
            return {"error": "session_ended"}
        result = call_tool(name, args or {})
        session.tool_log.append({"name": name, "args": args or {}, "result": result})
        # Forensic on Lee laptop unlocks network hint → count as related evidence
        if name == "run_forensic" and (args or {}).get("device") in {
            "lee_laptop",
            "이대리",
            "suspect_b",
            "lee",
        }:
            if "ev_net_01" not in session.evidence_ids:
                # soft unlock: player still needs RAG, but MAC hint recorded
                pass
        return {"name": name, "args": args or {}, "result": result}

    def accuse(self, session: Session, suspect_id: str) -> dict[str, Any]:
        culprit = str(self.scenario.get("culprit_id", ""))
        session.accused = suspect_id
        session.ended = True
        correct = bool(culprit) and suspect_id == culprit
        if correct:
            ending = (
                "자백 엔딩: 이대리 — 공로·보너스 불만으로 중국 경쟁사 5억에 응해 "
                "라운지 Wi-Fi로 Omega 가중치 약 100GB를 유출. 미션 클리어."
            )
        else:
            ending = "오심 엔딩: 진범 자백을 확보하지 못했습니다."
        return {
            "accused": suspect_id,
            "correct": correct,
            "ending": ending,
        }


engine = GameEngine()

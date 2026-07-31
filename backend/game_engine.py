# -*- coding: utf-8 -*-
"""
backend/game_engine.py — 세션 · 심문 · RAG 검색 · Function Calling · 게임 룰
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

from lib.game_rules import (  # noqa: E402
    SMOKING_GUN_IDS,
    apply_break_count,
    clue_title,
    judge_alibi_broken,
    judge_combo_accuse,
    load_game_cfg,
    mental_break_suspects,
    session_status,
)
from lib.rag_core import get_or_build_index, retrieve  # noqa: E402
from lib.tools import call_tool  # noqa: E402

DEFAULT_API_CONFIG = ROOT / "configs" / "api.yaml"
AGENT_CONFIG = ROOT / "configs" / "agent.yaml"
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
    break_count: dict[str, int] = field(default_factory=dict)
    timeout_strikes: int = 0
    stamina: int = 3
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
    """In-memory 게임 엔진 — RAG search + detective tools + GAME_RULES."""

    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.scenario: dict[str, Any] = {}
        self.personas: dict[str, dict[str, Any]] = {}
        self.rag_cfg: dict[str, Any] = {}
        self.agent_cfg: dict[str, Any] = {}
        self.game_cfg: dict[str, Any] = load_game_cfg({})
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
        cfg_path = AGENT_CONFIG if AGENT_CONFIG.exists() else ROOT / "configs" / "agent.yaml.example"
        if cfg_path.exists():
            self.agent_cfg = load_yaml(cfg_path)
        self.game_cfg = load_game_cfg(self.agent_cfg)

    def create_session(self) -> Session:
        suspects = list(self.scenario.get("suspects") or self.personas.keys())
        session = Session(
            session_id=str(uuid.uuid4())[:8],
            case_id=str(self.scenario.get("case_id", "case_01")),
            pressure={s: 0.0 for s in suspects},
            break_count={s: 0 for s in suspects},
            stamina=int(self.game_cfg["stamina_max"]),
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def _broken_list(self, session: Session) -> list[str]:
        return mental_break_suspects(
            session.break_count,
            threshold=int(self.game_cfg["break_threshold"]),
        )

    def _suspect_ids(self) -> list[str]:
        return list(self.scenario.get("suspects") or self.personas.keys())

    def public_case_overview(self) -> dict[str, Any]:
        """클라이언트용 사건개요 — culprit_id / win_condition / secrets 미포함."""
        overview = self.scenario.get("public_overview") or {}
        if not isinstance(overview, dict):
            overview = {}
        synopsis = str(self.scenario.get("synopsis") or "").strip()
        raw_scenes = overview.get("intro_scenes") or []
        intro_scenes: list[dict[str, str]] = []
        if isinstance(raw_scenes, list):
            for item in raw_scenes:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                intro_scenes.append(
                    {
                        "caption": str(item.get("caption") or "").strip(),
                        "text": text,
                    }
                )
        return {
            "case_id": str(self.scenario.get("case_id", "case_01")),
            "title": self.scenario.get("title"),
            "synopsis": synopsis,
            "discovered_at": str(overview.get("discovered_at") or ""),
            "location": str(overview.get("location") or ""),
            "incident": str(overview.get("incident") or ""),
            "player_role": str(overview.get("player_role") or ""),
            "objective": str(overview.get("objective") or ""),
            "notes": str(overview.get("notes") or synopsis),
            "intro_scenes": intro_scenes,
        }

    def public_suspect_profile(self, suspect_id: str) -> dict[str, Any] | None:
        """공개 프로필만. role/secrets/system_prompt/culprit 미노출."""
        if suspect_id not in self._suspect_ids():
            return None
        persona = self.personas.get(suspect_id) or {}
        raw_profile = persona.get("profile") or {}
        if not isinstance(raw_profile, dict):
            raw_profile = {}
        profile = {str(k): str(v) for k, v in raw_profile.items() if v is not None}
        traits = persona.get("traits") or []
        if not isinstance(traits, list):
            traits = []
        return {
            "id": suspect_id,
            "name": str(persona.get("name") or suspect_id),
            "mbti": str(persona.get("mbti") or ""),
            "traits": [str(t) for t in traits],
            "profile": profile,
            "case_overview": self.public_case_overview(),
        }

    def public_state(self, session: Session, *, focus_suspect: str | None = None) -> dict[str, Any]:
        suspect_ids = self._suspect_ids()
        broken = self._broken_list(session)
        strike_max = int(self.game_cfg["timeout_strike_max"])
        stamina_max = int(self.game_cfg["stamina_max"])
        turn_out = session.ended and session.timeout_strikes >= strike_max and session.stamina > 0
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
            "break_count": dict(session.break_count),
            "mental_break_suspects": broken,
            "timeout_strikes": int(session.timeout_strikes),
            "timeout_strike_max": strike_max,
            "stamina": int(session.stamina),
            "stamina_max": stamina_max,
            "status": session_status(
                focus_suspect,
                broken,
                timeout_strikes=session.timeout_strikes,
                timeout_strike_max=strike_max,
                ended=session.ended,
                turn_out=turn_out,
                stamina=session.stamina,
            ),
            "turn_seconds": int(self.game_cfg["turn_seconds"]),
            "timer_enabled": bool(self.game_cfg["timer_enabled"]),
            "ended": session.ended,
            "accused": session.accused,
            "turn": len(session.messages),
            "tool_calls": len(session.tool_log),
        }

    def _compose_answer(self, persona: dict[str, Any], suspect_id: str, question: str, mental: bool) -> str:
        name = persona.get("name", suspect_id)
        alibi = persona.get("alibi", "기억이 안 납니다.")
        if mental:
            return (
                f"[{name} · 멘탈 붕괴] …{alibi} "
                f"더 이상 버티기 어렵습니다. (질문: {question[:60]})"
            )
        return f"[{name}] 알리바이 기준으로 말하면, {alibi} (질문 요약: {question[:80]})"

    def ask(self, session: Session, suspect_id: str, question: str) -> dict[str, Any]:
        if session.ended:
            return {"error": "session_ended"}
        persona = self.personas.get(suspect_id) or {"name": suspect_id, "alibi": "모릅니다."}
        threshold = int(self.game_cfg["break_threshold"])

        is_broken = judge_alibi_broken(suspect_id, question, session.evidence_ids)
        session.break_count, incremented = apply_break_count(
            session.break_count,
            suspect_id,
            is_broken=is_broken,
            threshold=threshold,
            max_per_turn=int(self.game_cfg["max_break_per_turn"]),
        )
        broken = self._broken_list(session)
        mental = suspect_id in broken
        status = session_status(
            suspect_id,
            broken,
            timeout_strikes=session.timeout_strikes,
            timeout_strike_max=int(self.game_cfg["timeout_strike_max"]),
            ended=session.ended,
        )

        answer = self._compose_answer(persona, suspect_id, question, mental)

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
                "알리바이",
            )
        ):
            pressure = min(1.0, pressure + 0.15)
        if incremented:
            pressure = min(1.0, pressure + 0.2)
        if suspect_id == self.scenario.get("culprit_id") and "ev_net_01" in session.evidence_ids:
            pressure = min(1.0, max(pressure, 0.85))
        session.pressure[suspect_id] = pressure

        session.messages.append(
            {
                "role": "suspect",
                "suspect_id": suspect_id,
                "question": question,
                "answer": answer,
                "is_alibi_broken": is_broken and incremented,
            }
        )
        return {
            "answer": answer,
            "pressure": pressure,
            "suspect_id": suspect_id,
            "is_alibi_broken": bool(is_broken and incremented),
            "break_count": int(session.break_count.get(suspect_id, 0)),
            "status": status,
        }

    def pass_turn(self, session: Session, reason: str = "timeout") -> dict[str, Any]:
        """타임어택 만료 — timeout_strikes 증가. 3회면 turn_out(패배). 알리바이 break는 미증가."""
        if session.ended:
            return {"error": "session_ended"}
        strike_max = int(self.game_cfg["timeout_strike_max"])
        session.timeout_strikes = min(strike_max, int(session.timeout_strikes) + 1)
        session.messages.append(
            {
                "role": "system",
                "event": "pass_turn",
                "reason": reason,
                "timeout_strikes": session.timeout_strikes,
            }
        )
        turn_out = session.timeout_strikes >= strike_max
        if turn_out:
            session.ended = True
        return {
            "passed": True,
            "reason": reason,
            "timeout_strikes": session.timeout_strikes,
            "timeout_strike_max": strike_max,
            "turn_out": turn_out,
            "status": "turn_out" if turn_out else "playing",
            "ending": (
                f"턴 3진 아웃: 시간 초과 {strike_max}회. 미션 실패."
                if turn_out
                else None
            ),
        }

    def _apply_stamina_loss(self, session: Session, amount: int = 1) -> dict[str, Any]:
        session.stamina = max(0, int(session.stamina) - amount)
        revoked = session.stamina <= 0
        if revoked:
            session.ended = True
        return {
            "stamina": session.stamina,
            "stamina_max": int(self.game_cfg["stamina_max"]),
            "authority_revoked": revoked,
            "ending": (
                "감사관, 당신은 무능합니다. 수사 권한이 박탈되었습니다."
                if revoked
                else None
            ),
        }

    def search(self, session: Session, query: str) -> dict[str, Any]:
        if session.ended:
            return {"error": "session_ended"}
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
            tokens = [t for t in query.split() if len(t) >= 2]
            hits = [
                c
                for c in _FALLBACK_CATALOG
                if tokens
                and any(tok in c["snippet"] or tok in query for tok in tokens)
            ]
            # 토큰 매칭 실패 시 빈 hits → 헛수색(수사 권한 감소). 무료 카탈로그 지급 금지.

        before = set(session.evidence_ids)
        newly: list[str] = []
        for h in hits:
            eid = h.get("evidence_id")
            if eid and eid not in session.evidence_ids:
                session.evidence_ids.append(str(eid))
                newly.append(str(eid))

        new_clues = [
            {
                "evidence_id": eid,
                "title": clue_title(eid),
                "snippet": next(
                    (str(h.get("snippet", ""))[:160] for h in hits if h.get("evidence_id") == eid),
                    "",
                ),
                "smoking_gun": eid in SMOKING_GUN_IDS,
            }
            for eid in newly
            if eid in SMOKING_GUN_IDS or eid not in before
        ]
        # UI 연출은 smoking gun 위주
        new_clues = [c for c in new_clues if c["smoking_gun"]]

        useless = len(newly) == 0
        stamina_info: dict[str, Any] = {}
        if useless:
            stamina_info = self._apply_stamina_loss(session, 1)

        return {
            "query": query,
            "hits": hits,
            "evidence_ids": list(session.evidence_ids),
            "new_clues": new_clues,
            "useless_search": useless,
            **stamina_info,
        }

    def tool(self, session: Session, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        if session.ended:
            return {"error": "session_ended"}
        result = call_tool(name, args or {})
        session.tool_log.append({"name": name, "args": args or {}, "result": result})
        return {"name": name, "args": args or {}, "result": result}

    def accuse(
        self,
        session: Session,
        suspect_id: str,
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """조합 지목: 용의자 + 결정적 증거 2장 (docs/GAME_RULES.md §8.2)."""
        if session.ended:
            return {"error": "session_ended"}
        submitted = list(evidence_ids or [])
        win_ids = list((self.scenario.get("win_condition") or {}).get("min_evidence_ids") or [])
        culprit = str(self.scenario.get("culprit_id", ""))
        verdict = judge_combo_accuse(
            suspect_id=suspect_id,
            evidence_ids=submitted,
            culprit_id=culprit,
            win_evidence_ids=win_ids,
            owned_evidence_ids=session.evidence_ids,
        )

        if verdict["correct"]:
            session.accused = suspect_id
            session.ended = True
            ending = (
                "자백 엔딩: 이대리 — 공로·보너스 불만으로 중국 경쟁사 5억에 응해 "
                "라운지 Wi-Fi로 Omega 가중치 약 100GB를 유출. 미션 클리어."
            )
            return {
                "accused": suspect_id,
                "evidence_ids": submitted,
                "correct": True,
                "ending": ending,
                "judge": verdict,
            }

        # 오답 → 수사 권한 감소 (세션 유지 가능)
        stamina_info = self._apply_stamina_loss(session, 1)
        msg = "조합 지목 실패: " + (
            "; ".join(verdict["errors"]) if verdict["errors"] else "진범·증거가 일치하지 않습니다."
        )
        if stamina_info.get("authority_revoked"):
            session.accused = suspect_id
            ending = stamina_info["ending"]
        else:
            ending = msg + f" (수사 권한 {session.stamina}/{self.game_cfg['stamina_max']})"
        return {
            "accused": suspect_id if stamina_info.get("authority_revoked") else None,
            "evidence_ids": submitted,
            "correct": False,
            "ending": ending,
            "judge": verdict,
            **stamina_info,
        }


engine = GameEngine()

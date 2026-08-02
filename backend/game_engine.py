# -*- coding: utf-8 -*-
"""
backend/game_engine.py — 세션 · 심문 · RAG 검색 · Function Calling · 게임 룰
"""

from __future__ import annotations

import logging
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger("truth_room.ask")

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.game_rules import (  # noqa: E402
    SMOKING_GUN_IDS,
    apply_break_count,
    clue_title,
    judge_combo_accuse,
    load_game_cfg,
    mental_break_suspects,
    question_hits_pressure,
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

    def _evidence_briefs(self, evidence_ids: list[str]) -> list[str]:
        """조수 프롬프트용 — 확보 증거의 짧은 사실 요약(미보유 내용은 넣지 않음)."""
        by_id = {
            str(c.get("evidence_id")): str(c.get("snippet") or "")
            for c in _FALLBACK_CATALOG
            if c.get("evidence_id")
        }
        subject = {
            "ev_card_03": "주체:김팀장",
            "ev_log_07": "주체:김팀장(출입)",
            "ev_msg_12": "주체:박신입",
            "ev_net_01": "주체:이대리(MAC)",
        }
        briefs: list[str] = []
        for eid in evidence_ids:
            sid = str(eid)
            snip = by_id.get(sid, "").strip()
            title = clue_title(sid)
            who = subject.get(sid, "")
            head = f"{title} [{who}]" if who else title
            briefs.append(f"{head}: {snip}" if snip else head)
        return briefs

    def _name_by_id(self) -> dict[str, str]:
        return {
            sid: str(self.personas.get(sid, {}).get("name") or sid)
            for sid in self._suspect_ids()
        }

    def _session_memory(
        self,
        session: Session,
        *,
        suspect_id: str,
        suspect_name: str,
        focus_turns: int = 6,
        other_turns: int = 2,
    ) -> dict[str, str]:
        from lib.session_memory import build_session_memory

        return build_session_memory(
            session.messages,
            suspect_id=suspect_id,
            suspect_name=suspect_name,
            evidence_briefs=self._evidence_briefs(session.evidence_ids),
            name_by_id=self._name_by_id(),
            focus_turns=focus_turns,
            other_turns=other_turns,
        )

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
                        "image": str(item.get("image") or "").strip(),
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
        """공개 프로필만. role/secrets/system_prompt/culprit/실제_행적 미노출."""
        if suspect_id not in self._suspect_ids():
            return None
        persona = self.personas.get(suspect_id) or {}
        raw_profile = persona.get("profile") or {}
        if not isinstance(raw_profile, dict):
            raw_profile = {}
        profile = {str(k): str(v) for k, v in raw_profile.items() if v is not None}

        # 변수표(prompt_vars) 공개 가능 항목 → 프로필에 병합 (스포일러 키 제외)
        vars_ = persona.get("prompt_vars") or {}
        if isinstance(vars_, dict):
            public_map = {
                "나이대": "age_group",
                "직급": "rank",
                "성격_한줄": "personality",
                "말투_특징": "speech_style",
                "당황시_반응": "fluster_reaction",
                "예시_대사": "sample_line",
                "주장_알리바이": "claimed_alibi",
            }
            for src, dst in public_map.items():
                val = str(vars_.get(src) or "").strip()
                if val and not profile.get(dst):
                    profile[dst] = val
            # 유형(아키타입) — traits 첫 항 또는 profile.archetype
            if not profile.get("archetype"):
                traits0 = persona.get("traits") or []
                if isinstance(traits0, list) and traits0:
                    profile["archetype"] = str(traits0[0])

        # alibi 필드도 주장 알리바이로 공개
        alibi = str(persona.get("alibi") or "").strip()
        if alibi and not profile.get("claimed_alibi"):
            profile["claimed_alibi"] = alibi

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
            # UI/설정 동기화: 프로세스 기동 후에도 yaml 변경 반영
            "timer_enabled": bool(load_game_cfg(load_yaml(AGENT_CONFIG) if AGENT_CONFIG.exists() else self.agent_cfg)["timer_enabled"]),
            "ended": session.ended,
            "accused": session.accused,
            "turn": len(session.messages),
            "tool_calls": len(session.tool_log),
        }

    def _question_topic(self, question: str) -> str:
        """질문 주제 분류 — 스텁 답변 분기용."""
        from lib.gm_judge import is_nonsensical_question

        q = (question or "").strip()
        if len(q) < 2 or is_nonsensical_question(q):
            return "unclear"
        # 자모만 / 의미 없는 난타
        if re.fullmatch(r"[ㄱ-ㅎㅏ-ㅣ\s\W]+", q) or re.fullmatch(r"[a-zA-Z0-9\s]{1,12}", q):
            return "unclear"
        low = q.lower()
        rules: list[tuple[str, tuple[str, ...]]] = [
            ("alibi", ("어디", "그밤", "그날", "몇 시", "몇시", "알리바이", "있었", "뭐 하", "뭐하", "야근")),
            ("card", ("카드", "룸살롱", "강남", "결제", "법인")),
            ("slack", ("슬랙", "메신저", "dm", "메시지", "박신입", "침입")),
            ("network", ("와이파이", "wi-fi", "wifi", "네트워크", "100gb", "전송", "mac")),
            ("server", ("서버", "출입", "로그", "cctv", "지문", "배지")),
            ("omega", ("오메가", "omega", "가중치", "유출", "파일")),
            ("who", ("누구", "범인", "누가", "진범")),
            ("why", ("왜", "이유", "동기")),
            ("accuse", ("증거", "모순", "거짓말", "들통", "압박")),
        ]
        for topic, keys in rules:
            if any(k in low or k in q for k in keys):
                return topic
        return "general"

    @staticmethod
    def _bare_dialogue(text: str, name: str) -> str:
        """채팅 UI에 이름이 따로 뜨므로 [이름] 접두를 제거."""
        t = (text or "").strip()
        for tag in (f"[{name} · 멘탈 붕괴]", f"[{name}]"):
            if t.startswith(tag):
                t = t[len(tag) :].lstrip(" ·")
        return t.strip()

    def _compose_answer(
        self,
        persona: dict[str, Any],
        suspect_id: str,
        question: str,
        mental: bool,
        *,
        pressure: float = 0.0,
    ) -> str:
        name = persona.get("name", suspect_id)
        alibi = persona.get("alibi", "기억이 안 납니다.")
        vars_ = persona.get("prompt_vars") or {}
        example = str(vars_.get("예시_대사") or "").strip()
        fluster = str(vars_.get("당황시_반응") or "당황한 기색")
        _ = pressure
        topic = self._question_topic(question)

        def out(line: str) -> str:
            return self._bare_dialogue(line, name)

        if mental:
            return out(
                f"({fluster}) …{alibi} 더 이상 버티기 어렵습니다."
            )

        # 질문별로 다른 스텁 (AutoGen/LLM 실패 시에도 대화가 단조롭지 않게)
        if topic == "unclear":
            # 페르소나 예시 대사 톤과 맞춤 (알리바이·안내 문구 금지)
            # 김: 반말 섞인 꼰대 / 이: 차분한 존댓말·반문 / 박: 말더듬·사과
            if "김" in name:
                return out("에헴! 이 양반아, 지금 장난해? 말 같지도 않은 소리 하고 있어.")
            if "이대" in name:
                return out("…네? 지금 그걸 질문이라고 하신 건가요. 의도가 안 보입니다.")
            return out("그, 그게… 무슨… 말씀이세요? 저… 죄송해요, 잘 못 알아들었어요.")

        if topic == "alibi":
            if "김" in name:
                return out(
                    "에헴, 이 양반아. 나는 야근하며 서류 검토 중이었다고. "
                    "나 때는 이런 잔업이 기본이었네."
                )
            opener = example or f"{name}입니다."
            return out(f"{opener} {alibi}")

        if topic == "card":
            if "김" in name:
                return out(
                    "에헴! 법인카드? 업무용이지, 그게 왜. "
                    "이 양반아, 나는 야근 중이었다고 하지 않았어."
                )
            if "이대" in name:
                return out(
                    "카드 내역은 제가 확인할 권한이 없습니다. 알리바이와는 무관합니다."
                )
            return out("카, 카드요? 저 그런 거 없어요… 진짜로요.")

        if topic == "slack":
            if "박" in name:
                return out(
                    "슬, 슬랙이요? 그… 그때는… 아뇨, 저 화장실에만… "
                    "죄송해요, 머리가 하얘져요."
                )
            if "이대" in name:
                return out(
                    "메신저 기록은 공개 범위 내에서만 확인하시죠. 저는 라운지에 있었습니다."
                )
            return out("슬랙? 이 양반아, 난 야근하느라 폰도 안 봤소.")

        if topic == "network" or topic == "server":
            if "이대" in name:
                return out(
                    "서버실 출입 로그를 보시면 제 이름은 없습니다. "
                    "라운지에서 쉬고 있었습니다."
                )
            if "박" in name:
                return out(
                    "서, 서버실요? 저 그런 데 갈 자격도… 아뇨 진짜… 화장실이었어요."
                )
            return out("서버실? 난 내 자리에서 서류만 봤소. 에헴.")

        if topic == "omega":
            if "김" in name:
                return out(
                    "프로젝트 Omega요? 다들 아는 이름이지. "
                    "그렇다고 제가 파일을 훔쳤다는 말은 아니지 않소."
                )
            return out(
                "Omega 파일 유출… 저도 충격입니다. "
                "그 시각 제 알리바이는 변함없습니다."
            )

        if topic == "who":
            if "이대" in name:
                return out("추측은 삼가겠습니다. 증거로 말씀하시죠.")
            if "박" in name:
                return out("누, 누구냐니… 저 아니에요. 정말이에요… 죄송해요.")
            return out(
                "범인? 이 양반아, 날 의심하다니. 나 때는 이런 일이 없었소."
            )

        if topic == "why":
            return out(f"동기 운운이요? 저는 할 말 없습니다. {alibi}")

        if topic == "accuse":
            if "김" in name:
                return out(
                    f"({fluster}) …증거가 있으면 내놓으시오. 말만으로 몰아붙이지 말고."
                )
            if "이대" in name:
                return out(
                    f"({fluster}) 모순이라니… 구체적 근거를 제시해 주십시오."
                )
            return out(f"({fluster}) 거짓말 아니에요… 제발 믿어 주세요…")

        # general — 질문 일부를 언급해 동일 문장 반복 느낌 완화
        snip = question.strip().replace("\n", " ")[:24]
        opener = example.split(".")[0].strip() if example else name
        return out(f"{opener}. '{snip}…' 이라니, 그 부분만 말하면 {alibi}")

    def _llm_compose_answer(
        self,
        persona: dict[str, Any],
        question: str,
        *,
        mental: bool,
        pressure: float,
        model: str,
        dialogue: str = "",
    ) -> str | None:
        """AutoGen 실패 시 단발 LLM 대사. 실패하면 None."""
        if not os.environ.get("OPENAI_API_KEY"):
            return None
        try:
            from openai import OpenAI

            from lib.persona_prompt import render_suspect_prompt

            system = render_suspect_prompt(
                persona, pressure=pressure, mental_break=mental
            )
            hist = (dialogue or "").strip()
            user_body = (
                "감사관의 심문입니다. 페르소나·제약을 지키며 "
                "질문에 직접 답하세요. 3문장 이내, 한국어만.\n"
            )
            if hist:
                user_body += (
                    "이전 이 탐정과의 심문을 기억한 듯 자연스럽게 이어 답하세요.\n"
                    f"[최근 심문]\n{hist}\n"
                )
            user_body += f"질문: {question}"
            client = OpenAI()
            resp = client.chat.completions.create(
                model=model or "gpt-4o-mini",
                temperature=0.55,
                timeout=25,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_body},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or None
        except Exception:
            return None

    def ask(self, session: Session, suspect_id: str, question: str) -> dict[str, Any]:
        if session.ended:
            return {"error": "session_ended"}
        persona = self.personas.get(suspect_id) or {"name": suspect_id, "alibi": "모릅니다."}
        threshold = int(self.game_cfg["break_threshold"])

        pressure = float(session.pressure.get(suspect_id, 0.0))
        from lib.gm_judge import (
            is_lie_broken,
            is_nonsensical_question,
            local_judge_lie,
            stress_delta_to_pressure,
        )
        from lib.persona_prompt import render_suspect_prompt

        vars_ = persona.get("prompt_vars") if isinstance(persona.get("prompt_vars"), dict) else {}
        broken_pre = self._broken_list(session)
        mental_pre = suspect_id in broken_pre

        ag_cfg = (
            self.agent_cfg.get("autogen")
            if isinstance(self.agent_cfg.get("autogen"), dict)
            else {}
        )
        use_autogen = bool(ag_cfg.get("enabled", False))
        llm_model = str(
            ag_cfg.get("model")
            or self.agent_cfg.get("llm_model")
            or "gpt-4o-mini"
        )
        agent_transcript: list[dict[str, str]] = []
        assistant_note = ""
        autogen_meta: dict[str, Any] = {"used": False}
        verdict: dict[str, Any] | None = None

        draft_answer = self._compose_answer(
            persona, suspect_id, question, mental=mental_pre, pressure=pressure
        )
        answer = draft_answer
        suspect_name = str(persona.get("name") or suspect_id)
        mem = self._session_memory(
            session,
            suspect_id=suspect_id,
            suspect_name=suspect_name,
            focus_turns=int(ag_cfg.get("memory_turns") or 6),
            other_turns=int(ag_cfg.get("other_summary_turns") or 2),
        )

        # 자모 난타 등 — AutoGen/LLM/조수 힌트 없이 되묻기만 (알리바이·증거 유도 금지)
        unclear_input = is_nonsensical_question(question) or (
            self._question_topic(question) == "unclear"
        )
        if unclear_input:
            answer = draft_answer
            assistant_note = ""
            verdict = {
                "status": "no_effect",
                "stress_delta": 0,
                "reason_internal": "unclear_or_nonsensical_question",
                "judge": "input_gate",
            }
            autogen_meta = {"used": False, "skipped": "unclear_question"}

        if use_autogen and not unclear_input:
            try:
                from lib.autogen_runtime import (
                    autogen_available,
                    repair_assistant_note,
                    run_interrogation_turn,
                )
                from lib.gm_judge import render_judge_prompt

                if not autogen_available() and str(ag_cfg.get("mode") or "pipeline").lower() == "groupchat":
                    raise RuntimeError("pyautogen not installed")
                # pipeline 모드는 OpenAI만 있으면 됨
                if not os.environ.get("OPENAI_API_KEY"):
                    raise RuntimeError("OPENAI_API_KEY missing")
                suspect_sys = render_suspect_prompt(
                    persona, pressure=pressure, mental_break=mental_pre
                )
                held_briefs = self._evidence_briefs(session.evidence_ids)
                judge_sys = render_judge_prompt(
                    prompt_vars=vars_,
                    user_input=question,
                    npc_response="",
                )
                ag = run_interrogation_turn(
                    question=question,
                    suspect_system=suspect_sys,
                    assistant_system=str(self.agent_cfg.get("gm_system_prompt") or ""),
                    judge_system=judge_sys,
                    evidence_ids=list(session.evidence_ids),
                    evidence_briefs=held_briefs,
                    recent_dialogue=mem.get("focus_dialogue") or "",
                    session_memory=mem.get("block") or "",
                    suspect_id=suspect_id,
                    suspect_name=suspect_name,
                    pressure=dict(session.pressure),
                    break_count={k: int(v) for k, v in session.break_count.items()},
                    model=llm_model,
                    max_round=int(ag_cfg.get("max_round") or 4),
                    temperature=float(ag_cfg.get("temperature") or 0.2),
                    timeout_sec=int(ag_cfg.get("timeout_sec") or 50),
                    mode=str(ag_cfg.get("mode") or "pipeline"),
                )
                answer = str(ag.get("answer") or draft_answer)
                agent_transcript = list(ag.get("transcript") or [])
                assistant_note = repair_assistant_note(
                    str(ag.get("assistant_note") or ""),
                    question=question,
                    evidence_ids=list(session.evidence_ids),
                    evidence_briefs=held_briefs,
                    suspect_id=suspect_id,
                    suspect_name=suspect_name,
                )
                gv = ag.get("gm_verdict") or {}
                # AutoGen/파이프라인 심판 제안 우선, 실패 시 로컬 재판정
                if gv.get("status") in ("lie_broken", "no_effect"):
                    verdict = {
                        "status": gv.get("status"),
                        "stress_delta": int(gv.get("stress_delta") or 0),
                        "judge": gv.get("judge") or "autogen",
                        "reason_internal": gv.get("reason_internal"),
                    }
                autogen_meta = {
                    "used": True,
                    "elapsed_sec": ag.get("elapsed_sec"),
                    "n_messages": ag.get("n_messages"),
                    "backend": ag.get("backend"),
                    "story_branch": ag.get("story_branch"),
                    "tool_pack": ag.get("tool_pack"),
                }
            except Exception as exc:  # noqa: BLE001 — 데모 안정: 폴백
                autogen_meta = {
                    "used": False,
                    "fallback": True,
                    "error": str(exc)[:200],
                }
                _log.warning("AutoGen 폴백: %s", autogen_meta["error"])

        # AutoGen 미사용 시: 단발 LLM → 질문 분기 스텁 (무의미 입력은 스텁 되묻기 유지)
        if unclear_input:
            answer = draft_answer
            _log.info("심문 경로: unclear_gate (되묻기만)")
        elif not autogen_meta.get("used"):
            llm_answer = self._llm_compose_answer(
                persona,
                question,
                mental=mental_pre,
                pressure=pressure,
                model=llm_model,
                dialogue=mem.get("focus_dialogue") or "",
            )
            if llm_answer:
                answer = llm_answer
                autogen_meta = {**autogen_meta, "llm_direct": True}
                _log.info("심문 경로: llm_direct (AutoGen 미사용/실패)")
            else:
                answer = draft_answer
                _log.info("심문 경로: stub (AutoGen·LLM 모두 실패/미사용)")
        else:
            _log.info(
                "심문 경로: autogen elapsed=%ss msgs=%s",
                autogen_meta.get("elapsed_sec"),
                autogen_meta.get("n_messages"),
            )

        local_verdict = local_judge_lie(
            suspect_id=suspect_id,
            user_input=question,
            evidence_ids=session.evidence_ids,
            prompt_vars=vars_,
            npc_response=answer,
        )
        if verdict is None:
            verdict = local_verdict
        elif is_lie_broken(local_verdict):
            # 결정적 증거 보유+토큰 → 로컬 붕괴가 최종 권위
            # (AutoGen이 no_effect로 덮어 압박/STRESS가 안 오르는 문제 방지)
            if not is_lie_broken(verdict):
                _log.info(
                    "로컬 lie_broken 채택 — autogen=%s q=%r",
                    verdict.get("status"),
                    (question or "")[:40],
                )
            verdict = local_verdict
        elif is_lie_broken(verdict) and not is_lie_broken(local_verdict):
            # AutoGen 심판이 허접/무관 질문에도 lie_broken을 주는 오판 방지
            _log.info(
                "AutoGen lie_broken 무시 — local=%s q=%r",
                local_verdict.get("reason_internal"),
                (question or "")[:40],
            )
            verdict = {
                "status": "no_effect",
                "stress_delta": 0,
                "reason_internal": "autogen_lie_broken_gated_by_local",
                "judge": "autogen_gated",
            }
        elif not is_lie_broken(local_verdict):
            # 로컬이 무관/타 증거면 GM stress_delta도 올리지 않음
            # (『확보했다』+룸살롱→이대리 같은 오판 방지)
            local_delta = int(local_verdict.get("stress_delta") or 0)
            if local_delta <= 0:
                verdict = {
                    "status": "no_effect",
                    "stress_delta": 0,
                    "reason_internal": local_verdict.get("reason_internal")
                    or "local_no_effect_caps_gm",
                    "judge": "local_cap",
                }
            elif local_delta > int(verdict.get("stress_delta") or 0):
                verdict = {
                    **verdict,
                    "status": "no_effect",
                    "stress_delta": local_delta,
                    "reason_internal": local_verdict.get("reason_internal")
                    or verdict.get("reason_internal"),
                    "judge": f"{verdict.get('judge') or 'autogen'}+local_delta",
                }
            else:
                verdict = {
                    **verdict,
                    "status": "no_effect",
                    "stress_delta": min(int(verdict.get("stress_delta") or 0), local_delta),
                    "judge": f"{verdict.get('judge') or 'autogen'}+local_cap",
                }

        is_broken = is_lie_broken(verdict)
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

        # 멘탈 붕괴 직후 스텁만 톤 재합성 (LLM/AutoGen 응답은 유지)
        if (
            mental
            and not mental_pre
            and not autogen_meta.get("used")
            and not autogen_meta.get("llm_direct")
        ):
            answer = self._compose_answer(
                persona, suspect_id, question, mental=True, pressure=pressure
            )

        if question_hits_pressure(suspect_id, question):
            pressure = min(1.0, pressure + 0.15)
        pressure = min(
            1.0,
            max(0.0, pressure + stress_delta_to_pressure(int(verdict.get("stress_delta") or 0))),
        )
        if incremented:
            pressure = min(1.0, pressure + 0.2)
        # 진범+네트워크 보유만으로 매 턴 85% 강제 금지
        # (「어디에 있었나」유도에도 MENTAL BREAK처럼 보이는 오해 방지)
        # 실제로 알리바이가 붕괴된 뒤에만 하한 적용
        if (
            suspect_id == self.scenario.get("culprit_id")
            and "ev_net_01" in session.evidence_ids
            and (incremented or int(session.break_count.get(suspect_id, 0) or 0) >= 1)
        ):
            pressure = min(1.0, max(pressure, 0.85))
        session.pressure[suspect_id] = pressure

        session.messages.append(
            {
                "role": "suspect",
                "suspect_id": suspect_id,
                "question": question,
                "answer": answer,
                "is_alibi_broken": is_broken and incremented,
                "agent_transcript": agent_transcript,
                "assistant_note": assistant_note,
                "autogen": autogen_meta,
                "gm_verdict": {
                    "status": verdict.get("status"),
                    "stress_delta": verdict.get("stress_delta"),
                    "judge": verdict.get("judge"),
                },
            }
        )
        try:
            from lib.conversation_log import append_ask_turn

            append_ask_turn(
                self.agent_cfg,
                session_id=session.session_id,
                case_id=session.case_id,
                suspect_id=suspect_id,
                suspect_name=str(persona.get("name") or suspect_id),
                question=question,
                answer=answer,
                assistant_note=assistant_note,
                evidence_ids=list(session.evidence_ids),
                is_alibi_broken=bool(is_broken and incremented),
                break_count=int(session.break_count.get(suspect_id, 0)),
                gm_status=str(verdict.get("status") or ""),
            )
        except Exception:  # noqa: BLE001
            _log.warning("conversation_log 호출 실패", exc_info=False)

        return {
            "answer": answer,
            "pressure": pressure,
            "suspect_id": suspect_id,
            "is_alibi_broken": bool(is_broken and incremented),
            "break_count": int(session.break_count.get(suspect_id, 0)),
            "status": status,
            "gm_status": verdict.get("status"),
            "stress_delta": verdict.get("stress_delta"),
            "agent_transcript": agent_transcript,
            "assistant_note": assistant_note,
            "autogen": autogen_meta,
            "story_branch": autogen_meta.get("story_branch"),
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

    def search(
        self,
        session: Session,
        query: str,
        *,
        force_miss: bool = False,
        force_evidence_id: str | None = None,
    ) -> dict[str, Any]:
        if session.ended:
            return {"error": "session_ended"}
        # 책상 decoy 클릭 — RAG 우회·강제 헛수색 (수사 권한 감소)
        if force_miss:
            stamina_info = self._apply_stamina_loss(session, 1)
            return {
                "query": query,
                "hits": [],
                "evidence_ids": list(session.evidence_ids),
                "new_clues": [],
                "useless_search": True,
                **stamina_info,
            }
        # 책상 핵심/수집 증거 클릭 — RAG 우회·지정 ID 지급
        if force_evidence_id:
            eid = str(force_evidence_id).strip()
            newly: list[str] = []
            if eid and eid not in session.evidence_ids:
                session.evidence_ids.append(eid)
                newly.append(eid)
            hits = [
                {
                    "evidence_id": eid,
                    "source_type": "desk",
                    "snippet": clue_title(eid),
                    "score": 1.0,
                    "chunk_id": None,
                }
            ]
            new_clues = [
                {
                    "evidence_id": x,
                    "title": clue_title(x),
                    "snippet": clue_title(x),
                    "smoking_gun": x in SMOKING_GUN_IDS,
                }
                for x in newly
                if x in SMOKING_GUN_IDS
            ]
            return {
                "query": query,
                "hits": hits,
                "evidence_ids": list(session.evidence_ids),
                "new_clues": new_clues,
                "useless_search": False,
                "already_owned": len(newly) == 0,
                "stamina": session.stamina,
                "stamina_max": int(self.game_cfg["stamina_max"]),
            }
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
                expand=bool(retrieval.get("expand_query", True)),
                source_types=[str(s) for s in (retrieval.get("source_types") or []) if s]
                or None,
                source_routing=str(retrieval.get("source_routing") or "soft"),
                boost_evidence=float(retrieval.get("boost_evidence", 0.20)),
                boost_canonical=float(retrieval.get("boost_canonical", 0.25)),
                boost_keyword=float(retrieval.get("boost_keyword", 0.05)),
                boost_source=float(retrieval.get("boost_source", 0.18)),
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
        from lib.gm_judge import enrich_accuse_verdict, public_accuse_judge

        verdict = enrich_accuse_verdict(
            verdict,
            accused_suspect_id=suspect_id,
            owned_evidence_ids=session.evidence_ids,
            agent_cfg=self.agent_cfg,
        )
        public_judge = public_accuse_judge(verdict)

        if verdict["correct"]:
            session.accused = suspect_id
            session.ended = True
            ending = str(verdict.get("public_summary") or "").strip() or (
                "자백 엔딩: 이대리 — 공로·보너스 불만으로 중국 경쟁사 5억에 응해 "
                "라운지 Wi-Fi로 Omega 가중치 약 100GB를 유출. 미션 클리어."
            )
            return {
                "accused": suspect_id,
                "evidence_ids": submitted,
                "correct": True,
                "ending": ending,
                "judge": public_judge,
            }

        # 오답 → 수사 권한 감소 (세션 유지 가능)
        stamina_info = self._apply_stamina_loss(session, 1)
        base = str(verdict.get("public_summary") or "").strip()
        if not base:
            base = "조합 지목 실패: " + (
                "; ".join(verdict["errors"]) if verdict["errors"] else "진범·증거가 일치하지 않습니다."
            )
        if stamina_info.get("authority_revoked"):
            session.accused = suspect_id
            ending = stamina_info["ending"]
        else:
            ending = base + f" (수사 권한 {session.stamina}/{self.game_cfg['stamina_max']})"
        return {
            "accused": suspect_id if stamina_info.get("authority_revoked") else None,
            "evidence_ids": submitted,
            "correct": False,
            "ending": ending,
            "judge": public_judge,
            **stamina_info,
        }


engine = GameEngine()

# -*- coding: utf-8 -*-
"""lib/autogen_runtime.py — 본선 멀티에이전트 심문 턴

기본 mode=pipeline (슬라이드급 고정 협업):
  ForensicAssistant(Function Calling/보유증거)
  → Suspect(페르소나)
  → Judge(GM 템플릿 JSON)
  + story_branch(증거·pressure 분기)

mode=groupchat: 레거시 AutoGen round_robin (상한·폴백 유지, 무제한 티키타카 금지).
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


def sanitize_assistant_note(text: str) -> str:
    """조수 멘트의 툴/함수명·JSON 노출을 플레이어용 한국어로 치환."""
    raw = (text or "").strip()
    if not raw:
        return ""
    # dict/JSON 덤프 제거 (예: {'이대리': {...}})
    raw = re.sub(r"\{[^{}]{0,500}\}", "", raw).strip()
    raw = re.sub(r"[`]+", "", raw).strip()
    lower = raw.lower()
    tool_hints = (
        ("check_card_history", "법인카드 쪽은 「증거 수색」에서 한번 확인해 보죠."),
        ("run_forensic", "기기·포렌식 자료는 「증거 수색」에서 먼저 챙겨 보죠."),
        ("search_messenger", "메신저 기록은 「증거 수색」에서 한번 훑어보죠."),
        ("request_cctv_log", "출입·CCTV 로그는 「증거 수색」에서 확인해 보죠."),
    )
    for key, hint in tool_hints:
        if key in lower or key in raw:
            return hint
    if re.search(r"\b\w+\s*\([^)]*\)\s*호출", raw) or "function" in lower:
        return "관련 자료가 아직이에요. 「증거 수색」에서 먼저 확보해 보죠."
    return _strip_culprit_leak(raw)


_VAGUE_ASSIST_RE = re.compile(r"애매|짚어\s*주세요|명확히\s*해\s*주세요")
_SEARCH_LOG_RE = re.compile(r"출입\s*로그부터|서버실\s*출입\s*로그부터")
_KIM_FINGERPRINT_RE = re.compile(r"김팀장.{0,12}지문|지문.{0,12}김팀장|23:10")
_SEARCH_NUDGE_RE = re.compile(r"증거\s*수색|확인해\s*보|맞춰\s*보|보죠")
_CLAIM_SECURED_RE = re.compile(
    r"이미\s*확보|확보했|확보한\s*(출입|로그|카드|메신저|네트워크)|출입\s*로그는\s*이미"
)
# 보유 증거가 있는데 '확보한 증거 없음'으로 거짓말
_DENY_HELD_EVIDENCE_RE = re.compile(
    r"(아직\s*)?(확보|보유)한\s*증거(는|가)?\s*없"
    r"|확보된\s*증거(는|가)?\s*없"
    r"|증거(가|는)\s*아직\s*없"
)
_CARD_FACT_RE = re.compile(r"법인카드|룸살롱|850")


def _question_netish(question: str) -> bool:
    q = question or ""
    return any(k in q for k in ("네트워크", "와이파이", "Wi-Fi", "MAC", "전송", "100GB", "외부"))


def _claims_unheld_evidence(note: str, evidence_ids: list[str]) -> bool:
    """보유 목록에 없는 증거를 '이미 확보'했다고 말하면 True."""
    text = note or ""
    if not _CLAIM_SECURED_RE.search(text):
        return False
    ids = set(evidence_ids)
    # 출입/로그 확보 주장인데 ev_log_07 없음
    if re.search(r"출입|로그", text) and "ev_log_07" not in ids:
        return True
    if re.search(r"카드|전표|룸살롱|결제", text) and "ev_card_03" not in ids:
        return True
    if re.search(r"메신저|DM|슬랙", text) and "ev_msg_12" not in ids:
        return True
    if re.search(r"네트워크|와이파이|Wi-?Fi|MAC|전송", text) and "ev_net_01" not in ids:
        return True
    # 막연한 '이미 확보'만 있고 목록이 비어 있으면 거짓
    if not ids:
        return True
    return False


def _denies_held_evidence(note: str, evidence_ids: list[str]) -> bool:
    """보유 증거가 있는데 '확보한 증거 없음'이라고 하면 True."""
    if not evidence_ids:
        return False
    return bool(_DENY_HELD_EVIDENCE_RE.search(note or ""))


def _omits_net_attribution(
    note: str,
    *,
    question: str,
    suspect_id: str,
    evidence_ids: list[str],
) -> bool:
    """네트워크 보유·질문인데 이대리 MAC 구분을 빼먹으면 True (김/박)."""
    if "ev_net_01" not in set(evidence_ids):
        return False
    if not _question_netish(question):
        return False
    if str(suspect_id or "") not in ("suspect_a", "suspect_c"):
        return False
    text = note or ""
    # 이대리 주체를 말하지 않으면 인벤토리 무시·귀속 누락으로 간주
    return "이대" not in text


def _question_cardish(question: str) -> bool:
    q = question or ""
    return any(k in q for k in ("카드", "전표", "결제", "강남", "룸살롱"))


def _pivots_after_held_card(
    note: str,
    *,
    question: str,
    suspect_id: str,
    evidence_ids: list[str],
) -> bool:
    """카드 질문·보유인데 확인 후 출입 로그 수색으로 넘기면 True."""
    if str(suspect_id or "") != "suspect_a":
        return False
    if "ev_card_03" not in set(evidence_ids):
        return False
    if not _question_cardish(question):
        return False
    text = note or ""
    if not _CARD_FACT_RE.search(text):
        return False
    return bool(_SEARCH_LOG_RE.search(text) or re.search(r"출입\s*로그", text))


def _misattributes_evidence(note: str, *, suspect_id: str) -> bool:
    """현재 심문 대상에게 남의 핵심 증거를 붙이면 True."""
    text = note or ""
    if not text.strip():
        return False
    sid = str(suspect_id or "")
    netish = bool(
        re.search(r"100\s*GB|외부\s*전송|라운지\s*Wi-?Fi|네트워크\s*기록", text, re.I)
    )
    cardish = bool(re.search(r"룸살롱|850,?000|법인카드\s*결제", text))
    msgish = bool(re.search(r"메신저|슬랙\s*DM|화장실.*서버실", text))

    if sid == "suspect_a":
        # 네트워크 스모킹건을 김팀장 것으로 말함
        if netish and "이대" not in text:
            return True
        if re.search(r"김팀장.{0,48}(네트워크|외부\s*전송|100\s*GB)", text, re.I):
            return True
    if sid == "suspect_b":
        if cardish and "김" not in text:
            return True
        if msgish and "박" not in text:
            return True
        # 네트워크를 김팀장 행위로 말함
        if netish and re.search(r"김팀장", text) and "이대" not in text:
            return True
    if sid == "suspect_c":
        if netish and "이대" not in text:
            return True
        if cardish and "김" not in text:
            return True
        if netish and re.search(r"김팀장|박신입.{0,20}전송", text) and "이대" not in text:
            return True
    return False


def _needs_corroboration_nudge(
    *,
    question: str,
    suspect_id: str,
    evidence_ids: list[str],
) -> bool:
    """알리바이·행적 질문인데 교차검증 증거가 아직 없으면 True."""
    q = question or ""
    ids = set(evidence_ids)
    alibiish = any(k in q for k in ("어디", "있었", "알리바이", "행적", "야근", "휴식", "화장실"))
    cardish = any(k in q for k in ("카드", "전표", "결제", "강남", "룸살롱"))
    logish = any(k in q for k in ("출입", "지문", "서버실", "CCTV", "로그"))
    if suspect_id == "suspect_a":
        if cardish:
            return "ev_card_03" not in ids
        if logish:
            return "ev_log_07" not in ids
        return alibiish and "ev_log_07" not in ids
    if suspect_id == "suspect_c":
        return alibiish and "ev_msg_12" not in ids
    if suspect_id == "suspect_b":
        return alibiish and "ev_net_01" not in ids
    return False


def _eun_neun(name: str) -> str:
    """한글 조사 은/는."""
    if not name:
        return "은"
    ch = name[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        return "은" if (code - 0xAC00) % 28 else "는"
    return "는"


def _assistant_fallback(
    *,
    question: str,
    suspect_id: str,
    suspect_name: str,
    evidence_ids: list[str],
) -> str:
    """주제·현재 용의자·보유 증거에 맞는 안전 조수 멘트."""
    q = question or ""
    name = (suspect_name or "용의자").strip()
    ids = set(evidence_ids)
    has_log = "ev_log_07" in ids
    has_card = "ev_card_03" in ids
    has_msg = "ev_msg_12" in ids
    has_net = "ev_net_01" in ids
    cardish = any(k in q for k in ("카드", "전표", "결제", "강남", "룸살롱"))
    logish = any(k in q for k in ("출입", "지문", "서버실", "CCTV", "로그"))
    netish = any(k in q for k in ("네트워크", "와이파이", "Wi-Fi", "MAC", "전송", "100GB", "외부"))

    if suspect_id == "suspect_a":
        # 네트워크는 이대리 루트 — 김팀장에게 귀속 금지
        if netish:
            if has_net:
                return (
                    "네트워크 대용량 전송은 이대리 노트북 MAC으로 잡혀 있어요. "
                    "김팀장 알리바이 압박은 법인카드·출입 로그 쪽이 맞아요."
                )
            return (
                "네트워크 기록은 김팀장 루트가 아니에요. "
                "김팀장은 「증거 수색」에서 법인카드·출입 로그를 맞춰 보죠."
            )
        if logish and has_log:
            return "서버실 출입 로그에 김팀장 지문이 23:10에 찍혀 있어요."
        if cardish and has_card:
            return "맞아요. 법인카드에 강남역 룸살롱 결제가 찍혀 있어요."
        if cardish and not has_card:
            return "강남 쪽을 확인하려면 「증거 수색」에서 법인카드부터 한번 보죠."
        if not has_log:
            return (
                f"{name}{_eun_neun(name)} 야근했다고 하네요. 추가 증거가 필요하니 "
                "「증거 수색」에서 서버실 출입 로그부터 확인해 보죠."
            )
        if not has_card:
            return "출입 로그엔 김팀장 기록이 있어요. 야근 알리바이는 법인카드도 맞춰 보죠."
        return "확보한 로그·카드로 김팀장 야근 주장을 교차검증해 보죠."

    if suspect_id == "suspect_c":
        if netish:
            if has_net:
                return (
                    "네트워크 전송 기록은 이대리 MAC 쪽이에요. "
                    f"{name}은 메신저로 교차검증하는 게 맞아요."
                )
            return (
                f"네트워크는 {name} 핵심 루트가 아니에요. "
                "「증거 수색」에서 메신저 기록부터 확인해 보죠."
            )
        if has_msg and any(k in q for k in ("메신저", "DM", "슬랙", "화장실", "목격", "서버실")):
            return "메신저에 박신입이 서버실 쪽을 본 듯한 기록이 있어요."
        if not has_msg:
            return (
                f"{name}{_eun_neun(name)} 화장실에 있었다고 하네요. 추가 증거가 필요하니 "
                "「증거 수색」에서 메신저 기록부터 확인해 보죠."
            )
        return f"출입 로그는 김팀장 쪽이에요. {name}은 메신저로 교차검증하는 게 맞아요."

    # 이대리 알리바이 유도 + 네트워크 보유 → 스모킹건 들이밀지 말고 교차검증 유도만
    if suspect_id == "suspect_b" and _is_alibi_probe_question(q):
        if has_net:
            return (
                f"{name} 라운지·식당 주장이네요. 확보한 네트워크를 쓰려면 "
                "Wi-Fi·MAC·전송량처럼 증거 내용을 질문으로 짚어 주세요."
            )
        return (
            f"{name}{_eun_neun(name)} 라운지·식당에 있었다고 하네요. 추가 증거가 필요하니 "
            "「증거 수색」에서 네트워크·라운지 쪽부터 확인해 보죠."
        )

    if suspect_id == "suspect_b":
        if has_net and (netish or any(k in q for k in ("라운지", "와이파이", "Wi-Fi", "MAC", "전송", "네트워크"))):
            return "라운지 Wi-Fi에서 이대리 노트북 MAC으로 대용량 전송이 잡혀 있어요."
        if logish and has_log:
            return "출입 로그에 찍힌 건 김팀장 쪽이에요. 이대리 알리바이는 네트워크·라운지 쪽을 맞춰 보죠."
        if not has_net:
            return (
                f"{name}{_eun_neun(name)} 라운지·식당에 있었다고 하네요. 추가 증거가 필요하니 "
                "「증거 수색」에서 네트워크·라운지 쪽부터 확인해 보죠."
            )
        return f"확보한 네트워크 기록으로 {name} 휴식 주장을 교차검증해 보죠."

    if cardish and not has_card:
        return "「증거 수색」에서 법인카드부터 한번 보죠."
    if not has_log:
        return "알리바이를 맞춰 보려면 「증거 수색」에서 관련 로그부터 한번 보죠."
    return f"{name} 진술은 확보한 증거로 짧게 교차검증해 보죠."


def _is_alibi_probe_question(question: str) -> bool:
    """어디 있었나 등 유도·알리바이 질문 (증거 내용 미제시)."""
    q = question or ""
    if any(
        k in q
        for k in (
            "카드",
            "룸살롱",
            "결제",
            "강남",
            "네트워크",
            "와이파이",
            "Wi-Fi",
            "MAC",
            "전송",
            "100GB",
            "100gb",
            "메신저",
            "슬랙",
            "DM",
            "지문",
            "출입",
            "로그",
        )
    ):
        return False
    return any(k in q for k in ("어디", "있었", "알리바이", "행적", "야근", "휴식", "뭐 하고"))


_SMOKING_GUN_NOTE_RE = re.compile(
    r"100\s*GB|100GB|외부\s*전송|라운지\s*Wi-?Fi|와이파이로|법인카드.{0,12}결제|850,?000|슬랙\s*DM",
    re.I,
)


def _dumps_gun_on_alibi_probe(note: str, *, question: str) -> bool:
    """알리바이 유도 질문에 스모킹건 수치를 들이밀면 True."""
    if not _is_alibi_probe_question(question):
        return False
    return bool(_SMOKING_GUN_NOTE_RE.search(note or ""))


def repair_assistant_note(
    note: str,
    *,
    question: str,
    evidence_ids: list[str] | None = None,
    evidence_briefs: list[str] | None = None,
    suspect_id: str = "",
    suspect_name: str = "",
) -> str:
    """조수 멘트가 주제·용의자·보유증거와 어긋나면 교정."""
    del evidence_briefs  # 호환용 · 판정은 evidence_ids 기준
    text = sanitize_assistant_note(note)
    ids = [str(x) for x in (evidence_ids or [])]
    sid = str(suspect_id or "")
    name = str(suspect_name or "")

    bad = False
    if not text or _VAGUE_ASSIST_RE.search(text):
        bad = True
    # 이미 출입 로그를 갖고 있는데 또 '로그부터 보죠'
    if "ev_log_07" in ids and _SEARCH_LOG_RE.search(text or ""):
        bad = True
    # 김팀장이 아닌데 김팀장 지문 멘트를 반복
    if sid and sid != "suspect_a" and _KIM_FINGERPRINT_RE.search(text or ""):
        bad = True
    # JSON 잔여
    if "{" in (text or "") or "}" in (text or ""):
        bad = True
    # 미보유 증거를 '이미 확보'했다고 거짓말
    if _claims_unheld_evidence(text or "", ids):
        bad = True
    # 보유 증거를 '아직 없어요'로 부정 (김팀장 네트워크 질문 등)
    if _denies_held_evidence(text or "", ids):
        bad = True
    # 네트워크 보유·질문인데 이대리 MAC 구분을 빼먹음
    if _omits_net_attribution(
        text or "", question=question, suspect_id=sid, evidence_ids=ids
    ):
        bad = True
    # 카드 확인 후 불필요하게 출입 로그 수색으로 피벗
    if _pivots_after_held_card(
        text or "", question=question, suspect_id=sid, evidence_ids=ids
    ):
        bad = True
    # 알리바이 유도 질문에 100GB·룸살롱 결제 등 스모킹건을 들이밈
    if _dumps_gun_on_alibi_probe(text or "", question=question):
        bad = True
    # 현재 용의자에게 남의 증거 귀속
    if sid and _misattributes_evidence(text or "", suspect_id=sid):
        bad = True
    # 알리바이 질문인데 교차검증 안내 없이 진술만 반복 → 이대리/박신입과 동일하게 보강
    if (
        sid
        and _needs_corroboration_nudge(
            question=question, suspect_id=sid, evidence_ids=ids
        )
        and not _SEARCH_NUDGE_RE.search(text or "")
    ):
        bad = True

    if not bad:
        return text
    return _assistant_fallback(
        question=question,
        suspect_id=sid,
        suspect_name=name,
        evidence_ids=ids,
    )


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


def _openai_chat(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
    timeout_sec: int,
) -> str:
    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=float(temperature),
        timeout=int(timeout_sec),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def run_collaboration_pipeline(
    *,
    question: str,
    suspect_system: str,
    assistant_system: str,
    judge_system: str,
    evidence_ids: list[str] | None = None,
    evidence_briefs: list[str] | None = None,
    recent_dialogue: str | None = None,
    session_memory: str | None = None,
    suspect_id: str = "",
    suspect_name: str = "",
    pressure: dict[str, float] | None = None,
    break_count: dict[str, int] | None = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0.2,
    timeout_sec: int = 45,
) -> dict[str, Any]:
    """
    슬라이드급 고정 협업 파이프라인 (무제한 티키타카 아님).

    ForensicAssistant(툴/보유증거) → Suspect(사실 반영) → Judge(GM 템플릿 JSON)
    LangGraph 층: story_branch로 톤·힌트 분기.
    """
    from lib.forensic_router import collect_forensic_facts
    from lib.story_branch import resolve_story_branch

    t0 = time.time()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY missing")

    who = (suspect_name or "용의자").strip()
    sid = str(suspect_id or "")
    ids = list(evidence_ids or [])
    briefs = [b.strip() for b in (evidence_briefs or []) if str(b).strip()]
    dialogue = (recent_dialogue or "").strip() or "(이전 대화 없음)"
    memory = (session_memory or "").strip()

    branch = resolve_story_branch(
        suspect_id=sid,
        evidence_ids=ids,
        pressure=pressure,
        break_count=break_count,
    )
    pack = collect_forensic_facts(
        question=question,
        suspect_id=sid,
        suspect_name=who,
        evidence_ids=ids,
        evidence_briefs=briefs,
    )
    fact_block = "\n".join(f"- {f}" for f in (pack.get("facts") or [])) or "- (없음)"

    # nudge/no_data는 라우터 문장을 그대로 사용 (LLM이 스모킹건을 다시 들이밀지 못하게)
    if str(pack.get("source") or "") in ("nudge", "no_data"):
        assist_line = repair_assistant_note(
            str(pack.get("summary") or ""),
            question=question,
            evidence_ids=ids,
            evidence_briefs=briefs,
            suspect_id=sid,
            suspect_name=who,
        )
    else:
        # ── 1) 포렌식 조수: 툴/보유 사실을 한국어 한두 문장으로 ──
        assist_sys = (assistant_system or "").strip() + (
            "\n\n[협업 파이프라인 · 조수]\n"
            "아래 【조회 사실】만 근거로 탐정에게 한두 문장 전하세요.\n"
            "함수명·영문·JSON·진범 단정 금지. 목록에 없는 사실을 지어내지 마세요.\n"
            f"【스토리 분기】 {branch.get('label')} — {branch.get('assistant_hint')}\n"
            f"【조회 사실·출처={pack.get('source')}·의도={pack.get('intent')}】\n{fact_block}\n"
            "출처가 no_data/nudge이면 보유 스모킹건(100GB 등)을 이번 질문에 끌어오지 마세요.\n"
        )
        assist_user = (
            f"심문 대상: {who}\n"
            f"탐정 질문: {question}\n"
            f"{memory}\n"
            "조수 멘트를 한국어로만 출력하세요."
        )
        assist_raw = _openai_chat(
            system=assist_sys,
            user=assist_user,
            model=model,
            temperature=min(0.3, float(temperature)),
            timeout_sec=timeout_sec,
        )
        assist_line = repair_assistant_note(
            assist_raw,
            question=question,
            evidence_ids=ids,
            evidence_briefs=briefs,
            suspect_id=sid,
            suspect_name=who,
        )
        if not assist_line.strip():
            assist_line = str(pack.get("summary") or "관련 자료를 확인했습니다.")

    # ── 2) 용의자: 조수 사실을 듣고 페르소나로 답변 ──
    suspect_sys = (suspect_system or "").strip() + (
        "\n\n[협업] 포렌식 조수가 탐정 옆에서 아래 사실을 말했습니다. "
        "당신이 그 사실을 '이미 아는' 것처럼 반응하지 말고, "
        "탐정 질문에 페르소나로만 답하세요. "
        f"【분기 톤】 {branch.get('tone')}\n"
        f"【조수 발언】 {assist_line}\n"
        "한국어 대사만. JSON 금지."
    )
    suspect_user = (
        f"[최근 심문]\n{dialogue}\n\n"
        f"감사관 질문: {question}\n"
        "3문장 이내로 답하세요."
    )
    suspect_raw = _openai_chat(
        system=suspect_sys,
        user=suspect_user,
        model=model,
        temperature=float(temperature),
        timeout_sec=timeout_sec,
    )
    suspect_answer = _extract_suspect_utterance(_strip_culprit_leak(suspect_raw))
    if not suspect_answer:
        raise RuntimeError("pipeline: empty suspect answer")

    # ── 3) 게임마스터: 템플릿 기반 JSON 제안 ──
    judge_sys = (judge_system or "").strip() or (
        "당신은 심판입니다. JSON만 출력: "
        '{"status":"lie_broken"|"no_effect","stress_delta":0,"reason_internal":"..."}'
    )
    judge_user = (
        f"사용자 발언: {question}\n"
        f"용의자 응답: {suspect_answer}\n"
        f"조수 사실: {assist_line}\n"
        f"보유 증거 ID: {', '.join(ids) or '(없음)'}\n"
        f"스토리 분기: {branch.get('id')}\n"
        "【중요】 '증거를 확보했다'는 말만으로 lie_broken 금지. "
        "현재 심문 대상의 결정적 증거 핵심(이대리=Wi-Fi/전송/100GB, "
        "김팀장=룸살롱/법인카드, 박신입=메신저/슬랙)이 발언에 있어야 함. "
        "이대리에게 룸살롱을 물으면 반드시 no_effect.\n"
        "JSON만 출력하세요."
    )
    judge_raw = _openai_chat(
        system=judge_sys,
        user=judge_user,
        model=model,
        temperature=0.0,
        timeout_sec=timeout_sec,
    )
    verdict = _parse_judge(judge_raw)
    status = str(verdict.get("status") or "no_effect")
    if status not in ("lie_broken", "no_effect"):
        status = "no_effect"
        verdict["status"] = status

    transcript = [
        {
            "role": "StoryBranch",
            "content": f"{branch.get('id')}: {branch.get('label')} (clues={branch.get('clue_count')})",
        },
        {
            "role": "ForensicTools",
            "content": json.dumps(
                {
                    "intent": pack.get("intent"),
                    "source": pack.get("source"),
                    "tools": [
                        {"name": t.get("name"), "status": (t.get("result") or {}).get("status")}
                        for t in (pack.get("tool_calls") or [])
                    ],
                },
                ensure_ascii=False,
            )[:800],
        },
        {"role": "ForensicAssistant", "content": assist_line[:800]},
        {"role": "Suspect", "content": suspect_answer[:800]},
        {"role": "Judge", "content": (_strip_culprit_leak(judge_raw) or "")[:800]},
    ]

    elapsed = round(time.time() - t0, 3)
    return {
        "backend": "autogen_pipeline",
        "answer": suspect_answer,
        "assistant_note": assist_line,
        "transcript": transcript,
        "gm_verdict": {
            "status": status,
            "stress_delta": int(verdict.get("stress_delta") or 0),
            "judge": "autogen_gm",
            "reason_internal": str(verdict.get("reason_internal") or "")[:240],
        },
        "story_branch": branch,
        "tool_pack": {
            "intent": pack.get("intent"),
            "source": pack.get("source"),
            "n_tools": len(pack.get("tool_calls") or []),
        },
        "elapsed_sec": elapsed,
        "n_messages": len(transcript),
    }


def run_interrogation_turn(
    *,
    question: str,
    suspect_system: str,
    assistant_system: str,
    judge_system: str | None = None,
    evidence_ids: list[str] | None = None,
    evidence_briefs: list[str] | None = None,
    recent_dialogue: str | None = None,
    session_memory: str | None = None,
    suspect_id: str = "",
    suspect_name: str = "",
    pressure: dict[str, float] | None = None,
    break_count: dict[str, int] | None = None,
    model: str = "gpt-4o-mini",
    max_round: int = 4,
    temperature: float = 0.2,
    timeout_sec: int = 45,
    mode: str = "pipeline",
) -> dict[str, Any]:
    """
    Detective → 협업 턴.
    mode=pipeline(기본): 조수(툴)→용의자→GM 고정 파이프라인.
    mode=groupchat: 레거시 round_robin GroupChat.
    """
    if str(mode or "pipeline").lower() != "groupchat":
        from lib.gm_judge import render_judge_prompt

        # judge_system이 이미 렌더된 본문이면 그대로, 아니면 최소 가드
        js = (judge_system or "").strip()
        if not js:
            js = render_judge_prompt(
                prompt_vars={},
                user_input=question,
                npc_response="",
            )
        return run_collaboration_pipeline(
            question=question,
            suspect_system=suspect_system,
            assistant_system=assistant_system,
            judge_system=js,
            evidence_ids=evidence_ids,
            evidence_briefs=evidence_briefs,
            recent_dialogue=recent_dialogue,
            session_memory=session_memory,
            suspect_id=suspect_id,
            suspect_name=suspect_name,
            pressure=pressure,
            break_count=break_count,
            model=model,
            temperature=temperature,
            timeout_sec=timeout_sec,
        )

    from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent

    t0 = time.time()
    ev_ids = ", ".join(evidence_ids or []) or "(없음)"
    briefs = [b.strip() for b in (evidence_briefs or []) if str(b).strip()]
    ev_facts = "\n".join(f"- {b}" for b in briefs) if briefs else "- (확보된 증거 요약 없음)"
    dialogue = (recent_dialogue or "").strip() or "(이전 대화 없음)"
    memory = (session_memory or "").strip()
    if not memory:
        memory = (
            f"[확보 증거]\n{ev_facts}\n"
            f"[이 용의자와의 최근 대화]\n{dialogue}"
        )
    who = (suspect_name or "용의자").strip()
    sid = str(suspect_id or "")
    judge_sys = judge_system or (
        "당신은 심판 AI입니다. 잡담 금지. "
        '마지막 발화는 JSON만: {"status":"lie_broken"|"no_effect","stress_delta":0,"reason_internal":"..."}. '
        "lie_broken은 탐정이 구체적 증거·모순을 제시해 알리바이가 실제로 깨졌을 때만. "
        "무의미한 문자열·장난·관련 없는 질문은 반드시 no_effect, stress_delta 0. "
        "culprit_id·진범 이름 금지."
    )
    # groupchat 경로는 기존 로직 유지 — 아래는 기존 함수 본문을 이어서 사용
    return _run_groupchat_turn(
        question=question,
        suspect_system=suspect_system,
        assistant_system=assistant_system,
        judge_sys=judge_sys,
        evidence_ids=list(evidence_ids or []),
        briefs=briefs,
        dialogue=dialogue,
        memory=memory,
        who=who,
        sid=sid,
        model=model,
        max_round=max_round,
        temperature=temperature,
        timeout_sec=timeout_sec,
        t0=t0,
        AssistantAgent=AssistantAgent,
        GroupChat=GroupChat,
        GroupChatManager=GroupChatManager,
        UserProxyAgent=UserProxyAgent,
    )


def _run_groupchat_turn(
    *,
    question: str,
    suspect_system: str,
    assistant_system: str,
    judge_sys: str,
    evidence_ids: list[str],
    briefs: list[str],
    dialogue: str,
    memory: str,
    who: str,
    sid: str,
    model: str,
    max_round: int,
    temperature: float,
    timeout_sec: int,
    t0: float,
    AssistantAgent: Any,
    GroupChat: Any,
    GroupChatManager: Any,
    UserProxyAgent: Any,
) -> dict[str, Any]:
    """레거시 AutoGen GroupChat (발표 토글용)."""
    ev_ids = ", ".join(evidence_ids) or "(없음)"
    assist = (assistant_system or "").strip()
    assist += (
        f"\n\n[심문 턴 · 출력 규칙]\n"
        f"[현재 심문 대상] {who} (id={sid or 'unknown'})\n"
        f"[세션 보유 증거 ID] {ev_ids}\n"
        f"{memory}\n"
        "위 세션 메모리를 읽되, 【확보 증거】 목록에 있는 것만 실제로 가진 증거입니다.\n"
        "이 턴에서는 함수를 호출하지 마세요. 함수명·영문 툴명·코드·JSON을 절대 말하지 마세요.\n"
        "탐정 옆 동료처럼 자연스러운 한국어로, 한두 문장만 답하세요.\n"
        f"【최우선】 지금 심문 대상은 {who}입니다.\n"
        "목록에 없는 금액·장소·시각을 추측하지 마세요. 진범 단정 금지."
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
            + "\n\n[출력] 한국어 대사만. JSON·코드블록·메타 태그 금지.\n"
            + "이전 이 탐정과의 심문 내용을 기억한 듯 자연스럽게 이어 답하세요. "
            + "다른 용의자 심문 내용을 자기 대사로 옮기지 마세요.\n"
            + f"[이 사람과의 최근 심문]\n{dialogue}"
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
        f"{memory}\n\n"
        f"현재 심문 대상: {who}\n"
        f"감사관 이번 질문: {question}\n"
        "순서: 용의자 답변 → 조수 사실 한 줄 → 심판 JSON.\n"
        "세션 메모리를 반영해 답하되, 현재 대상·이번 질문에 집중하세요."
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
            assist_line = repair_assistant_note(
                m["content"],
                question=question,
                evidence_ids=list(evidence_ids),
                evidence_briefs=briefs,
                suspect_id=sid,
                suspect_name=who,
            )
            m["content"] = assist_line
        if m["role"] == "Judge":
            judge_raw = m["content"]

    assist_line = repair_assistant_note(
        assist_line,
        question=question,
        evidence_ids=list(evidence_ids),
        evidence_briefs=briefs,
        suspect_id=sid,
        suspect_name=who,
    )
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


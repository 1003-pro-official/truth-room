# -*- coding: utf-8 -*-
"""포렌식 조수 — 질문 의도 → Function Calling / 보유 증거 사실 (슬라이드 데이터 층)."""

from __future__ import annotations

from typing import Any

from lib.game_rules import CLUE_TITLES
from lib.tools import call_tool


def _route_intent(question: str, suspect_id: str) -> str:
    """
    질문 주제만 본다. 용의자 기본 루트로 스모킹건을 자동 들이밀지 않음.
    '라운지' 단독·증언/목격 질문은 네트워크 증거로 매핑하지 않음.
    """
    q = question or ""
    # 증언·목격자 — 네트워크/카드와 별개 (자료 없음 안내)
    if any(k in q for k in ("증언", "목격자", "사람들", "봤", "목격했")):
        # '메신저로 목격' 등은 messenger가 우선
        if any(k in q for k in ("메신저", "슬랙", "DM")):
            return "messenger"
        return "witness"
    if any(k in q for k in ("카드", "전표", "결제", "강남", "룸살롱", "850")):
        return "card"
    if any(k in q for k in ("메신저", "슬랙", "DM", "화장실")):
        return "messenger"
    # 네트워크는 전송/와이파이 등 명시적 단서만 (라운지 단독 X)
    if any(
        k in q
        for k in ("네트워크", "와이파이", "Wi-Fi", "MAC", "전송", "100GB", "100gb", "외부")
    ):
        return "forensic_net"
    if any(k in q for k in ("출입", "지문", "서버실", "CCTV", "로그")):
        return "cctv"
    # 알리바이·행적만 물은 경우 — 용의자별 '다음 수색' 힌트 (보유 스모킹건 자동 인용 금지)
    if any(k in q for k in ("어디", "있었", "알리바이", "행적", "야근", "휴식", "라운지", "식당")):
        return {
            "suspect_a": "alibi_kim",
            "suspect_b": "alibi_lee",
            "suspect_c": "alibi_park",
        }.get(str(suspect_id or ""), "off_topic")
    return "off_topic"


def collect_forensic_facts(
    *,
    question: str,
    suspect_id: str,
    suspect_name: str,
    evidence_ids: list[str] | None = None,
    evidence_briefs: list[str] | None = None,
) -> dict[str, Any]:
    """
    1) 의도·보유 증거가 **같은 루트**일 때만 보유 사실을 인용.
    2) 아니면 Function Calling 또는 '자료 없음/수색 안내'.
    3) 엉뚱한 질문에 스모킹건을 자동으로 들이밀지 않음.
    """
    ids = [str(x) for x in (evidence_ids or [])]
    briefs = [str(b) for b in (evidence_briefs or []) if str(b).strip()]
    intent = _route_intent(question, suspect_id)
    name = (suspect_name or "").strip() or "용의자"
    tool_calls: list[dict[str, Any]] = []
    facts: list[str] = []

    held_map = {
        "card": "ev_card_03",
        "messenger": "ev_msg_12",
        "forensic_net": "ev_net_01",
        "cctv": "ev_log_07",
    }

    # 증언 DB 없음 — 네트워크 증거를 진실 판정용으로 끌어오지 않음
    if intent == "witness":
        facts.append(
            "라운지·식당 목격자 증언 데이터는 없어요. "
            "이대리 알리바이를 깨려면 네트워크·Wi-Fi 전송 쪽을 질문해 보죠."
        )
        return {
            "intent": intent,
            "source": "no_data",
            "facts": facts,
            "tool_calls": tool_calls,
            "summary": facts[0],
        }

    if intent == "off_topic":
        facts.append("그 질문은 지금 조회할 포렌식 자료와 안 맞아요. 알리바이·증거 쪽으로 짚어 보죠.")
        return {
            "intent": intent,
            "source": "no_data",
            "facts": facts,
            "tool_calls": tool_calls,
            "summary": facts[0],
        }

    if intent == "alibi_kim":
        if "ev_card_03" in ids or "ev_log_07" in ids:
            facts.append(
                "알리바이만으로는 부족해요. 확보한 법인카드·출입 로그로 교차검증하는 질문을 해 보죠."
            )
        else:
            facts.append("야근 주장이네요. 「증거 수색」에서 법인카드·출입 로그부터 확인해 보죠.")
        return {
            "intent": intent,
            "source": "nudge",
            "facts": facts,
            "tool_calls": tool_calls,
            "summary": facts[0],
        }

    if intent == "alibi_lee":
        if "ev_net_01" in ids:
            facts.append(
                "라운지 휴식 주장이네요. 확보한 네트워크를 쓰려면 "
                "Wi-Fi·MAC·전송량처럼 증거 내용을 질문으로 짚어 주세요."
            )
        else:
            facts.append("라운지·식당 주장이네요. 「증거 수색」에서 네트워크·라운지 쪽부터 확인해 보죠.")
        return {
            "intent": intent,
            "source": "nudge",
            "facts": facts,
            "tool_calls": tool_calls,
            "summary": facts[0],
        }

    if intent == "alibi_park":
        if "ev_msg_12" in ids:
            facts.append("화장실 주장이네요. 확보한 메신저 기록으로 교차검증하는 질문을 해 보죠.")
        else:
            facts.append("화장실 주장이네요. 「증거 수색」에서 메신저 기록부터 확인해 보죠.")
        return {
            "intent": intent,
            "source": "nudge",
            "facts": facts,
            "tool_calls": tool_calls,
            "summary": facts[0],
        }

    need = held_map.get(intent)
    if need and need in ids:
        title = CLUE_TITLES.get(need, need)
        try:
            i = ids.index(need)
            fact = briefs[i] if i < len(briefs) else title
        except ValueError:
            fact = title
        facts.append(f"[보유] {fact}")
        return {
            "intent": intent,
            "source": "held_evidence",
            "facts": facts,
            "tool_calls": tool_calls,
            "summary": facts[0],
        }

    # Function Calling (의도 일치·미보유일 때만)
    if intent == "card":
        args = {"suspect_name": "김팀장"}
        result = call_tool("check_card_history", args)
        tool_calls.append({"name": "check_card_history", "args": args, "result": result})
        if result.get("status") == "ok":
            facts.extend(str(f) for f in (result.get("facts") or [])[:2])
        else:
            facts.append(str(result.get("summary") or result.get("message") or "조회 권한 없음"))
    elif intent == "messenger":
        args = {
            "suspect_name": name if suspect_id == "suspect_c" else "박신입",
            "keyword": "서버실",
        }
        result = call_tool("search_messenger", args)
        tool_calls.append({"name": "search_messenger", "args": args, "result": result})
        if result.get("status") == "ok":
            facts.extend(str(f) for f in (result.get("facts") or [])[:2])
        else:
            facts.append(str(result.get("summary") or result.get("message") or "조회 권한 없음"))
    elif intent == "forensic_net":
        args = {"suspect_name": "이대리", "device": "lee_laptop"}
        result = call_tool("run_forensic", args)
        tool_calls.append({"name": "run_forensic", "args": args, "result": result})
        facts.append(str(result.get("summary") or "포렌식 결과 확인"))
    elif intent == "cctv":
        args = {"location": "서버실"}
        result = call_tool("request_cctv_log", args)
        tool_calls.append({"name": "request_cctv_log", "args": args, "result": result})
        facts.append(str(result.get("summary") or "CCTV 조회"))
    else:
        facts.append("관련 자료를 특정하지 못했어요.")

    return {
        "intent": intent,
        "source": "function_calling" if tool_calls else "no_data",
        "facts": facts,
        "tool_calls": tool_calls,
        "summary": facts[0] if facts else "관련 자료 미확인",
    }

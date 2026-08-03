#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/auto_ask_collect.py — 질문셋 기반 자동 심문 + CONVERSATION_LOG 적재

8/4~8/7 말투 FT용 ask 턴을 모은다. UI 크롤링이 아니라 GameEngine.ask 경로.

  # 당일 스케줄 (data/sft/auto_ask_questions.yaml)
  CONVERSATION_LOG=1 python3 scripts/auto_ask_collect.py --today

  # 날짜 지정 · 턴 수 덮어쓰기
  CONVERSATION_LOG=1 python3 scripts/auto_ask_collect.py --date 2026-08-04
  CONVERSATION_LOG=1 python3 scripts/auto_ask_collect.py --date 2026-08-04 --turns 45

  # 스모크 (3턴만, 로그 OFF여도 강제 ON)
  python3 scripts/auto_ask_collect.py --smoke

금요일 재학습:
  python3 scripts/export_conversation_log.py
  python3 scripts/local_lora_persona.py --model Qwen/Qwen2.5-3B-Instruct ...
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import yaml  # noqa: E402

_QUESTIONS = ROOT / "data" / "sft" / "auto_ask_questions.yaml"
_SUMMARY = ROOT / "runs" / "conversation_log" / "auto_ask_summary.jsonl"

_SUFFIXES = ["", "요.", "죠?", " 맞습니까?", " 설명해 주세요."]
_PREFIXES = ["", "잠깐, ", "한 가지만 더 — ", "기록상으로 "]


def _load_bank(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _variant(q: str, enabled: bool, rng: random.Random) -> str:
    q = (q or "").strip()
    if not enabled or not q:
        return q
    # 조사/어미만 가볍게 — 의미는 유지
    out = q
    if rng.random() < 0.45 and not out.endswith(("?", "요", "다", "까")):
        out = out.rstrip(". ") + rng.choice(["?", "요?", "습니까?"])
    if rng.random() < 0.35:
        out = rng.choice(_PREFIXES) + out
    if rng.random() < 0.25 and "?" not in out:
        out = out.rstrip(". ") + rng.choice(_SUFFIXES)
    return out.strip()


def _pick_queue(
    bank: dict[str, Any],
    *,
    focus: list[str],
    turns: int,
    rng: random.Random,
) -> list[tuple[str, str]]:
    """(suspect_id, question) 리스트."""
    shared = list(bank.get("shared") or [])
    by_s = bank.get("by_suspect") or {}
    pools: dict[str, list[str]] = {"shared": shared}
    for sid, qs in by_s.items():
        pools[sid] = list(qs or [])

    suspects = ["suspect_a", "suspect_b", "suspect_c"]
    queue: list[tuple[str, str]] = []
    # focus 순서대로 라운드로빈
    focus = focus or ["shared", *suspects]
    idx = {k: 0 for k in pools}
    fi = 0
    guard = 0
    while len(queue) < turns and guard < turns * 20:
        guard += 1
        key = focus[fi % len(focus)]
        fi += 1
        if key == "shared":
            pool = pools.get("shared") or []
            if not pool:
                continue
            q = pool[idx["shared"] % len(pool)]
            idx["shared"] += 1
            sid = suspects[len(queue) % 3]
            queue.append((sid, q))
        else:
            pool = pools.get(key) or []
            if not pool:
                continue
            q = pool[idx[key] % len(pool)]
            idx[key] += 1
            queue.append((key, q))
    rng.shuffle(queue)
    return queue[:turns]


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto ask collector for conversation_log")
    ap.add_argument("--questions", type=Path, default=_QUESTIONS)
    ap.add_argument("--date", type=str, default="", help="YYYY-MM-DD (스케줄 키)")
    ap.add_argument("--today", action="store_true", help="오늘 날짜로 스케줄")
    ap.add_argument("--turns", type=int, default=0, help="스케줄 turns 덮어쓰기")
    ap.add_argument("--sleep", type=float, default=0.4, help="턴 사이 sleep(초)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-variants", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="3턴만 · 강제 로그 ON")
    ap.add_argument("--force-log", action="store_true", help="CONVERSATION_LOG=1 강제")
    args = ap.parse_args()

    if args.smoke or args.force_log or args.today or args.date:
        os.environ["CONVERSATION_LOG"] = "1"
    # 기본도 수집 목적이면 ON (명시적 --no-log 없음: 스케줄 실행 시 ON)
    if not args.smoke:
        os.environ.setdefault("CONVERSATION_LOG", "1")

    bank = _load_bank(args.questions)
    rng = random.Random(args.seed)
    use_variants = bool(bank.get("variants", True)) and not args.no_variants

    day_key = ""
    if args.smoke:
        day_key = "smoke"
        turns = 3
        focus = ["shared", "suspect_a", "suspect_b"]
        label = "smoke"
    else:
        if args.today:
            day_key = date.today().isoformat()
        elif args.date:
            day_key = args.date.strip()
        else:
            day_key = date.today().isoformat()
        sched = (bank.get("schedule") or {}).get(day_key) or {}
        if not sched:
            print(
                f"스케줄 없음: {day_key} — yaml schedule 키를 확인하거나 --turns 로 직접 지정",
                file=sys.stderr,
            )
            if not args.turns:
                return 1
            turns = int(args.turns)
            focus = ["shared", "suspect_a", "suspect_b", "suspect_c"]
            label = "manual"
        else:
            turns = int(args.turns or sched.get("turns") or 45)
            focus = list(sched.get("focus") or ["shared"])
            label = str(sched.get("label") or day_key)

    queue = _pick_queue(bank, focus=focus, turns=turns, rng=rng)
    if use_variants:
        queue = [(sid, _variant(q, True, rng)) for sid, q in queue]

    from backend.game_engine import GameEngine

    eng = GameEngine()
    session = eng.create_session()
    # 조수 힌트 경로가 나오게 증거 일부 보유 (말투 다양성)
    session.evidence_ids = ["ev_card_03", "ev_msg_12", "ev_net_01"]

    ok = 0
    fail = 0
    logged = 0
    rows_out: list[dict[str, Any]] = []

    print(
        json.dumps(
            {
                "date": day_key,
                "label": label,
                "turns_planned": len(queue),
                "variants": use_variants,
                "conversation_log": os.environ.get("CONVERSATION_LOG"),
                "session_id": session.session_id,
            },
            ensure_ascii=False,
        )
    )

    for i, (sid, question) in enumerate(queue, 1):
        try:
            result = eng.ask(session, sid, question)
            ans = str(result.get("answer") or "")
            if ans:
                ok += 1
                # append는 engine 내부에서 수행. 여기선 카운트용 추정
                if os.environ.get("CONVERSATION_LOG", "").strip().lower() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                ):
                    logged += 1
            else:
                fail += 1
            rows_out.append(
                {
                    "i": i,
                    "suspect_id": sid,
                    "question": question,
                    "answer_preview": ans[:120],
                    "gm_status": result.get("gm_status"),
                    "reply_source": result.get("reply_source")
                    or (result.get("autogen") or {}).get("used"),
                }
            )
            print(f"[{i}/{len(queue)}] {sid} q={question[:40]}… ok={bool(ans)}")
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(queue)}] FAIL {sid}: {exc}", file=sys.stderr)
        if args.sleep > 0:
            time.sleep(args.sleep)

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "date": day_key,
        "label": label,
        "session_id": session.session_id,
        "ok": ok,
        "fail": fail,
        "logged_est": logged,
        "turns": len(queue),
    }
    _SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with _SUMMARY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(
        "다음(금): python3 scripts/export_conversation_log.py",
        file=sys.stderr,
    )
    return 0 if ok > 0 and fail == 0 else (0 if ok > fail else 1)


if __name__ == "__main__":
    raise SystemExit(main())

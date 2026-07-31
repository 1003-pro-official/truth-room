#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/smoke_autogen_ask.py — AutoGen 본선 ask 경로 스모크

  python3 scripts/smoke_autogen_ask.py
  python3 scripts/smoke_autogen_ask.py --offline   # API 키 없이 available()만
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    from lib.autogen_runtime import autogen_available

    out: dict = {"autogen_available": autogen_available()}
    if not out["autogen_available"]:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        print("FAIL: pip install 'pyautogen>=0.2.0,<0.3'", file=sys.stderr)
        return 1

    if args.offline:
        print(json.dumps({**out, "status": "ok_offline"}, ensure_ascii=False, indent=2))
        return 0

    from backend.game_engine import GameEngine

    eng = GameEngine()
    session = eng.create_session()
    # 증거 일부 보유 — 조수 힌트 경로
    session.evidence_ids = ["ev_card_03", "ev_net_01"]
    result = eng.ask(
        session,
        "suspect_a",
        "법인카드로 룸살롱 결제한 기록이 있는데, 그날 밤 집에 있었다고요?",
    )
    out.update(
        {
            "status": "ok" if result.get("answer") else "fail",
            "answer_preview": str(result.get("answer") or "")[:160],
            "assistant_note": str(result.get("assistant_note") or "")[:160],
            "gm_status": result.get("gm_status"),
            "autogen": result.get("autogen"),
            "n_transcript": len(result.get("agent_transcript") or []),
            "culprit_leak": "culprit_id" in json.dumps(result, ensure_ascii=False),
        }
    )
    out_path = ROOT / "runs" / "agent" / "autogen_ask_smoke.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out.get("culprit_leak"):
        print("FAIL: culprit_id leaked", file=sys.stderr)
        return 1
    if not (result.get("autogen") or {}).get("used"):
        print("WARN: AutoGen fallback — check OPENAI_API_KEY / pyautogen", file=sys.stderr)
        return 2
    return 0 if out["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

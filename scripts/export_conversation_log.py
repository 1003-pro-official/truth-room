#!/usr/bin/env python3
"""scripts/export_conversation_log.py — ask JSONL → 말투 FT 후보 jsonl

룰/판정은 export하지 않는다. 용의자 대사 위주 OpenAI messages 형식.
기본 입력: runs/conversation_log/ask_turns.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.persona_prompt import render_suspect_prompt  # noqa: E402
import yaml  # noqa: E402

_DEFAULT_IN = ROOT / "runs" / "conversation_log" / "ask_turns.jsonl"
_DEFAULT_OUT = ROOT / "runs" / "conversation_log" / "persona_ft_candidates.jsonl"
_GIBBERISH = re.compile(r"^[ㄱ-ㅎㅏ-ㅣa-zA-Z0-9\s]{1,3}$")


def _load_persona(suspect_id: str) -> dict[str, Any]:
    path = ROOT / "data" / "personas" / f"{suspect_id}.yaml"
    if not path.exists():
        return {"id": suspect_id, "name": suspect_id}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _keep_row(row: dict[str, Any]) -> bool:
    q = str(row.get("question") or "").strip()
    a = str(row.get("answer") or "").strip()
    if len(q) < 4 or len(a) < 4:
        return False
    if _GIBBERISH.match(q):
        return False
    if "편집됨" in a:
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Export ask logs to persona FT candidates")
    ap.add_argument("--input", type=Path, default=_DEFAULT_IN)
    ap.add_argument("--output", type=Path, default=_DEFAULT_OUT)
    ap.add_argument("--include-assistant", action="store_true", help="조수 멘트도 별도 샘플로")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"입력 없음: {args.input}", file=sys.stderr)
        return 1

    rows: list[dict[str, Any]] = []
    with args.input.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    out_rows: list[dict[str, Any]] = []
    skipped = 0
    for row in rows:
        if not _keep_row(row):
            skipped += 1
            continue
        sid = str(row.get("suspect_id") or "")
        persona = _load_persona(sid)
        system = render_suspect_prompt(persona, pressure=0.2, mental_break=False)
        out_rows.append(
            {
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": str(row.get("question") or "")},
                    {"role": "assistant", "content": str(row.get("answer") or "")},
                ],
                "meta": {
                    "suspect_id": sid,
                    "session_id": row.get("session_id"),
                    "ts": row.get("ts"),
                    "ft_candidate": "persona_speech",
                },
            }
        )
        note = str(row.get("assistant_note") or "").strip()
        if args.include_assistant and len(note) >= 4:
            out_rows.append(
                {
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "당신은 포렌식 조수입니다. 사실만 짧게, 동료 말투로. "
                                "진범 단정·JSON 금지."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"[대상] {row.get('suspect_name')}\n"
                                f"[질문] {row.get('question')}\n"
                                f"[보유증거] {', '.join(row.get('evidence_ids') or []) or '(없음)'}"
                            ),
                        },
                        {"role": "assistant", "content": note},
                    ],
                    "meta": {
                        "suspect_id": sid,
                        "session_id": row.get("session_id"),
                        "ts": row.get("ts"),
                        "ft_candidate": "assistant_speech",
                    },
                }
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for item in out_rows:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "output": str(args.output),
        "n_source": len(rows),
        "n_exported": len(out_rows),
        "n_skipped": skipped,
        "note": "말투 FT 후보만. 알리바이/승패 룰은 코드 유지.",
    }
    man_path = args.output.with_suffix(".manifest.yaml")
    with man_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

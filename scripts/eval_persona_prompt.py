#!/usr/bin/env python3
"""scripts/eval_persona_prompt.py — 프롬프트 고도화 스모크 (알리바이 일관성 proxy)

LLM 호출 없이 렌더된 시스템 프롬프트·SFT 모범답변 규칙 검사 + (선택) API 1턴.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from lib.persona_prompt import render_suspect_prompt  # noqa: E402

CHECKS = [
    ("알리바이 일관성 조항", "알리바이 일관성"),
    ("환각 금지 조항", "환각 금지"),
    ("진범 단정 금지", "단정적으로 진범"),
]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="gpt-4o-mini 1턴 샘플 호출")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    for sid in ("suspect_a", "suspect_b", "suspect_c"):
        persona = load_yaml(ROOT / "data" / "personas" / f"{sid}.yaml")
        prompt = render_suspect_prompt(persona, stress_level=40)
        missing = [name for name, needle in CHECKS if needle not in prompt]
        results.append(
            {
                "suspect_id": sid,
                "prompt_chars": len(prompt),
                "rules_ok": len(missing) == 0,
                "missing_rules": missing,
            }
        )

    sft = ROOT / "data" / "sft" / "persona_sft.jsonl"
    n_sft = sum(1 for _ in sft.open(encoding="utf-8")) if sft.exists() else 0

    live_sample = None
    if args.live and os.environ.get("OPENAI_API_KEY"):
        from openai import OpenAI

        client = OpenAI()
        persona = load_yaml(ROOT / "data" / "personas" / "suspect_b.yaml")
        system = render_suspect_prompt(persona, stress_level=35)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "그날 밤 어디에 있었습니까?"},
            ],
        )
        ans = (resp.choices[0].message.content or "").strip()
        alibi = str((persona.get("prompt_vars") or {}).get("주장_알리바이") or "")
        live_sample = {
            "suspect_id": "suspect_b",
            "question": "그날 밤 어디에 있었습니까?",
            "answer": ans,
            "mentions_lounge_or_alibi": ("라운지" in ans) or ("구내" in ans) or any(
                t in ans for t in alibi.replace("·", " ").split() if len(t) > 1
            ),
            "denies_ai": "AI" not in ans and "인공지능" not in ans,
        }

    out = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt_rule_checks": results,
        "all_rules_present": all(r["rules_ok"] for r in results),
        "sft_examples": n_sft,
        "live_sample": live_sample,
        "status": "ok" if all(r["rules_ok"] for r in results) else "fail",
    }
    out_path = ROOT / "runs" / "sft" / "persona_prompt_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

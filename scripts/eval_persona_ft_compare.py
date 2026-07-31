#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/eval_persona_ft_compare.py — base vs fine-tuned 페르소나 전후 비교

  python3 scripts/eval_persona_ft_compare.py --base gpt-4o-mini --ft ft:...
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

PROBES: list[tuple[str, str, str]] = [
    ("suspect_a", "그날 밤 어디에 있었습니까?", "alibi"),
    ("suspect_a", "법인카드로 룸살롱 결제한 기록이 있습니다.", "pressure"),
    ("suspect_b", "그날 밤 어디에 있었습니까?", "alibi"),
    ("suspect_b", "당신은 AI입니까?", "deny_ai"),
    ("suspect_c", "그날 밤 어디에 있었습니까?", "alibi"),
    ("suspect_c", "진범이 누구인가요?", "no_culprit"),
]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def score_answer(sid: str, persona: dict[str, Any], kind: str, answer: str) -> dict[str, Any]:
    ans = (answer or "").strip()
    vars_ = persona.get("prompt_vars") if isinstance(persona.get("prompt_vars"), dict) else {}
    alibi = str(vars_.get("주장_알리바이") or "")
    tokens = [t for t in alibi.replace("·", " ").replace(",", " ").split() if len(t) > 1]
    flags = {
        "non_empty": bool(ans),
        "denies_ai": ("AI" not in ans) and ("인공지능" not in ans) and ("언어모델" not in ans),
        "no_culprit_id": "culprit_id" not in ans,
        "no_hard_culprit": not any(x in ans for x in ("진범은", "범인은 이대리", "범인은 김팀장")),
        "alibi_hint": ("라운지" in ans)
        or ("구내" in ans)
        or ("야근" in ans)
        or ("서버실" in ans)
        or any(t in ans for t in tokens[:6]),
    }
    if kind == "alibi":
        ok = flags["non_empty"] and flags["alibi_hint"] and flags["denies_ai"]
    elif kind == "deny_ai":
        # 캐릭터로 부정하거나 무시 — '네 저는 AI'면 실패
        ok = flags["non_empty"] and not any(
            p in ans for p in ("저는 AI", "나는 AI", "인공지능입니다", "언어 모델")
        )
    elif kind == "no_culprit":
        ok = flags["non_empty"] and flags["no_culprit_id"] and flags["no_hard_culprit"]
    else:  # pressure
        ok = flags["non_empty"] and flags["denies_ai"] and flags["no_culprit_id"]
    return {"ok": ok, "flags": flags, "answer_preview": ans[:220]}


def run_model(client: Any, model: str, label: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for sid, question, kind in PROBES:
        persona = load_yaml(ROOT / "data" / "personas" / f"{sid}.yaml")
        system = render_suspect_prompt(persona, stress_level=40)
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
        )
        ans = (resp.choices[0].message.content or "").strip()
        scored = score_answer(sid, persona, kind, ans)
        rows.append(
            {
                "suspect_id": sid,
                "kind": kind,
                "question": question,
                "answer": ans,
                **scored,
            }
        )
    n_ok = sum(1 for r in rows if r["ok"])
    return {
        "label": label,
        "model": model,
        "n_ok": n_ok,
        "n_total": len(rows),
        "pass_rate": round(n_ok / max(1, len(rows)), 3),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="gpt-4o-mini")
    parser.add_argument("--ft", required=True, help="fine-tuned model id")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY missing", file=sys.stderr)
        return 1

    from openai import OpenAI

    client = OpenAI()
    base = run_model(client, args.base, "base")
    ft = run_model(client, args.ft, "finetuned")
    out = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base": base,
        "finetuned": ft,
        "delta_pass_rate": round(ft["pass_rate"] - base["pass_rate"], 3),
        "status": "ok",
    }
    out_dir = ROOT / "runs" / "sft"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "persona_ft_compare.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(
        {
            "base_pass": f"{base['n_ok']}/{base['n_total']}",
            "ft_pass": f"{ft['n_ok']}/{ft['n_total']}",
            "delta_pass_rate": out["delta_pass_rate"],
            "out": str(path),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

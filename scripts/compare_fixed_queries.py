#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/compare_fixed_queries.py — Baseline vs Advanced Hit@5 고정 쿼리 비교"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.rag_core import get_or_build_index, retrieve  # noqa: E402

QUERIES = [
    ("법인카드 룸살롱", "ev_card_03"),
    ("슬랙 DM 박신입 서버실", "ev_msg_12"),
    ("김팀장 지문 서버실", "ev_log_07"),
    ("라운지 Wi-Fi 100GB", "ev_net_01"),
]


def hit_rank(hits: list[dict], target: str) -> int | None:
    for i, h in enumerate(hits, start=1):
        if str(h.get("evidence_id") or "") == target:
            return i
    return None


def main() -> int:
    index = get_or_build_index(
        ROOT / "data/processed/chunks.jsonl",
        ROOT / "runs/rag/index/vectors.json",
    )
    rows = []
    for q, target in QUERIES:
        base = retrieve(index, q, mode="baseline", top_k=5, expand=False)
        adv = retrieve(index, q, mode="advanced", top_k=5, rrf_k=60, rerank=True, expand=True)
        br = hit_rank(base, target)
        ar = hit_rank(adv, target)
        rows.append(
            {
                "query": q,
                "target": target,
                "baseline_top1": (base[0].get("evidence_id") if base else None),
                "advanced_top1": (adv[0].get("evidence_id") if adv else None),
                "baseline_hit5": br is not None,
                "advanced_hit5": ar is not None,
                "baseline_rank": br,
                "advanced_rank": ar,
                "advanced_ids": [h.get("evidence_id") for h in adv],
            }
        )
    b_ok = sum(1 for r in rows if r["baseline_hit5"])
    a_ok = sum(1 for r in rows if r["advanced_hit5"])
    out = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "fixed_4_queries_top_k=5",
        "baseline_hit5": f"{b_ok}/4",
        "advanced_hit5": f"{a_ok}/4",
        "rows": rows,
    }
    path = ROOT / "runs" / "rag" / "exp_compare_fixed_queries.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

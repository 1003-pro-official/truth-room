#!/usr/bin/env python3
"""rag_pipeline.py — Baseline (dense) / Advanced (hybrid RRF + rerank)"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lib.rag_core import get_or_build_index, retrieve  # noqa: E402


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "advanced"], default="baseline")
    parser.add_argument("--query", default="김팀장 법인카드 23시 룸살롱")
    parser.add_argument("--config", default="configs/rag.yaml")
    args = parser.parse_args()

    cfg_path = ROOT / args.config
    if not cfg_path.exists():
        cfg_path = ROOT / "configs" / "rag.yaml.example"
    cfg = load_yaml(cfg_path)

    retrieval = cfg.get("retrieval", {})
    top_k = int(retrieval.get("top_k", 5))
    rrf_k = int(retrieval.get("rrf_k", 60))
    do_rerank = bool(retrieval.get("rerank", True)) and args.mode == "advanced"

    persist = ROOT / cfg.get("persist_dir", "runs/rag/index")
    index_path = persist / "vectors.json"
    chunks_path = ROOT / "data" / "processed" / "chunks.jsonl"
    if not chunks_path.exists():
        raise SystemExit("chunks 없음 — python3 ingest.py 먼저")

    index = get_or_build_index(chunks_path, index_path)
    hits = retrieve(
        index,
        args.query,
        mode=args.mode,
        top_k=top_k,
        rrf_k=rrf_k,
        rerank=do_rerank,
    )

    out_dir = ROOT / "runs" / "rag" / f"exp_{args.mode}"
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "mode": args.mode,
        "query": args.query,
        "top_k": top_k,
        "rrf_k": rrf_k if args.mode == "advanced" else None,
        "rerank": do_rerank,
        "n_hits": len(hits),
        "hits": [
            {
                "chunk_id": h.get("chunk_id"),
                "evidence_id": h.get("evidence_id"),
                "source_type": h.get("source_type"),
                "score": h.get("score"),
                "text": str(h.get("text", ""))[:240],
            }
            for h in hits
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": "baseline=dense · advanced=hybrid_rrf+rerank (local)",
    }
    out = out_dir / "last_query.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

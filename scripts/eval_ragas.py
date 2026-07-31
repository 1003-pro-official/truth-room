#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/eval_ragas.py — RAGAS 또는 OpenAI-embedding faithfulness 평가

  pip install 'ragas>=0.2.0' datasets   # 선택
  python3 scripts/eval_ragas.py
"""

from __future__ import annotations

import argparse
import json
import math
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

from lib.rag_core import get_or_build_index, retrieve  # noqa: E402


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def embedding_faithfulness(client: Any, answer: str, contexts: list[str]) -> float:
    """answer ↔ contexts 임베딩 코사인 (RAGAS faithfulness 대리)."""
    texts = [answer.strip()] + [(" ".join(contexts))[:4000]]
    if not texts[0] or not texts[1].strip():
        return 0.0
    resp = client.embeddings.create(model="text-embedding-3-small", input=texts)
    vecs = [d.embedding for d in resp.data]
    return round(max(0.0, _cosine(vecs[0], vecs[1])), 4)


def try_ragas(rows: list[dict[str, Any]], retrieved_map: dict[str, list[str]]) -> dict[str, Any] | None:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    except ImportError as exc:
        return {"status": "skip", "reason": f"ragas_import_fail: {exc}"}

    payload = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }
    for row in rows:
        qid = str(row.get("id") or "")
        payload["question"].append(str(row.get("question") or ""))
        payload["answer"].append(str(row.get("answer") or row.get("ground_truth") or ""))
        # RAGAS contexts = retrieved snippets
        payload["contexts"].append(retrieved_map.get(qid) or [str(c) for c in (row.get("contexts") or [])])
        payload["ground_truth"].append(str(row.get("ground_truth") or ""))

    ds = Dataset.from_dict(payload)
    try:
        result = evaluate(
            ds,
            metrics=[faithfulness, context_precision, context_recall, answer_relevancy],
        )
        # ragas Result → dict-like
        scores = dict(result) if hasattr(result, "items") else getattr(result, "_scores_dict", {})
        flat = {str(k): (float(v) if isinstance(v, (int, float)) else v) for k, v in dict(scores).items()}
        return {"status": "ok", "backend": "ragas", "scores": flat}
    except Exception as exc:  # noqa: BLE001
        return {"status": "fail", "backend": "ragas", "error": str(exc)[:400]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/eval/eval_questions.jsonl")
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    cfg = load_yaml(ROOT / "configs" / "rag.yaml") if (ROOT / "configs" / "rag.yaml").exists() else {}
    retrieval = cfg.get("retrieval") or {}
    rows = load_jsonl(ROOT / args.dataset)[: max(1, args.limit)]
    index = get_or_build_index(
        ROOT / "data/processed/chunks.jsonl",
        ROOT / "runs/rag/index/vectors.json",
    )

    retrieved_map: dict[str, list[str]] = {}
    local_prec: list[float] = []
    for row in rows:
        q = str(row.get("question") or "")
        hits = retrieve(
            index,
            q,
            mode="advanced",
            top_k=int(retrieval.get("top_k", 5)),
            rrf_k=int(retrieval.get("rrf_k", 60)),
            rerank=True,
            expand=True,
            source_routing=str(retrieval.get("source_routing") or "soft"),
        )
        snips = [str(h.get("text") or "")[:500] for h in hits]
        retrieved_map[str(row.get("id") or "")] = snips
        gold = " ".join([*(row.get("contexts") or []), str(row.get("ground_truth") or "")])
        eids = [h.get("evidence_id") for h in hits]
        import re

        gold_ids = set(re.findall(r"ev_[a-z]+_\d+", gold, flags=re.I))
        if eids:
            hits_n = sum(1 for e in eids if e and str(e).lower() in {g.lower() for g in gold_ids})
            local_prec.append(hits_n / len(eids))

    ragas_out = try_ragas(rows, retrieved_map)

    emb_scores: list[float] = []
    emb_backend = None
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI

            client = OpenAI()
            for row in rows:
                ans = str(row.get("answer") or row.get("ground_truth") or "")
                ctxs = retrieved_map.get(str(row.get("id") or "")) or [
                    str(c) for c in (row.get("contexts") or [])
                ]
                emb_scores.append(embedding_faithfulness(client, ans, ctxs))
            emb_backend = "openai_embedding_cosine"
        except Exception as exc:  # noqa: BLE001
            emb_backend = f"fail:{exc}"

    out = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n": len(rows),
        "source_routing": retrieval.get("source_routing"),
        "local_context_precision_routed": round(sum(local_prec) / len(local_prec), 4)
        if local_prec
        else None,
        "ragas": ragas_out,
        "embedding_faithfulness": {
            "backend": emb_backend,
            "mean": round(sum(emb_scores) / len(emb_scores), 4) if emb_scores else None,
            "scores": emb_scores,
        },
        "status": "ok",
    }
    path = ROOT / "runs" / "eval" / "ragas_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

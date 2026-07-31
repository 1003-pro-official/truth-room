#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/eval_ragas.py — RAGAS 또는 OpenAI-embedding faithfulness 평가

Python ≥3.10 권장 (3.12 검증). macOS 예:
  /opt/homebrew/bin/python3.12 -m venv .venv310 && source .venv310/bin/activate
  pip install ragas datasets langchain-community langchain-openai openai pyyaml python-dotenv
  python scripts/eval_ragas.py --limit 0   # 0 = 전체
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
        from ragas.metrics import ContextPrecision, ContextRecall, Faithfulness
    except ImportError as exc:
        return {"status": "skip", "reason": f"ragas_import_fail: {exc}"}

    payload = {
        "user_input": [],
        "response": [],
        "retrieved_contexts": [],
        "reference": [],
    }
    for row in rows:
        qid = str(row.get("id") or "")
        gt = str(row.get("ground_truth") or "")
        payload["user_input"].append(str(row.get("question") or ""))
        payload["response"].append(str(row.get("answer") or gt))
        payload["retrieved_contexts"].append(
            retrieved_map.get(qid) or [str(c) for c in (row.get("contexts") or [])]
        )
        payload["reference"].append(gt)

    ds = Dataset.from_dict(payload)
    # AnswerRelevancy는 임베딩 어댑터 이슈가 있어 제외 (faithfulness/precision/recall만)
    metrics = [Faithfulness(), ContextPrecision(), ContextRecall()]
    try:
        result = evaluate(ds, metrics=metrics)
        scores: dict[str, Any] = {}
        if hasattr(result, "to_pandas"):
            pdf = result.to_pandas()
            for col in ("faithfulness", "context_precision", "context_recall"):
                if col in pdf.columns:
                    series = pdf[col].dropna()
                    if len(series):
                        scores[col] = float(series.mean())
        return {
            "status": "ok",
            "backend": "ragas",
            "python": sys.version.split()[0],
            "metrics": ["faithfulness", "context_precision", "context_recall"],
            "scores": scores,
            "n": len(rows),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "fail",
            "backend": "ragas",
            "python": sys.version.split()[0],
            "error": str(exc)[:500],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/eval/eval_questions.jsonl")
    parser.add_argument("--limit", type=int, default=0, help="0이면 전체 문항")
    parser.add_argument(
        "--out",
        default="",
        help="산출 JSON 경로 (기본: runs/eval/ragas_report.json, py≥3.10이면 ragas_py312_report.json도 기록)",
    )
    args = parser.parse_args()

    cfg = load_yaml(ROOT / "configs" / "rag.yaml") if (ROOT / "configs" / "rag.yaml").exists() else {}
    retrieval = cfg.get("retrieval") or {}
    all_rows = load_jsonl(ROOT / args.dataset)
    rows = all_rows if args.limit <= 0 else all_rows[: max(1, args.limit)]
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
    out_dir = ROOT / "runs" / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = ROOT / args.out if args.out else out_dir / "ragas_report.json"
    text = json.dumps(out, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    # Python ≥3.10에서 ragas.evaluate 성공본은 py312 리포트로도 보관
    py_major, py_minor = sys.version_info[:2]
    if py_major > 3 or (py_major == 3 and py_minor >= 10):
        (out_dir / "ragas_py312_report.json").write_text(text, encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

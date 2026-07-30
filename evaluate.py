#!/usr/bin/env python3
"""evaluate.py — Faithfulness (local) · 시나리오 루브릭

RAGAS 미설치 환경에서도 context 대비 answer 토큰 겹침으로 faithfulness를 산출한다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lib.rag_core import get_or_build_index, retrieve, tokenize  # noqa: E402


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def faithfulness_score(answer: str, contexts: list[str]) -> float:
    """Fraction of answer tokens/ngrams supported by concatenated contexts."""
    ans = (answer or "").strip()
    if not ans:
        return 0.0
    ctx = " ".join(contexts)
    ctx_l = ctx.lower()
    ans_toks = [t for t in tokenize(ans) if len(t) > 1]
    if not ans_toks:
        # fallback: char bigrams for short Korean answers
        grams = [ans[i : i + 2] for i in range(max(len(ans) - 1, 0))]
        if not grams:
            return 0.0
        return round(sum(1 for g in grams if g in ctx) / len(grams), 4)
    supported = 0
    for t in ans_toks:
        if t in ctx_l or t in ctx:
            supported += 1
            continue
        # Korean substring soft match
        if len(t) >= 2 and t in ctx.replace(" ", ""):
            supported += 1
    return round(supported / len(ans_toks), 4)


def context_precision_at_k(retrieved_eids: list[str | None], gold_hints: list[str]) -> float:
    if not retrieved_eids:
        return 0.0
    gold = " ".join(gold_hints).lower()
    hits = 0
    for eid in retrieved_eids:
        if eid and eid.lower() in gold:
            hits += 1
    return round(hits / len(retrieved_eids), 4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/eval.yaml")
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="evaluate 후 update_report.py 호출 생략",
    )
    args = parser.parse_args()

    cfg_path = ROOT / args.config
    if not cfg_path.exists():
        cfg_path = ROOT / "configs" / "eval.yaml.example"
    cfg = load_yaml(cfg_path)

    dataset_path = ROOT / cfg.get("dataset", "data/processed/eval_questions.jsonl")
    rows = load_jsonl(dataset_path)
    sample_size = min(int(cfg.get("sample_size", 20)), len(rows) or 0)

    rag_cfg_path = ROOT / "configs" / "rag.yaml"
    rag_cfg = load_yaml(rag_cfg_path) if rag_cfg_path.exists() else {}
    persist = ROOT / rag_cfg.get("persist_dir", "runs/rag/index")
    index = get_or_build_index(ROOT / "data/processed/chunks.jsonl", persist / "vectors.json")
    retrieval = rag_cfg.get("retrieval", {})

    per_item: list[dict[str, Any]] = []
    faith_scores: list[float] = []
    prec_scores: list[float] = []
    relevancy_scores: list[float] = []

    for row in rows[:sample_size]:
        answer = str(row.get("answer") or row.get("ground_truth") or "")
        contexts = [str(c) for c in (row.get("contexts") or [])]
        faith = faithfulness_score(answer, contexts)
        faith_scores.append(faith)

        q = str(row.get("question", ""))
        hits = retrieve(
            index,
            q,
            mode="advanced",
            top_k=int(retrieval.get("top_k", 5)),
            rrf_k=int(retrieval.get("rrf_k", 60)),
            rerank=bool(retrieval.get("rerank", True)),
        )
        eids = [h.get("evidence_id") for h in hits]
        prec = context_precision_at_k(eids, contexts + [str(row.get("ground_truth", ""))])
        prec_scores.append(prec)

        # answer relevancy proxy: overlap(question tokens, answer tokens)
        q_set = set(tokenize(q))
        a_set = set(tokenize(answer))
        rel = round(len(q_set & a_set) / max(len(q_set), 1), 4)
        relevancy_scores.append(rel)

        per_item.append(
            {
                "id": row.get("id"),
                "faithfulness": faith,
                "context_precision": prec,
                "answer_relevancy": rel,
                "retrieved_evidence_ids": eids,
            }
        )

    def _avg(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 4) if xs else None

    # context_recall proxy: gold evidence id mentioned in contexts recovered in retrieval
    recall_scores: list[float] = []
    for row, item in zip(rows[:sample_size], per_item):
        gold_ctx = " ".join(str(c) for c in (row.get("contexts") or []))
        m = re.findall(r"ev_[\w]+", gold_ctx)
        if not m:
            continue
        retrieved = set(filter(None, item.get("retrieved_evidence_ids") or []))
        recall_scores.append(round(len(set(m) & retrieved) / len(set(m)), 4))

    metrics = {
        "faithfulness": _avg(faith_scores),
        "context_precision": _avg(prec_scores),
        "context_recall": _avg(recall_scores),
        "answer_relevancy": _avg(relevancy_scores),
    }

    out_dir = ROOT / cfg.get("output_dir", "runs/eval")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "sample_size": sample_size,
        "dataset": str(dataset_path.relative_to(ROOT)),
        "status": "ok",
        "backend": "local_token_overlap_faithfulness",
        "items": per_item,
        "note": "RAGAS 대체 로컬 메트릭 — 발표 표에 Faithfulness 수치 사용 가능",
    }
    out = out_dir / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": metrics, "sample_size": sample_size, "status": "ok"}, ensure_ascii=False, indent=2))

    if not args.no_report:
        import subprocess

        print("\nREADME.md 갱신 중 (update_report.py)...")
        subprocess.run([sys.executable, str(ROOT / "update_report.py")], cwd=ROOT, check=False)


if __name__ == "__main__":
    main()

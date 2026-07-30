"""lib/rag_core.py — local Hybrid RAG (dense + sparse RRF + rerank)

OpenAI/Chroma 없이도 스모크 가능. API 키 embedding 훅은 확장 포인트만 둔다.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣_.:/-]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.strip()]


def load_chunks(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _char_ngrams(text: str, n: int = 3) -> Counter[str]:
    s = re.sub(r"\s+", "", (text or "").lower())
    if len(s) < n:
        return Counter([s] if s else [])
    return Counter(s[i : i + n] for i in range(len(s) - n + 1))


def dense_vector(text: str, dim: int = 256) -> list[float]:
    """Simple hashing n-gram embedding (local dense)."""
    vec = [0.0] * dim
    grams = _char_ngrams(text, 3)
    for g, c in grams.items():
        idx = hash(g) % dim
        vec[idx] += float(c)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def build_index(chunks: list[dict[str, Any]], dim: int = 256) -> dict[str, Any]:
    docs: list[dict[str, Any]] = []
    df: Counter[str] = Counter()
    tokenized: list[list[str]] = []

    for c in chunks:
        text = str(c.get("text", ""))
        toks = tokenize(text)
        tokenized.append(toks)
        df.update(set(toks))
        docs.append(
            {
                "chunk_id": c.get("chunk_id"),
                "evidence_id": c.get("evidence_id"),
                "source_type": c.get("source_type"),
                "source_path": c.get("source_path"),
                "text": text,
                "dense": dense_vector(text, dim=dim),
                "tf": dict(Counter(toks)),
            }
        )

    n = max(len(docs), 1)
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in df}
    return {"dim": dim, "idf": idf, "docs": docs, "n_docs": len(docs)}


def save_index(index: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


def load_index(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _sparse_scores(index: dict[str, Any], query: str) -> list[tuple[int, float]]:
    q_tf = Counter(tokenize(query))
    idf: dict[str, float] = index.get("idf", {})
    scored: list[tuple[int, float]] = []
    for i, doc in enumerate(index.get("docs", [])):
        tf: dict[str, float] = doc.get("tf", {})
        score = 0.0
        for t, qf in q_tf.items():
            if t in tf:
                score += qf * tf[t] * idf.get(t, 1.0)
        scored.append((i, score))
    return scored


def _dense_scores(index: dict[str, Any], query: str) -> list[tuple[int, float]]:
    dim = int(index.get("dim", 256))
    qv = dense_vector(query, dim=dim)
    scored: list[tuple[int, float]] = []
    for i, doc in enumerate(index.get("docs", [])):
        scored.append((i, cosine(qv, doc.get("dense", []))))
    return scored


def _rrf(
    ranked_lists: list[list[tuple[int, float]]],
    k: int = 60,
) -> dict[int, float]:
    fused: dict[int, float] = {}
    for scored in ranked_lists:
        ordered = sorted(scored, key=lambda x: x[1], reverse=True)
        for rank, (idx, _) in enumerate(ordered, start=1):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank)
    return fused


def _rerank(
    docs: list[dict[str, Any]],
    fused: dict[int, float],
    query: str,
    boost_evidence: float = 0.15,
    boost_keyword: float = 0.05,
) -> list[tuple[int, float]]:
    q_toks = set(tokenize(query))
    out: list[tuple[int, float]] = []
    for idx, score in fused.items():
        doc = docs[idx]
        bonus = 0.0
        if doc.get("evidence_id"):
            bonus += boost_evidence
        text_toks = set(tokenize(str(doc.get("text", ""))))
        overlap = len(q_toks & text_toks)
        bonus += boost_keyword * overlap
        out.append((idx, score + bonus))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def retrieve(
    index: dict[str, Any],
    query: str,
    *,
    mode: str = "baseline",
    top_k: int = 5,
    rrf_k: int = 60,
    rerank: bool = False,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = index.get("docs", [])
    if not docs:
        return []

    dense = _dense_scores(index, query)
    if mode == "baseline":
        fused = {i: s for i, s in dense}
        ordered = sorted(fused.items(), key=lambda x: x[1], reverse=True)
    else:
        sparse = _sparse_scores(index, query)
        fused = _rrf([dense, sparse], k=rrf_k)
        ordered = (
            _rerank(docs, fused, query)
            if rerank
            else sorted(fused.items(), key=lambda x: x[1], reverse=True)
        )

    hits: list[dict[str, Any]] = []
    for idx, score in ordered[:top_k]:
        doc = dict(docs[idx])
        doc.pop("dense", None)
        doc.pop("tf", None)
        doc["score"] = round(float(score), 6)
        hits.append(doc)
    return hits


def get_or_build_index(
    chunks_path: Path | None = None,
    index_path: Path | None = None,
) -> dict[str, Any]:
    chunks_path = chunks_path or (ROOT / "data" / "processed" / "chunks.jsonl")
    index_path = index_path or (ROOT / "runs" / "rag" / "index" / "vectors.json")
    index = load_index(index_path)
    if index and index.get("docs"):
        return index
    chunks = load_chunks(chunks_path)
    index = build_index(chunks)
    save_index(index, index_path)
    return index

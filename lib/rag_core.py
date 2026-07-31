"""lib/rag_core.py — local Hybrid RAG (dense + sparse RRF + rerank)

기본 스모크·데모 백엔드. OpenAI+Chroma 실험은 `lib/rag_chroma.py`.
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
_FULL_EVIDENCE_RE = re.compile(r"^ev_[a-z]+_\d+$", re.IGNORECASE)

# Smoking Gun — exact ID에 추가 가산
CANONICAL_EVIDENCE = ("ev_card_03", "ev_msg_12", "ev_log_07", "ev_net_01")

# 쿼리 확장 (동의어·템플릿 키워드)
QUERY_EXPANSIONS: dict[str, list[str]] = {
    "슬랙": ["메신저", "DM", "slack", "대화"],
    "DM": ["슬랙", "메신저", "direct"],
    "박신입": ["신입", "박"],
    "서버실": ["server_room", "서버", "출입"],
    "법인카드": ["카드", "결제", "룸살롱"],
    "룸살롱": ["강남역", "접대", "결제"],
    "Wi-Fi": ["와이파이", "wifi", "라운지", "BULK_TRANSFER"],
    "와이파이": ["Wi-Fi", "wifi", "라운지", "100GB"],
    "100GB": ["대용량", "전송", "BULK"],
    "지문": ["fingerprint", "출입", "badge"],
}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.strip()]


def expand_query(query: str) -> str:
    """동의어·관련 키워드를 덧붙여 sparse/키워드 매칭을 보강."""
    q = (query or "").strip()
    if not q:
        return q
    extras: list[str] = []
    lower = q.lower()
    for key, syns in QUERY_EXPANSIONS.items():
        if key.lower() in lower or key in q:
            extras.extend(syns)
    if not extras:
        return q
    # 중복 제거 순서 유지
    seen = set(tokenize(q))
    add: list[str] = []
    for t in extras:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            add.append(t)
    return q if not add else f"{q} {' '.join(add)}"


def is_full_evidence_id(eid: Any) -> bool:
    return bool(eid) and bool(_FULL_EVIDENCE_RE.match(str(eid)))


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

    for c in chunks:
        text = str(c.get("text", ""))
        toks = tokenize(text)
        df.update(set(toks))
        eid = c.get("evidence_id")
        # 인덱스 단계에서도 잘린 ID 제거
        if eid and not is_full_evidence_id(eid):
            eid = None
        docs.append(
            {
                "chunk_id": c.get("chunk_id"),
                "evidence_id": eid,
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
    *,
    boost_evidence: float = 0.20,
    boost_canonical: float = 0.25,
    boost_keyword: float = 0.05,
) -> list[tuple[int, float]]:
    q_toks = set(tokenize(query))
    out: list[tuple[int, float]] = []
    for idx, score in fused.items():
        doc = docs[idx]
        bonus = 0.0
        eid = doc.get("evidence_id")
        if is_full_evidence_id(eid):
            bonus += boost_evidence
            if str(eid) in CANONICAL_EVIDENCE:
                bonus += boost_canonical
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
    expand: bool = True,
    source_types: list[str] | None = None,
    boost_evidence: float = 0.20,
    boost_canonical: float = 0.25,
    boost_keyword: float = 0.05,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = index.get("docs", [])
    if not docs:
        return []

    q = expand_query(query) if expand and mode != "baseline" else query

    dense = _dense_scores(index, q)
    if mode == "baseline":
        fused = {i: s for i, s in dense}
        ordered = sorted(fused.items(), key=lambda x: x[1], reverse=True)
    else:
        sparse = _sparse_scores(index, q)
        fused = _rrf([dense, sparse], k=rrf_k)
        ordered = (
            _rerank(
                docs,
                fused,
                q,
                boost_evidence=boost_evidence,
                boost_canonical=boost_canonical,
                boost_keyword=boost_keyword,
            )
            if rerank
            else sorted(fused.items(), key=lambda x: x[1], reverse=True)
        )

    allowed = {s.lower() for s in source_types} if source_types else None
    hits: list[dict[str, Any]] = []
    for idx, score in ordered:
        doc = docs[idx]
        if allowed and str(doc.get("source_type") or "").lower() not in allowed:
            continue
        row = dict(doc)
        row.pop("dense", None)
        row.pop("tf", None)
        row["score"] = round(float(score), 6)
        row["query_expanded"] = q if q != query else None
        hits.append(row)
        if len(hits) >= top_k:
            break
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

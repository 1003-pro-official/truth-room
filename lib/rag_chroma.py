# -*- coding: utf-8 -*-
"""lib/rag_chroma.py — OpenAI embedding + Chroma (선택 실험 백엔드)

로컬 Hybrid(`lib/rag_core.py`)와 병렬. 기본 데모/스모크는 로컬 인덱스.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _openai_client():
    from openai import OpenAI

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY 필요 — .env 확인")
    return OpenAI(api_key=key)


def embed_texts(
    texts: list[str],
    *,
    model: str = "text-embedding-3-small",
    batch_size: int = 64,
) -> list[list[float]]:
    """OpenAI embeddings API — 배치 호출."""
    client = _openai_client()
    out: list[list[float]] = []
    cleaned = [(t or " ").replace("\n", " ")[:8000] for t in texts]
    for i in range(0, len(cleaned), batch_size):
        batch = cleaned[i : i + batch_size]
        resp = client.embeddings.create(model=model, input=batch)
        # API는 index 순서로 보장되지 않을 수 있어 정렬
        ordered = sorted(resp.data, key=lambda d: d.index)
        out.extend([list(d.embedding) for d in ordered])
    return out


def chroma_persist_dir(base: Path | None = None) -> Path:
    return (base or (ROOT / "runs" / "rag" / "chroma")).resolve()


def build_chroma_collection(
    chunks: list[dict[str, Any]],
    *,
    persist_dir: Path | None = None,
    collection_name: str = "truth_room",
    embedding_model: str = "text-embedding-3-small",
    batch_size: int = 64,
) -> dict[str, Any]:
    """chunks → Chroma PersistentClient. 기존 컬렉션은 재생성."""
    import chromadb

    persist = chroma_persist_dir(persist_dir)
    persist.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist))
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    col = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine", "embedding_model": embedding_model},
    )

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    for i, c in enumerate(chunks):
        cid = str(c.get("chunk_id") or f"chunk_{i}")
        text = str(c.get("text") or "")
        ids.append(cid)
        documents.append(text)
        metadatas.append(
            {
                "evidence_id": str(c.get("evidence_id") or ""),
                "source_type": str(c.get("source_type") or ""),
                "source_path": str(c.get("source_path") or ""),
            }
        )

    for i in range(0, len(ids), batch_size):
        sl = slice(i, i + batch_size)
        embs = embed_texts(documents[sl], model=embedding_model, batch_size=batch_size)
        col.add(
            ids=ids[sl],
            documents=documents[sl],
            metadatas=metadatas[sl],
            embeddings=embs,
        )

    return {
        "backend": "openai_chroma",
        "persist_dir": str(persist),
        "collection": collection_name,
        "embedding_model": embedding_model,
        "n_docs": len(ids),
        "status": "ready",
    }


def retrieve_chroma(
    query: str,
    *,
    persist_dir: Path | None = None,
    collection_name: str = "truth_room",
    embedding_model: str = "text-embedding-3-small",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """OpenAI query embedding → Chroma cosine top-k."""
    import chromadb

    persist = chroma_persist_dir(persist_dir)
    if not persist.exists():
        raise FileNotFoundError(f"Chroma 인덱스 없음: {persist} — build_index.py --backend chroma")
    client = chromadb.PersistentClient(path=str(persist))
    col = client.get_collection(collection_name)
    q_emb = embed_texts([query], model=embedding_model)[0]
    res = col.query(
        query_embeddings=[q_emb],
        n_results=max(1, top_k),
        include=["documents", "metadatas", "distances"],
    )
    hits: list[dict[str, Any]] = []
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    for i, cid in enumerate(ids):
        meta = metas[i] if i < len(metas) else {}
        dist = float(dists[i]) if i < len(dists) else 1.0
        # cosine distance → 유사도 스코어 (클수록 좋음)
        score = 1.0 - dist
        eid = (meta or {}).get("evidence_id") or None
        if eid == "":
            eid = None
        hits.append(
            {
                "chunk_id": cid,
                "evidence_id": eid,
                "source_type": (meta or {}).get("source_type"),
                "source_path": (meta or {}).get("source_path"),
                "text": docs[i] if i < len(docs) else "",
                "score": round(score, 6),
            }
        )
    return hits

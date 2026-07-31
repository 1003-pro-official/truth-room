#!/usr/bin/env python3
"""build_index.py — chunks → local Hybrid 또는 OpenAI+Chroma 인덱스"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from lib.rag_core import build_index, load_chunks, save_index  # noqa: E402


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rag.yaml")
    parser.add_argument("--chunks", default="data/processed/chunks.jsonl")
    parser.add_argument(
        "--backend",
        choices=["local", "chroma"],
        default=None,
        help="미지정 시 configs/rag.yaml index_backend (기본 local)",
    )
    args = parser.parse_args()

    cfg_path = ROOT / args.config
    if not cfg_path.exists():
        cfg_path = ROOT / "configs" / "rag.yaml.example"
    cfg = load_yaml(cfg_path)

    chunks_path = ROOT / args.chunks
    if not chunks_path.exists():
        raise SystemExit(f"chunks 없음: {chunks_path} — 먼저 python3 ingest.py")

    chunks = load_chunks(chunks_path)
    backend = args.backend or str(cfg.get("index_backend", "local"))

    if backend == "chroma":
        from lib.rag_chroma import build_chroma_collection, chroma_persist_dir

        openai_cfg = cfg.get("openai_embedding") or {}
        model = str(openai_cfg.get("model") or "text-embedding-3-small")
        collection = str(cfg.get("collection") or "truth_room")
        persist = chroma_persist_dir(
            ROOT / str(openai_cfg.get("persist_dir") or "runs/rag/chroma")
        )
        manifest = build_chroma_collection(
            chunks,
            persist_dir=persist,
            collection_name=collection,
            embedding_model=model,
            batch_size=int(openai_cfg.get("batch_size") or 64),
        )
        manifest["created_at"] = datetime.now(timezone.utc).isoformat()
        persist.mkdir(parents=True, exist_ok=True)
        with (persist / "manifest.yaml").open("w", encoding="utf-8") as f:
            yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return

    dim = int(cfg.get("local_dense_dim", 256))
    index = build_index(chunks, dim=dim)

    persist = ROOT / cfg.get("persist_dir", "runs/rag/index")
    persist.mkdir(parents=True, exist_ok=True)
    vectors_path = persist / "vectors.json"
    save_index(index, vectors_path)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_chunks": len(chunks),
        "embedding_model": cfg.get("embedding_model", "local_hashing_ngram"),
        "backend": "local_hybrid",
        "persist_dir": str(persist.relative_to(ROOT)),
        "vectors": str(vectors_path.relative_to(ROOT)),
        "dim": dim,
        "status": "ready",
    }
    with (persist / "manifest.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)
    (persist / "README.md").write_text(
        "# Local Hybrid Index\n\n"
        "`vectors.json` — dense hashing + TF-IDF idf for sparse/RRF.\n"
        "OpenAI/Chroma: `python3 build_index.py --backend chroma`\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

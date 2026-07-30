#!/usr/bin/env python3
"""ingest.py — raw evidence → chunks.jsonl (초안)"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def detect_evidence_id(text: str) -> str | None:
    m = re.search(r'evidence_id["\']?\s*[:=]\s*["\']?(ev_[\w]+)', text)
    return m.group(1) if m else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ingest.yaml")
    args = parser.parse_args()

    cfg_path = ROOT / args.config
    if not cfg_path.exists():
        cfg_path = ROOT / "configs" / "ingest.yaml.example"
    cfg = load_yaml(cfg_path)

    max_chars = int(cfg.get("chunking", {}).get("max_chars", 400))
    overlap = int(cfg.get("chunking", {}).get("overlap", 40))
    out_chunks = ROOT / cfg.get("output", {}).get("chunks", "data/processed/chunks.jsonl")
    out_summary = ROOT / cfg.get("output", {}).get("summary", "runs/ingest/summary.yaml")
    out_chunks.parent.mkdir(parents=True, exist_ok=True)
    out_summary.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for raw_dir in cfg.get("raw_dirs", []):
        directory = ROOT / raw_dir
        source_type = Path(raw_dir).name
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {
                ".md",
                ".txt",
                ".jsonl",
                ".csv",
                ".json",
            }:
                continue
            text = path.read_text(encoding="utf-8")
            # JSON 단일 객체는 문자열로 청킹
            if path.suffix.lower() == ".json":
                try:
                    text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    pass
            for i, chunk in enumerate(chunk_text(text, max_chars, overlap)):
                records.append(
                    {
                        "chunk_id": f"{path.stem}_{i}",
                        "source_type": source_type,
                        "source_path": str(path.relative_to(ROOT)),
                        "evidence_id": detect_evidence_id(chunk),
                        "text": chunk,
                    }
                )

    with out_chunks.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "n_chunks": len(records),
        "by_source": {},
        "with_evidence_id": sum(1 for r in records if r.get("evidence_id")),
        "chunks_path": str(out_chunks.relative_to(ROOT)),
    }
    for r in records:
        summary["by_source"][r["source_type"]] = summary["by_source"].get(r["source_type"], 0) + 1
    with out_summary.open("w", encoding="utf-8") as f:
        yaml.safe_dump(summary, f, allow_unicode=True, sort_keys=False)

    print(f"[ingest] chunks={len(records)} → {out_chunks}")
    print(f"[ingest] summary → {out_summary}")


if __name__ == "__main__":
    main()

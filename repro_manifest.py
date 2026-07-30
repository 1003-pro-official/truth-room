#!/usr/bin/env python3
"""repro_manifest.py — 진실의 방 재현성 manifest"""

from __future__ import annotations

import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "runs" / "reproducibility_manifest.yaml"


def _git_rev() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _package_version(name: str) -> str | None:
    try:
        import importlib.metadata

        return importlib.metadata.version(name)
    except Exception:
        return None


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_manifest() -> dict:
    ingest = _load_yaml(ROOT / "runs" / "ingest" / "summary.yaml")
    rag = _load_yaml(ROOT / "runs" / "rag" / "index" / "manifest.yaml")
    eval_report_path = ROOT / "runs" / "eval" / "report.json"
    eval_note = str(eval_report_path.relative_to(ROOT)) if eval_report_path.is_file() else None

    configs = [
        "configs/ingest.yaml",
        "configs/rag.yaml",
        "configs/agent.yaml",
        "configs/eval.yaml",
        "configs/api.yaml",
    ]

    return {
        "source": "repro_manifest.py",
        "project": "truth-room",
        "case_id": "case_01",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "git_commit": _git_rev(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {
            "fastapi": _package_version("fastapi"),
            "pyyaml": _package_version("pyyaml"),
            "openai": _package_version("openai"),
        },
        "pipeline": {
            "ingest_chunks": ingest.get("n_chunks"),
            "rag_index": rag.get("persist_dir") or "runs/rag/index",
            "rag_status": rag.get("status"),
            "eval_report": eval_note,
        },
        "config_files": [c for c in configs if (ROOT / c).is_file()],
        "notes": "정본은 configs/*.yaml + data/ + lib/. OpenAI 키는 .env only.",
    }


def main() -> None:
    manifest = build_manifest()
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with DEFAULT_OUTPUT.open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)

    print("=== Reproducibility Manifest ===")
    print(f"git: {manifest.get('git_commit') or '(not a git repo)'}")
    print(f"chunks: {manifest['pipeline'].get('ingest_chunks')}")
    print(f"rag: {manifest['pipeline'].get('rag_status')}")
    print(f"\n저장: {DEFAULT_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

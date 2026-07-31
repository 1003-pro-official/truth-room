#!/usr/bin/env python3
"""scripts/openai_finetune_persona.py — 소량 OpenAI FT 업로드/제출 (선택)

기본은 dry-run(파일·개수만 확인). --submit 시에만 API 호출.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/sft/persona_sft.jsonl")
    parser.add_argument("--model", default="gpt-4o-mini-2024-07-18")
    parser.add_argument("--submit", action="store_true", help="실제 fine-tuning job 생성")
    args = parser.parse_args()

    path = ROOT / args.data
    if not path.exists():
        raise SystemExit(f"없음: {path} — 먼저 python3 scripts/build_persona_sft.py")
    n = sum(1 for _ in path.open(encoding="utf-8"))
    print(json.dumps({"data": str(path), "n_examples": n, "submit": args.submit}, ensure_ascii=False))

    if not args.submit:
        print("dry-run 완료. 제출하려면 --submit (OpenAI 과금)")
        return

    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    with path.open("rb") as f:
        uploaded = client.files.create(file=f, purpose="fine-tune")
    job = client.fine_tuning.jobs.create(
        training_file=uploaded.id,
        model=args.model,
        suffix="truth-room-persona",
    )
    print(json.dumps({"file_id": uploaded.id, "job_id": job.id, "status": job.status}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

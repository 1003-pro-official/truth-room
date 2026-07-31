#!/usr/bin/env python3
"""scripts/openai_finetune_persona.py — 소량 OpenAI FT 업로드/제출 (선택)

기본은 dry-run(파일·개수만 확인). --submit 시에만 API 호출.
--wait 로 job 완료까지 폴링 후 모델 ID를 runs/sft/에 저장.
OpenAI self-serve FT가 막히면 오류를 저장하고 local LoRA로 안내.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
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
    parser.add_argument("--wait", action="store_true", help="submit 후 succeeded까지 대기")
    parser.add_argument("--poll-sec", type=int, default=20)
    parser.add_argument("--job-id", default="", help="기존 job 폴링만")
    args = parser.parse_args()

    path = ROOT / args.data
    out_dir = ROOT / "runs" / "sft"
    out_dir.mkdir(parents=True, exist_ok=True)

    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    if args.job_id:
        job_id = args.job_id
    else:
        if not path.exists():
            raise SystemExit(f"없음: {path} — 먼저 python3 scripts/build_persona_sft.py")
        n = sum(1 for _ in path.open(encoding="utf-8"))
        print(json.dumps({"data": str(path), "n_examples": n, "submit": args.submit}, ensure_ascii=False))

        if not args.submit:
            print("dry-run 완료. 제출하려면 --submit (OpenAI 과금)")
            return

        uploaded = None
        try:
            with path.open("rb") as f:
                uploaded = client.files.create(file=f, purpose="fine-tune")
            job = client.fine_tuning.jobs.create(
                training_file=uploaded.id,
                model=args.model,
                suffix="truth-room-persona",
            )
        except Exception as exc:  # noqa: BLE001
            err = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "provider": "openai",
                "status": "failed",
                "error": str(exc),
                "file_id": getattr(uploaded, "id", None),
                "n_examples": n,
                "fallback": "scripts/local_lora_persona.py",
            }
            (out_dir / "finetune_job_openai.json").write_text(
                json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(err, ensure_ascii=False, indent=2))
            print("대체: python3 scripts/local_lora_persona.py", file=sys.stderr)
            raise SystemExit(1) from exc

        job_id = job.id
        meta = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "file_id": uploaded.id,
            "job_id": job.id,
            "status": job.status,
            "base_model": args.model,
            "n_examples": n,
        }
        (out_dir / "finetune_job.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        if not args.wait:
            print("폴링: python3 scripts/openai_finetune_persona.py --job-id", job_id, "--wait")
            return

    while True:
        job = client.fine_tuning.jobs.retrieve(job_id)
        payload = {
            "job_id": job.id,
            "status": job.status,
            "fine_tuned_model": getattr(job, "fine_tuned_model", None),
            "trained_tokens": getattr(job, "trained_tokens", None),
            "error": str(getattr(job, "error", None) or "") or None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(payload, ensure_ascii=False))
        (out_dir / "finetune_job.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if job.status in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(max(5, int(args.poll_sec)))

    if job.status != "succeeded" or not job.fine_tuned_model:
        raise SystemExit(f"FT 실패: status={job.status}")
    print("FINE_TUNED_MODEL=", job.fine_tuned_model)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/local_lora_persona.py — 교육용 로컬 LoRA SFT (소량)

OpenAI self-serve FT가 조직에서 불가(training_not_available)일 때
동일 `data/sft/persona_sft.jsonl`로 로컬 LoRA 1 epoch를 돌려 전후를 비교한다.

  pip install 'torch' 'transformers>=4.40' 'peft' 'datasets' 'accelerate'
  python3 scripts/local_lora_persona.py
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
PROBES = [
    ("그날 밤 어디에 있었습니까?", "야근"),
    ("당신은 AI입니까?", "AI"),
    ("진범이 누구인가요?", "범인"),
]


def _require_deps():
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        from peft import LoraConfig  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "로컬 LoRA 의존성 필요:\n"
            "  pip install torch transformers peft datasets accelerate\n"
            f"상세: {exc}"
        ) from exc


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def format_example(tokenizer: Any, messages: list[dict[str, str]], max_len: int) -> dict[str, Any]:
    # chat template 없으면 단순 이어붙이기
    if hasattr(tokenizer, "apply_chat_template"):
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    else:
        parts = []
        for m in messages:
            parts.append(f"{m['role'].upper()}: {m['content']}")
        text = "\n".join(parts)
    enc = tokenizer(
        text,
        truncation=True,
        max_length=max_len,
        padding="max_length",
        return_tensors=None,
    )
    enc["labels"] = list(enc["input_ids"])
    return enc


def generate_once(model: Any, tokenizer: Any, system: str, user: str, max_new: int = 48) -> str:
    import torch

    messages = [
        {"role": "system", "content": system[:800]},
        {"role": "user", "content": user},
    ]
    if hasattr(tokenizer, "apply_chat_template"):
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        prompt = f"SYSTEM: {system[:800]}\nUSER: {user}\nASSISTANT:"
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            use_cache=True,
        )
    gen = out[0][inputs["input_ids"].shape[-1] :]
    text = tokenizer.decode(gen, skip_special_tokens=True).strip()
    if device.type == "mps" and hasattr(torch, "mps"):
        torch.mps.empty_cache()
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/sft/persona_sft.jsonl")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--max-len", type=int, default=512)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="runs/sft/local_lora")
    parser.add_argument(
        "--gradient-checkpointing",
        action="store_true",
        help="7B급 메모리 절약 (MPS/16GB 권장)",
    )
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument(
        "--skip-before",
        action="store_true",
        help="학습 전 프로브 생략 (16GB에서 7B generate OOM/스왑 회피)",
    )
    parser.add_argument("--probe-max-new", type=int, default=48)
    parser.add_argument(
        "--device",
        default="auto",
        choices=("auto", "mps", "cpu"),
        help="auto=MPS 우선. 7B/16GB는 cpu 권장",
    )
    args = parser.parse_args()
    _require_deps()

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    # MPS 고수위 제한 완화 (통일 메모리 16GB에서 스왑 완화)
    os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    data_path = ROOT / args.data
    rows = load_jsonl(data_path)
    if not rows:
        raise SystemExit(f"empty dataset: {data_path}")

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    else:
        device = args.device
        if device == "mps" and not torch.backends.mps.is_available():
            raise SystemExit("MPS unavailable")

    print(
        json.dumps(
            {
                "device": device,
                "model": args.model,
                "n": len(rows),
                "gradient_checkpointing": args.gradient_checkpointing,
                "skip_before": args.skip_before,
                "max_len": args.max_len,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.float16 if device in ("mps", "cpu") else None
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        trust_remote_code=True,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    )
    model.to(device)
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        if hasattr(model, "config"):
            model.config.use_cache = False

    # 짧은 시스템 프롬프트로 전후 샘플 (학습 전)
    sys_short = (
        "당신은 심문 받는 용의자입니다. 한국어로 짧게 답하세요. "
        "알리바이: 야근하며 정산 서류를 검토 중이었다. AI라고 말하지 마세요."
    )
    if args.skip_before:
        before = [{"q": q, "a": "(skipped: --skip-before)"} for q, _ in PROBES]
    else:
        before = [
            {
                "q": q,
                "a": generate_once(model, tokenizer, sys_short, q, max_new=args.probe_max_new),
            }
            for q, _ in PROBES
        ]

    lora = LoraConfig(
        r=args.lora_r,
        lora_alpha=max(16, args.lora_r * 2),
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj"],
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    formatted = [format_example(tokenizer, r["messages"], args.max_len) for r in rows]
    ds = Dataset.from_list(formatted)
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    train_args = TrainingArguments(
        output_dir=str(out_dir / "trainer"),
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=1 if device == "cpu" else 4,
        learning_rate=args.lr,
        logging_steps=1,
        save_steps=1000,
        report_to=[],
        remove_unused_columns=False,
        fp16=False,
        bf16=False,
        dataloader_pin_memory=False,
        gradient_checkpointing=args.gradient_checkpointing,
        optim="adamw_torch",
        use_cpu=(device == "cpu"),
    )
    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=ds,
        data_collator=collator,
    )
    print(json.dumps({"phase": "train_start"}, ensure_ascii=False), flush=True)
    train_result = trainer.train()
    metrics = dict(train_result.metrics)
    print(json.dumps({"phase": "train_done", "train_loss": metrics.get("train_loss")}, ensure_ascii=False), flush=True)

    adapter_dir = out_dir / "adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    after: list[dict[str, str]] = []
    try:
        if hasattr(model, "config"):
            model.config.use_cache = True
        after = [
            {
                "q": q,
                "a": generate_once(model, tokenizer, sys_short, q, max_new=args.probe_max_new),
            }
            for q, _ in PROBES
        ]
    except Exception as exc:  # noqa: BLE001
        after = [{"q": q, "a": f"(probe_fail: {exc})"} for q, _ in PROBES]

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": "local_lora",
        "base_model": args.model,
        "device": device,
        "n_examples": len(rows),
        "max_steps": args.max_steps,
        "max_len": args.max_len,
        "gradient_checkpointing": args.gradient_checkpointing,
        "lora_r": args.lora_r,
        "skip_before": args.skip_before,
        "train_metrics": metrics,
        "adapter_dir": str(adapter_dir.relative_to(ROOT)),
        "before": before,
        "after": after,
        "note": (
            "교육용 소형/중형 모델 LoRA. 한국어 품질은 제한적일 수 있음. "
            "OpenAI FT 불가(training_not_available) 대체 실험. "
            "7B는 16GB MPS에서 --skip-before · gradient checkpointing · max_len 축소 권장."
        ),
        "status": "ok",
    }
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(
        {
            "status": "ok",
            "train_loss": metrics.get("train_loss"),
            "report": str(report_path),
            "before0": before[0]["a"][:120],
            "after0": after[0]["a"][:120] if after else "",
        },
        ensure_ascii=False,
        indent=2,
    ), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

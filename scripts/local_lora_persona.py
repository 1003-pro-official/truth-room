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


def generate_once(model: Any, tokenizer: Any, system: str, user: str, max_new: int = 64) -> str:
    import torch

    messages = [
        {"role": "system", "content": system[:800]},
        {"role": "user", "content": user},
    ]
    if hasattr(tokenizer, "apply_chat_template"):
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        prompt = f"SYSTEM: {system[:800]}\nUSER: {user}\nASSISTANT:"
    inputs = tokenizer(prompt, return_tensors="pt")
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen = out[0][inputs["input_ids"].shape[-1] :]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/sft/persona_sft.jsonl")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--max-len", type=int, default=512)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    _require_deps()

    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    data_path = ROOT / args.data
    rows = load_jsonl(data_path)
    if not rows:
        raise SystemExit(f"empty dataset: {data_path}")

    out_dir = ROOT / "runs" / "sft" / "local_lora"
    out_dir.mkdir(parents=True, exist_ok=True)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(json.dumps({"device": device, "model": args.model, "n": len(rows)}, ensure_ascii=False))

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(args.model, trust_remote_code=True)
    model.to(device)

    # 짧은 시스템 프롬프트로 전후 샘플 (학습 전)
    sys_short = (
        "당신은 심문 받는 용의자입니다. 한국어로 짧게 답하세요. "
        "알리바이: 야근하며 정산 서류를 검토 중이었다. AI라고 말하지 마세요."
    )
    before = [
        {"q": q, "a": generate_once(model, tokenizer, sys_short, q)} for q, _ in PROBES
    ]

    lora = LoraConfig(
        r=8,
        lora_alpha=16,
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
        gradient_accumulation_steps=4,
        learning_rate=args.lr,
        logging_steps=5,
        save_steps=1000,
        report_to=[],
        remove_unused_columns=False,
        fp16=False,
        bf16=False,
        dataloader_pin_memory=False,
    )
    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=ds,
        data_collator=collator,
    )
    train_result = trainer.train()
    metrics = dict(train_result.metrics)

    adapter_dir = out_dir / "adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    after = [
        {"q": q, "a": generate_once(model, tokenizer, sys_short, q)} for q, _ in PROBES
    ]

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": "local_lora",
        "base_model": args.model,
        "device": device,
        "n_examples": len(rows),
        "max_steps": args.max_steps,
        "train_metrics": metrics,
        "adapter_dir": str(adapter_dir.relative_to(ROOT)),
        "before": before,
        "after": after,
        "note": (
            "교육용 소형 모델 LoRA. 한국어 품질은 제한적일 수 있음. "
            "OpenAI FT 불가(training_not_available) 대체 실험."
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
            "after0": after[0]["a"][:120],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

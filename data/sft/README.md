# data/sft — 소량 페르소나 SFT (대규모 FT 아님)

```bash
python3 scripts/build_persona_sft.py
python3 scripts/eval_persona_prompt.py --live

# OpenAI FT (조직에 권한이 있을 때만 — 본 레포는 training_not_available로 실패 기록)
python3 scripts/openai_finetune_persona.py          # dry-run
python3 scripts/openai_finetune_persona.py --submit --wait

# 교육용 로컬 LoRA ladder
pip install torch transformers peft datasets accelerate
python3 scripts/local_lora_persona.py --max-steps 30
python3 scripts/local_lora_persona.py --model Qwen/Qwen2.5-0.5B-Instruct --out-dir runs/sft/local_lora_qwen05
python3 scripts/local_lora_persona.py --model Qwen/Qwen2.5-1.5B-Instruct --max-steps 20 --out-dir runs/sft/local_lora_qwen15
python3 scripts/local_lora_persona.py --model Qwen/Qwen2.5-3B-Instruct --max-steps 12 --max-len 320 --out-dir runs/sft/local_lora_qwen3b
# 7B는 16GB에서 memory_limit (로드·trainable%만 확인) — 32GB+/QLoRA 권장
# python3 scripts/local_lora_persona.py --model Qwen/Qwen2.5-7B-Instruct --device cpu --skip-before --gradient-checkpointing --out-dir runs/sft/local_lora_qwen7b

# RAGAS (Python ≥3.10 권장 — 3.12 검증됨)
# /opt/homebrew/bin/python3.12 -m venv .venv310 && source .venv310/bin/activate
# pip install ragas datasets langchain-community langchain-openai openai pyyaml python-dotenv
python scripts/eval_ragas.py --limit 0   # 전체 n=30 → runs/eval/ragas_py312_report.json
```

- `persona_sft.jsonl` — OpenAI fine-tuning `messages` 형식 (78쌍)
- `manifest.yaml` — 샘플 수·생성 시각
- 산출물:
  - `runs/sft/finetune_job_openai.json` (OpenAI 403 기록)
  - `runs/sft/local_lora/` · `local_lora_qwen05/` · `qwen15/` · `qwen3b/` · `qwen7b/report.json` (`memory_limit`)
  - `runs/sft/lora_model_compare.json`
  - `runs/eval/ragas_py312_report.json` (n=30 · Faith≈0.64 · Prec≈0.75 · Recall≈0.77)

# data/sft — 소량 페르소나 SFT (대규모 FT 아님)

```bash
python3 scripts/build_persona_sft.py
python3 scripts/eval_persona_prompt.py --live

# OpenAI FT (조직에 권한이 있을 때만)
python3 scripts/openai_finetune_persona.py          # dry-run
python3 scripts/openai_finetune_persona.py --submit --wait

# OpenAI FT 불가 시 교육용 로컬 LoRA
pip install torch transformers peft datasets accelerate
python3 scripts/local_lora_persona.py --max-steps 30
python3 scripts/local_lora_persona.py --model Qwen/Qwen2.5-1.5B-Instruct --max-steps 20 --out-dir runs/sft/local_lora_qwen15

# RAGAS (Python ≥3.10 권장 — 3.12 검증됨)
# /opt/homebrew/bin/python3.12 -m venv .venv310 && source .venv310/bin/activate
# pip install ragas datasets langchain-community langchain-openai openai pyyaml python-dotenv
python scripts/eval_ragas.py --limit 6   # → runs/eval/ragas_py312_report.json

# 3B LoRA
python3 scripts/local_lora_persona.py --model Qwen/Qwen2.5-3B-Instruct --max-steps 12 --max-len 320 --out-dir runs/sft/local_lora_qwen3b
```

- `persona_sft.jsonl` — OpenAI fine-tuning `messages` 형식 (78쌍)
- `manifest.yaml` — 샘플 수·생성 시각
- 산출물: `runs/sft/finetune_job_openai.json` · `runs/sft/local_lora/report.json`

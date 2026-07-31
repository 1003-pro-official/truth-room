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
```

- `persona_sft.jsonl` — OpenAI fine-tuning `messages` 형식 (78쌍)
- `manifest.yaml` — 샘플 수·생성 시각
- 산출물: `runs/sft/finetune_job_openai.json` · `runs/sft/local_lora/report.json`

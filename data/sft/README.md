# data/sft — 소량 페르소나 SFT (대규모 FT 아님)

```bash
python3 scripts/build_persona_sft.py
python3 scripts/eval_persona_prompt.py --live
python3 scripts/openai_finetune_persona.py          # dry-run
# python3 scripts/openai_finetune_persona.py --submit  # 과금
```

- `persona_sft.jsonl` — OpenAI fine-tuning `messages` 형식
- `manifest.yaml` — 샘플 수·생성 시각

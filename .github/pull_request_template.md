## Summary

<!-- 변경 요약 (1~3문장) -->

## Role

<!-- Scenario / Prompt / RAG / Agent / Service / Docs -->

- [ ] Scenario / Data 원문
- [ ] Prompt / Persona
- [ ] RAG / Tools
- [ ] Agent / LangGraph
- [ ] Service / Demo
- [ ] PM / Docs

## Checklist

- [ ] `configs/*.yaml` 변경 시 하드코딩 없음
- [ ] `.env` / 비밀키 미포함
- [ ] `culprit_id`를 API 기본 응답·UI에 노출하지 않음
- [ ] (RAG) Baseline/Advanced 결과는 `runs/rag/exp_*/` · README 표 갱신(해당 시)
- [ ] (Agent) `--smoke` 또는 관련 시나리오 검증
- [ ] (Service) **React / Streamlit** → **FastAPI only** (LLM/인덱스 직결 없음)
- [ ] (Service) `/docs` Swagger 또는 `/game/` UI 스크린샷
- [ ] Only Me 아님 — 역할 밖 대규모 변경 시 리뷰

## Anti-pattern self-check

원칙: [AI_CONVENTION.md](AI_CONVENTION.md) · [docs/ANTIPATTERNS.md](docs/ANTIPATTERNS.md)

- [ ] UI → API 단일 경로
- [ ] Only Me 아님 (리뷰)
- [ ] Smoke / 로컬 재현 명령 PR 본문에 있음

## Test plan

```bash
# 예:
# python3 ingest.py && python3 build_index.py
# python3 rag_pipeline.py --mode advanced --query "…"
# python3 agent_graph.py --smoke
# python3 -m pytest tests/smoke -q   # API 기동 후
```

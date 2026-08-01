# TRAINING_CHECKLIST — RAG / Agent 실험 준비

> 진실의 방 파이프라인 체크리스트.

---

## 환경

- [ ] `.env`에 `OPENAI_API_KEY` (LLM 연동 시)
- [ ] `pip install -r requirements.txt -r requirements-llm.txt`
- [ ] `configs/*.yaml` 존재

## Data

- [ ] 시나리오·페르소나 리뷰 (`case_01` · 100억의 야근자들)
- [ ] `data/raw/` 4소스 (messenger·logs·corporate_card·network) · evidence_id
- [ ] `python3 ingest.py` · `python3 build_index.py` → `runs/rag/index/`

## RAG

- [ ] `python3 rag_pipeline.py --mode baseline`
- [ ] `python3 rag_pipeline.py --mode advanced`
- [ ] 결과를 `runs/rag/exp_*/` · README 표에 반영

## Agent

- [ ] `python3 agent_graph.py --smoke` → `backend: langgraph`
- [ ] `python3 scripts/smoke_autogen_ask.py`
- [ ] 페르소나 자백 가드레일 (`ev_net_01` 전 부인) 확인

## Eval · Demo

- [x] `python3 evaluate.py`
- [x] `python3 scripts/eval_ragas.py` (n=30 · py≥3.10)
- [x] `python3 scripts/plot_metrics.py`
- [x] API + Streamlit Golden Route 1회 · 또는 Railway https://web-production-072b8.up.railway.app
- [x] `culprit_id` 클라이언트 미노출
